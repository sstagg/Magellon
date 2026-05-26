"""Helpers for dispatching FFT tasks at the e2e seam.

The centerpiece test wants to round-trip a single FFT task (not the
batch path the existing ``test_fft_full_stack_e2e.py`` uses) so we can
observe each step event individually and verify the "done" file. This
module builds the right ``TaskMessage`` and publishes it to RMQ.
"""
from __future__ import annotations

import uuid
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Dict
from urllib.parse import unquote, urlparse


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
    from magellon_sdk.bus.binders.rmq._client import RabbitmqClient

    client = RabbitmqClient(_settings_from_rmq_url(rmq_url))
    try:
        client.connect()
        client.publish_message(json.dumps(task_message), queue_name=queue_name)
    finally:
        try:
            client.close_connection()
        except Exception:
            pass


def _settings_from_rmq_url(rmq_url: str):
    """Return the settings shape expected by SDK RabbitmqClient."""
    parsed = urlparse(rmq_url)
    host = parsed.hostname
    port = parsed.port or 5672
    username = unquote(parsed.username or "guest")
    password = unquote(parsed.password or "guest")
    virtual_host = None
    if host is not None and parsed.path and parsed.path != "/":
        virtual_host = unquote(parsed.path.lstrip("/"))

    if host is None:
        host_port = rmq_url.rsplit("@", 1)[-1].strip("/")
        host, _, port_text = host_port.partition(":")
        if port_text:
            port = int(port_text)

    return SimpleNamespace(
        HOST_NAME=host or "127.0.0.1",
        PORT=port,
        USER_NAME=username,
        PASSWORD=password,
        VIRTUAL_HOST=virtual_host,
        QUEUE_NAME="",
    )


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


def generate_test_micrograph_mrc(
    host_dir: Path, *,
    name: str = "test_micrograph.mrc",
    size: int = 1024,
    apix: float = 3.16,
    seed: int = 42,
) -> Path:
    """Write a deterministic ``size × size`` MRC micrograph for the
    template-picker e2e.

    Pure-noise data — the picker will run its cross-correlation pass
    over the configured templates and either find low-score peaks or
    nothing depending on threshold. That's exactly what we want for
    the retune-changes-counts assertion: at very low threshold the
    pick count is high; at very high threshold it's low or zero.
    """
    import numpy as np
    import mrcfile

    host_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed=seed)
    # Float32 in [0, 1] — matches MRC mode 2 (float32) which the
    # template-picker reads directly.
    data = rng.random((size, size)).astype("float32")

    path = host_dir / name
    with mrcfile.new(str(path), overwrite=True) as mrc:
        mrc.set_data(data)
        # Set apix on the MRC header so the picker's pixel-size
        # auto-derivation works if the operator omits it from
        # engine_opts.
        mrc.voxel_size = apix
    return path
