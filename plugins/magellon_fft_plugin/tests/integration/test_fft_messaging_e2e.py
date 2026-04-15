"""End-to-end test: 10 FFT tasks, real RMQ + NATS, in-process plugin.

Pipeline exercised
------------------

    test publishes TaskDto -> RMQ fft_tasks_queue
       -> plugin consumer thread picks up
          -> do_execute runs FFT, writes PNG to disk
             -> emits started / progress / completed envelopes
                -> NATS JetStream stream MAGELLON_STEP_EVENTS
                   <- test's NATS pull-subscriber drains them

Asserts:
- 10 input PNGs are produced before dispatch
- 10 output ``*_FFT.png`` files exist on disk after processing
- Exactly 10 ``magellon.step.started`` events
- At least 10 ``magellon.step.progress`` events (we emit two per task)
- Exactly 10 ``magellon.step.completed`` events
- 0 ``magellon.step.failed`` events
- The set of task_ids covered by ``started`` matches the dispatched set

This test is the smallest-footprint proof that the plugin contract
holds end-to-end with real brokers.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import List

import pytest

logger = logging.getLogger(__name__)

# Soft 90s ceiling — RMQ container cold-start can eat 10-15s on the
# first run, plus NATS, plus 10 FFTs. If we ever blow past this,
# something is genuinely stuck.
TEST_BUDGET = 90.0


# ---- helpers ----


def _generate_input_images(target_dir: Path, count: int) -> List[Path]:
    """Try Picsum (no API key needed). Fall back to deterministic
    numpy noise if the network is down — the FFT path doesn't care."""
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    try:
        import requests
    except Exception:
        requests = None

    for i in range(count):
        out = target_dir / f"sample_{i:02d}.png"
        wrote = False
        if requests is not None:
            try:
                # Picsum's seeded URL gives stable bytes per seed — handy
                # if a debug session needs to compare runs.
                resp = requests.get(
                    f"https://picsum.photos/seed/fft-{i}/256/256",
                    timeout=5,
                )
                if resp.status_code == 200 and resp.content:
                    out.write_bytes(resp.content)
                    wrote = True
            except Exception:
                wrote = False

        if not wrote:
            import numpy as np
            from PIL import Image

            rng = np.random.default_rng(seed=i)
            arr = (rng.random((256, 256)) * 255).astype("uint8")
            Image.fromarray(arr, mode="L").save(out)

        paths.append(out)
    return paths


def _publish_task_dto(rmq_settings, queue_name: str, image_path: Path, target_path: Path,
                      job_id: uuid.UUID, task_id: uuid.UUID) -> None:
    """Publish one FFT TaskDto onto fft_tasks_queue.

    Uses the plugin's own helper module so we exercise the same
    publish path the plugin uses for outbound messages. The plugin
    side reads the same singleton, so credentials match.
    """
    from core.helper import publish_message_to_queue
    from core.task_factory import FftTaskFactory
    from magellon_sdk.models import FftTaskData
    from magellon_sdk.models.tasks import PENDING, FFT_TASK

    data = FftTaskData(
        image_id=None,
        image_name=image_path.stem,
        image_path=str(image_path),
        target_path=str(target_path),
        target_name=target_path.name,
    )
    task = FftTaskFactory.create_task(
        pid=task_id,
        instance_id=uuid.uuid4(),
        job_id=job_id,
        data=data.model_dump(),
        ptype=FFT_TASK,
        pstatus=PENDING,
    )
    ok = publish_message_to_queue(task, queue_name)
    assert ok, f"failed to publish task {task_id} to {queue_name}"


async def _drain_step_events(nats_url: str, stream: str, subjects: str,
                             expected_completed: int, deadline: float) -> List[dict]:
    """Pull-subscribe and collect envelopes until ``expected_completed``
    completed events arrive or ``deadline`` (wall-clock) elapses."""
    import nats
    from nats.errors import Error as NatsError

    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    # The plugin's publisher creates the stream on first emit. Wait for
    # it so the consumer subscribes against a real stream rather than
    # racing the publisher.
    end = deadline
    while time.monotonic() < end:
        try:
            await js.stream_info(stream)
            break
        except NatsError:
            await asyncio.sleep(0.2)
    else:
        await nc.close()
        raise AssertionError(f"NATS stream {stream!r} never appeared")

    durable = f"e2e-{uuid.uuid4().hex[:8]}"
    try:
        await js.add_consumer(stream, durable_name=durable, ack_policy="explicit")
    except NatsError:
        pass
    sub = await js.pull_subscribe(subjects, durable=durable)

    received: List[dict] = []
    completed = 0
    try:
        while time.monotonic() < end and completed < expected_completed:
            try:
                msgs = await sub.fetch(batch=20, timeout=1.0)
            except (asyncio.TimeoutError, NatsError):
                continue
            for msg in msgs:
                env = json.loads(msg.data.decode("utf-8"))
                received.append(env)
                if env.get("type") == "magellon.step.completed":
                    completed += 1
                await msg.ack()
    finally:
        try:
            await sub.unsubscribe()
        except Exception:
            pass
        await nc.close()

    return received


def _start_consumer_thread() -> threading.Thread:
    """Boot the FFT plugin's broker runner on a daemon thread.

    Lazy import so the conftest can inject test brokers before the
    runner reads ``AppSettingsSingleton``.
    """
    from core.settings import AppSettingsSingleton
    from magellon_sdk.categories.contract import FFT
    from service.plugin import FftBrokerRunner, FftPlugin, build_fft_result

    rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
    runner = FftBrokerRunner(
        plugin=FftPlugin(),
        settings=rmq,
        in_queue=rmq.QUEUE_NAME,
        out_queue=rmq.OUT_QUEUE_NAME,
        result_factory=build_fft_result,
        contract=FFT,
    )
    t = threading.Thread(
        target=runner.start_blocking, daemon=True, name="fft-consumer-e2e"
    )
    t.start()
    return t


# ---- the test ----


def test_ten_ffts_round_trip_with_lifecycle_events(configured_plugin, tmp_path):
    info = configured_plugin
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    images = _generate_input_images(inputs_dir, count=10)
    assert len(images) == 10
    for p in images:
        assert p.exists() and p.stat().st_size > 0

    # Boot the plugin's RMQ consumer before publishing so the queue is
    # declared and the consumer is attached when our messages land.
    _start_consumer_thread()
    time.sleep(2.0)

    job_id = uuid.uuid4()
    task_ids = [uuid.uuid4() for _ in range(10)]
    targets = [outputs_dir / f"{img.stem}_FFT.png" for img in images]

    from core.settings import AppSettingsSingleton

    rmq_settings = AppSettingsSingleton.get_instance().rabbitmq_settings

    for img, tgt, tid in zip(images, targets, task_ids):
        _publish_task_dto(
            rmq_settings,
            queue_name=info["queue_name"],
            image_path=img,
            target_path=tgt,
            job_id=job_id,
            task_id=tid,
        )

    deadline = time.monotonic() + TEST_BUDGET
    received = asyncio.run(
        _drain_step_events(
            nats_url=info["nats"]["url"],
            stream=info["stream"],
            subjects=info["subjects"],
            expected_completed=10,
            deadline=deadline,
        )
    )

    # ---- output files ----
    missing = [tgt for tgt in targets if not tgt.exists() or tgt.stat().st_size == 0]
    assert not missing, f"FFT outputs missing or empty: {missing}"

    # ---- step events ----
    by_type: dict = {}
    for env in received:
        by_type.setdefault(env["type"], []).append(env)

    started = by_type.get("magellon.step.started", [])
    progress = by_type.get("magellon.step.progress", [])
    completed = by_type.get("magellon.step.completed", [])
    failed = by_type.get("magellon.step.failed", [])

    assert len(failed) == 0, f"unexpected failed events: {failed}"
    assert len(started) == 10, f"started count={len(started)} (events: {by_type})"
    assert len(completed) == 10, f"completed count={len(completed)} (events: {by_type})"
    # Two ticks per task: ``loading image`` + ``writing PNG``.
    assert len(progress) >= 20, f"progress count={len(progress)} (events: {by_type})"

    started_task_ids = {ev["data"]["task_id"] for ev in started}
    expected_task_ids = {str(t) for t in task_ids}
    assert started_task_ids == expected_task_ids, (
        f"started task_ids drift: missing="
        f"{expected_task_ids - started_task_ids}, "
        f"extra={started_task_ids - expected_task_ids}"
    )

    # All events must belong to the single job we dispatched against.
    for env in received:
        assert env["data"]["job_id"] == str(job_id), env

    # Each completed event should carry the output file path it produced.
    completed_outputs = {
        ev["data"]["output_files"][0] for ev in completed if ev["data"].get("output_files")
    }
    expected_outputs = {str(p) for p in targets}
    assert completed_outputs == expected_outputs, (
        f"completed outputs drift: missing="
        f"{expected_outputs - completed_outputs}, "
        f"extra={completed_outputs - expected_outputs}"
    )
