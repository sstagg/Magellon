"""Helpers for dispatching FFT tasks at the e2e seam.

The centerpiece test wants to round-trip a single FFT task (not the
batch path the existing ``test_fft_full_stack_e2e.py`` uses) so we can
observe each step event individually and verify the "done" file. This
module builds the right ``TaskMessage`` and publishes it to RMQ.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict


# FFT task category code from ``magellon_sdk.models.tasks.FFT_TASK``.
# Repeated here as a literal so this module doesn't need to import the
# SDK at e2e-test-collection time (keeps unit-test collectors from
# pulling SDK dependencies).
_FFT_TASK_CODE = 5
_FFT_TASK_NAME = "fft"


def build_fft_task_message(
    *,
    job_id: uuid.UUID,
    task_id: uuid.UUID,
    image_path: str,
    target_path: str,
    image_id: uuid.UUID,
    image_name: str,
    session_name: str = "fft_e2e",
    height: int = 256,
) -> Dict:
    """Construct the JSON-encodable ``TaskMessage`` for a single FFT
    task. Used by both RMQ and HTTP dispatch paths.

    ``image_path``/``target_path`` are passed through the dispatch
    boundary canonicalizer (core.helper.to_canonical_gpfs_path) on the
    CoreService side, so callers can pass either canonical /gpfs/...
    paths or host paths under MAGELLON_GPFS_PATH and get equivalent
    behaviour.
    """
    return {
        "id": str(task_id),
        "session_name": session_name,
        "data": {
            "image_id": str(image_id),
            "image_name": image_name,
            "image_path": image_path,
            "target_path": target_path,
            "engine_opts": {"height": height},
        },
        "type": {
            "code": _FFT_TASK_CODE,
            "name": _FFT_TASK_NAME,
            "description": "FFT computation",
        },
        "status": {
            "code": 0,
            "name": "PENDING",
            "description": "Pending",
        },
        "job_id": str(job_id),
        # Subject axis (Phase 3, SDK 2.0+) — image-keyed task.
        "subject_kind": "image",
        "subject_id": str(image_id),
    }


def dispatch_fft_task_via_rmq(
    task_message: Dict, *, rmq_url: str, queue_name: str = "fft_tasks_queue",
) -> None:
    """Publish the task message to RMQ via the SDK's RabbitmqClient.

    Bypasses CoreService's HTTP surface — useful when the test wants to
    drive the bus directly (Test 1 dispatches via the HTTP path
    instead; Test 4 uses this one to inject a single slow task without
    a job-creation API).
    """
    # Imports inside the function so unit-test collectors that touch
    # this module don't drag in pika.
    from magellon_sdk.bus.transport.rabbitmq import RabbitmqClient
    from magellon_sdk.envelope import Envelope
    import json

    client = RabbitmqClient(url=rmq_url)
    try:
        client.connect()
        envelope = Envelope.wrap(
            type="magellon.task.fft",
            source="magellon/tests/e2e",
            subject=f"magellon.job.{task_message['job_id']}.task",
            data=task_message,
        )
        client.publish_message_to_queue(
            queue_name=queue_name,
            message=json.dumps(envelope.model_dump(mode="json")),
        )
    finally:
        try:
            client.close()
        except Exception:
            pass


def generate_input_image(host_dir: Path, *, name: str = "fft_e2e_input.png",
                         size: int = 256) -> Path:
    """Write a deterministic ``size × size`` greyscale PNG to disk.

    Matches the pattern in test_fft_full_stack_e2e.py — uses numpy
    noise rather than network-fetched images so the test runs offline.
    Returns the absolute path of the written file.
    """
    import numpy as np
    from PIL import Image

    host_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed=42)
    arr = (rng.random((size, size)) * 255).astype("uint8")
    path = host_dir / name
    Image.fromarray(arr, mode="L").save(path)
    return path
