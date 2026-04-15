"""End-to-end test: 10 FFT tasks against the FFT plugin running as a real subprocess.

Goes one step further than ``test_fft_messaging_e2e.py`` — the plugin
runs as a uvicorn process (the way it ships in production), not an
in-process daemon thread. Catches startup, config-loading, and
process-boundary bugs that the in-process variant can't see.

Pipeline exercised
------------------

    test publishes TaskDto -> RMQ fft_tasks_queue_subproc
       -> FFT plugin SUBPROCESS (uvicorn) consumer thread picks up
          -> do_execute runs FFT, writes PNG
             -> emits started / progress / completed envelopes
                -> NATS stream MAGELLON_STEP_EVENTS_SUBPROC
                   <- test's NATS pull-subscriber drains them

Uses queue + stream names suffixed with ``_subproc`` so this test can
coexist with the in-process variant in the same pytest session
without the two consumers stealing each other's messages.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Iterator, List

import pika
import pytest
import requests

logger = logging.getLogger(__name__)

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
TEST_BUDGET = 120.0  # subprocess cold-start eats ~5-10s on top of G1's budget

QUEUE_NAME = "fft_tasks_queue_subproc"
NATS_STREAM = "MAGELLON_STEP_EVENTS_SUBPROC"
NATS_SUBJECTS = "magellon.job.*.step.*"


# ---- helpers ----


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(port: int, deadline: float = 30.0) -> None:
    end = time.monotonic() + deadline
    last_err: Exception | None = None
    while time.monotonic() < end:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)
            if r.status_code == 200:
                return
        except Exception as exc:
            last_err = exc
        time.sleep(0.5)
    raise RuntimeError(f"FFT subprocess /health not 200 within {deadline}s: {last_err}")


def _write_settings_yaml(target_path: Path, rmq: dict) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        f"""
ENV_TYPE: development
LOCAL_IP_ADDRESS: 127.0.0.1
PORT_NUMBER: 0

REPLACE_TYPE: none
REPLACE_PATTERN: ''
REPLACE_WITH: ''

JOBS_DIR: ''
HOST_JOBS_DIR: ''

consul_settings:
  CONSUL_HOST: ''
  CONSUL_PORT: 0

database_settings: {{}}

rabbitmq_settings:
  HOST_NAME: {rmq['host']}
  PORT: {rmq['port']}
  USER_NAME: {rmq['username']}
  PASSWORD: {rmq['password']}
  VIRTUAL_HOST: '/'
  SSL_ENABLED: false
  CONNECTION_TIMEOUT: 30
  PREFETCH_COUNT: 10
  QUEUE_NAME: {QUEUE_NAME}
  OUT_QUEUE_NAME: fft_out_tasks_queue_subproc
""".strip()
    )


@pytest.fixture(scope="module")
def fft_subprocess(rmq_container, nats_container, tmp_path_factory) -> Iterator[dict]:
    """Boot the FFT plugin via ``uvicorn main:app`` pointed at the test brokers.

    Uses MAGELLON_SETTINGS_FILE so we don't have to mutate the
    plugin's bundled configs/ dir. Stream name is suffixed so this
    test's events don't collide with the in-process variant's stream.
    """
    settings_dir = tmp_path_factory.mktemp("fft_subproc_settings")
    settings_path = settings_dir / "settings.yml"
    _write_settings_yaml(settings_path, rmq_container)

    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "development",
            "MAGELLON_SETTINGS_FILE": str(settings_path),
            "MAGELLON_STEP_EVENTS_ENABLED": "1",
            "MAGELLON_STEP_EVENTS_RMQ": "0",
            "NATS_URL": nats_container["url"],
            "NATS_STEP_EVENTS_STREAM": NATS_STREAM,
            "NATS_STEP_EVENTS_SUBJECTS": NATS_SUBJECTS,
            "PYTHONUNBUFFERED": "1",
        }
    )
    # Make ``core.*`` / ``service.*`` resolvable regardless of CWD.
    env["PYTHONPATH"] = str(PLUGIN_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(cmd, cwd=str(PLUGIN_ROOT), env=env)
    try:
        _wait_for_health(port, deadline=30.0)
        yield {"port": port, "proc": proc}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _generate_input_images(target_dir: Path, count: int) -> List[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []
    for i in range(count):
        out = target_dir / f"sub_{i:02d}.png"
        wrote = False
        try:
            r = requests.get(
                f"https://picsum.photos/seed/fft-sub-{i}/256/256", timeout=5
            )
            if r.status_code == 200 and r.content:
                out.write_bytes(r.content)
                wrote = True
        except Exception:
            pass
        if not wrote:
            import numpy as np
            from PIL import Image

            rng = np.random.default_rng(seed=100 + i)
            arr = (rng.random((256, 256)) * 255).astype("uint8")
            Image.fromarray(arr, mode="L").save(out)
        paths.append(out)
    return paths


def _publish_via_pika(rmq: dict, queue: str, payload: dict) -> None:
    """Publish one TaskDto JSON onto ``queue`` via a fresh blocking
    connection. Test process publishes directly so it doesn't need to
    share the plugin's settings singleton with the subprocess."""
    creds = pika.PlainCredentials(rmq["username"], rmq["password"])
    params = pika.ConnectionParameters(
        host=rmq["host"], port=rmq["port"], credentials=creds, virtual_host="/"
    )
    conn = pika.BlockingConnection(params)
    try:
        ch = conn.channel()
        ch.queue_declare(queue=queue, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=queue,
            body=json.dumps(payload).encode("utf-8"),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
        )
    finally:
        conn.close()


def _build_task_payload(*, image_path: Path, target_path: Path,
                        job_id: uuid.UUID, task_id: uuid.UUID) -> dict:
    """Hand-build the TaskDto JSON the plugin's parser expects.

    Bypasses the plugin's TaskFactory so the test isn't coupled to its
    Python types — only to the wire schema, which is what the plugin
    actually consumes from RMQ.
    """
    return {
        "id": str(task_id),
        "instance_id": str(uuid.uuid4()),
        "job_id": str(job_id),
        "type": {"code": 1, "name": "FFT", "description": "Fast Fourier Transform"},
        "pstatus": {"code": 0, "name": "pending", "description": "Task is pending"},
        "status": {"code": 0, "name": "pending", "description": "Task is pending"},
        "data": {
            "image_id": None,
            "image_name": image_path.stem,
            "image_path": str(image_path),
            "target_path": str(target_path),
            "target_name": target_path.name,
        },
    }


async def _drain_step_events(nats_url: str, stream: str, subjects: str,
                             expected_completed: int, deadline: float) -> List[dict]:
    import nats
    from nats.errors import Error as NatsError

    nc = await nats.connect(nats_url)
    js = nc.jetstream()

    while time.monotonic() < deadline:
        try:
            await js.stream_info(stream)
            break
        except NatsError:
            await asyncio.sleep(0.2)
    else:
        await nc.close()
        raise AssertionError(f"NATS stream {stream!r} never appeared")

    durable = f"e2e-sub-{uuid.uuid4().hex[:8]}"
    try:
        await js.add_consumer(stream, durable_name=durable, ack_policy="explicit")
    except NatsError:
        pass
    sub = await js.pull_subscribe(subjects, durable=durable)

    received: List[dict] = []
    completed = 0
    try:
        while time.monotonic() < deadline and completed < expected_completed:
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


# ---- the test ----


@pytest.mark.integration_subprocess
def test_subprocess_processes_ten_ffts_end_to_end(
    fft_subprocess, rmq_container, nats_container, tmp_path
):
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    images = _generate_input_images(inputs_dir, count=10)
    assert len(images) == 10
    for p in images:
        assert p.exists() and p.stat().st_size > 0

    job_id = uuid.uuid4()
    task_ids = [uuid.uuid4() for _ in range(10)]
    targets = [outputs_dir / f"{img.stem}_FFT.png" for img in images]

    for img, tgt, tid in zip(images, targets, task_ids):
        payload = _build_task_payload(
            image_path=img, target_path=tgt, job_id=job_id, task_id=tid
        )
        _publish_via_pika(rmq_container, QUEUE_NAME, payload)

    deadline = time.monotonic() + TEST_BUDGET
    received = asyncio.run(
        _drain_step_events(
            nats_url=nats_container["url"],
            stream=NATS_STREAM,
            subjects=NATS_SUBJECTS,
            expected_completed=10,
            deadline=deadline,
        )
    )

    missing = [t for t in targets if not t.exists() or t.stat().st_size == 0]
    assert not missing, f"FFT outputs missing or empty: {missing}"

    by_type: dict = {}
    for env in received:
        by_type.setdefault(env["type"], []).append(env)

    started = by_type.get("magellon.step.started", [])
    progress = by_type.get("magellon.step.progress", [])
    completed = by_type.get("magellon.step.completed", [])
    failed = by_type.get("magellon.step.failed", [])

    assert len(failed) == 0, f"unexpected failed events: {failed}"
    assert len(started) == 10
    assert len(completed) == 10
    assert len(progress) >= 20

    started_task_ids = {ev["data"]["task_id"] for ev in started}
    expected_task_ids = {str(t) for t in task_ids}
    assert started_task_ids == expected_task_ids

    for env in received:
        assert env["data"]["job_id"] == str(job_id), env

    completed_outputs = {
        ev["data"]["output_files"][0] for ev in completed if ev["data"].get("output_files")
    }
    expected_outputs = {str(p) for p in targets}
    assert completed_outputs == expected_outputs
