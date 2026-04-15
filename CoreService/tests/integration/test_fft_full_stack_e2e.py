"""Full-stack FFT e2e: real docker-compose stack + Socket.IO subscriber.

Pipeline exercised
------------------

    test logs in as super -> POST /image/fft/dispatch x10
       -> backend publishes 10 TaskDtos onto fft_tasks_queue
          -> magellon_fft_plugin container drains, runs FFT, writes PNG
             -> emits started/progress/completed envelopes onto NATS
                -> backend's NATS->Socket.IO forwarder fans out to job:<uuid>
                   <- this test's socketio.AsyncClient reads them off the wire

Asserts:
- 10 ``magellon.step.started``, 10 ``magellon.step.completed``,
  >=20 ``magellon.step.progress``, 0 ``magellon.step.failed``.
- Each completed event names an output PNG that exists on the host
  filesystem (mounted into both backend and plugin via ``MAGELLON_GPFS_PATH``).

Skip rules
----------
Gated on ``MAGELLON_E2E_STACK=up`` so the test never runs accidentally
in a unit-test loop. Operator workflow:

    cd Docker && docker compose up -d
    set MAGELLON_E2E_STACK=up
    set MAGELLON_GPFS_HOST_PATH=c:\\magellon\\gpfs   # whatever .env points at
    pytest tests/integration/test_fft_full_stack_e2e.py -v

If ``MAGELLON_GPFS_HOST_PATH`` is unset we fall back to ``c:\\magellon\\gpfs``
which matches the value baked into ``Docker/.env``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import List

import pytest

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.integration_e2e

# 10 FFTs over a real socket fan-out — each task is sub-second on
# 256x256 images, so 90s gives ~80s of headroom for cold container
# RMQ reconnect / NATS handshake jitter.
TEST_BUDGET = 90.0

BACKEND_URL = os.environ.get("MAGELLON_BACKEND_URL", "http://127.0.0.1:8000")
SUPER_USER = os.environ.get("MAGELLON_E2E_USER", "super")
SUPER_PASS = os.environ.get("MAGELLON_E2E_PASS", "behd1d2")


def _stack_up() -> bool:
    return os.environ.get("MAGELLON_E2E_STACK", "").lower() in {"1", "up", "true", "yes"}


pytestmark = [
    pytest.mark.integration_e2e,
    pytest.mark.skipif(
        not _stack_up(),
        reason="MAGELLON_E2E_STACK!=up — start `docker compose up -d` first",
    ),
]


def _gpfs_host_root() -> Path:
    """Host path that compose mounts at ``/gpfs`` inside containers.

    Defaults to the value baked into Docker/.env so a fresh checkout
    'just works' on Windows. Override via env when the operator's
    .env points elsewhere.
    """
    raw = os.environ.get("MAGELLON_GPFS_HOST_PATH", r"c:\magellon\gpfs")
    return Path(raw)


def _generate_input_images(host_dir: Path, count: int) -> List[Path]:
    """Write ``count`` 256x256 PNGs into ``host_dir``. Picsum if reachable,
    deterministic numpy noise otherwise — FFT path doesn't care."""
    host_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Path] = []

    try:
        import requests as _rq
    except Exception:
        _rq = None

    for i in range(count):
        out = host_dir / f"sample_{i:02d}.png"
        wrote = False
        if _rq is not None:
            try:
                r = _rq.get(f"https://picsum.photos/seed/fft-stack-{i}/256/256", timeout=5)
                if r.status_code == 200 and r.content:
                    out.write_bytes(r.content)
                    wrote = True
            except Exception:
                wrote = False
        if not wrote:
            import numpy as np
            from PIL import Image

            rng = np.random.default_rng(seed=400 + i)
            arr = (rng.random((256, 256)) * 255).astype("uint8")
            Image.fromarray(arr, mode="L").save(out)
        paths.append(out)
    return paths


def _login() -> str:
    """POST /auth/login — return the bearer token."""
    import requests

    resp = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"username": SUPER_USER, "password": SUPER_PASS},
        timeout=10,
    )
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text[:300]}"
    body = resp.json()
    token = body.get("access_token")
    assert token, f"no access_token in login response: {body}"
    return token


def _dispatch_one(token: str, image_path_in_container: str, job_id: uuid.UUID) -> dict:
    """POST /image/fft/dispatch — returns the response body (job_id, task_id, ...)."""
    import requests

    resp = requests.post(
        f"{BACKEND_URL}/image/fft/dispatch",
        json={"image_path": image_path_in_container, "job_id": str(job_id)},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert resp.status_code == 200, f"dispatch failed: {resp.status_code} {resp.text[:300]}"
    return resp.json()


async def _drain_socketio_events(job_id: uuid.UUID, expected_completed: int,
                                 deadline: float) -> List[dict]:
    """Connect to the backend's Socket.IO server, join job:<id>, collect
    ``step_event`` payloads until ``expected_completed`` completed events
    arrive or wall-clock ``deadline`` elapses."""
    import socketio

    received: List[dict] = []
    completed = 0
    done = asyncio.Event()

    sio = socketio.AsyncClient(reconnection=False, logger=False, engineio_logger=False)

    @sio.on("step_event")
    async def _on_step(payload):
        nonlocal completed
        received.append(payload)
        if payload.get("type") == "magellon.step.completed":
            completed += 1
            if completed >= expected_completed:
                done.set()

    await sio.connect(BACKEND_URL, transports=["websocket"])
    try:
        ack = await sio.call("join_job_room", {"job_id": str(job_id)}, timeout=5)
        assert ack and ack.get("ok"), f"join_job_room rejected: {ack}"

        try:
            remaining = max(0.5, deadline - time.monotonic())
            await asyncio.wait_for(done.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            pass
    finally:
        try:
            await sio.disconnect()
        except Exception:
            pass

    return received


def test_full_stack_dispatches_ten_ffts_and_streams_events(tmp_path):
    gpfs_root = _gpfs_host_root()
    if not gpfs_root.exists():
        pytest.skip(f"GPFS host root {gpfs_root} not present — is the stack mounted?")

    run_id = uuid.uuid4().hex[:8]
    rel_dir = f"fft_e2e_{run_id}"
    host_dir = gpfs_root / rel_dir
    container_dir = f"/gpfs/{rel_dir}"  # how the plugin sees it

    images = _generate_input_images(host_dir, count=10)
    assert len(images) == 10
    for p in images:
        assert p.exists() and p.stat().st_size > 0

    token = _login()
    job_id = uuid.uuid4()

    expected_outputs_host: List[Path] = []
    expected_outputs_container = set()
    for img in images:
        in_container = f"{container_dir}/{img.name}"
        body = _dispatch_one(token, in_container, job_id)
        assert body["job_id"] == str(job_id)
        # Backend derives target_path = <dirname>/<stem>_FFT.png
        target = body["target_path"]
        expected_outputs_container.add(target)
        expected_outputs_host.append(host_dir / (Path(img).stem + "_FFT.png"))

    deadline = time.monotonic() + TEST_BUDGET
    events = asyncio.run(
        _drain_socketio_events(
            job_id=job_id,
            expected_completed=10,
            deadline=deadline,
        )
    )

    by_type: dict = {}
    for env in events:
        by_type.setdefault(env.get("type"), []).append(env)

    started = by_type.get("magellon.step.started", [])
    progress = by_type.get("magellon.step.progress", [])
    completed = by_type.get("magellon.step.completed", [])
    failed = by_type.get("magellon.step.failed", [])

    assert len(failed) == 0, f"unexpected failed events: {failed}"
    assert len(started) == 10, f"started count={len(started)} types={list(by_type)}"
    assert len(completed) == 10, f"completed count={len(completed)} types={list(by_type)}"
    assert len(progress) >= 20, f"progress count={len(progress)} types={list(by_type)}"

    # All events must belong to the dispatched job
    for env in events:
        assert env["data"]["job_id"] == str(job_id), env

    completed_outputs = {
        ev["data"]["output_files"][0]
        for ev in completed
        if ev["data"].get("output_files")
    }
    assert completed_outputs == expected_outputs_container, (
        f"completed outputs drift: missing={expected_outputs_container - completed_outputs}, "
        f"extra={completed_outputs - expected_outputs_container}"
    )

    missing_on_host = [p for p in expected_outputs_host if not p.exists() or p.stat().st_size == 0]
    assert not missing_on_host, f"FFT outputs missing on host: {missing_on_host}"
