"""Full-stack FFT e2e: real docker-compose stack + DB + Socket.IO subscriber.

Pipeline exercised
------------------

    test logs in as super -> POST /image/fft/batch_dispatch (10 images)
       -> JobManager.create_job persists ImageJob + 10 ImageJobTask (QUEUED)
          -> backend publishes 10 TaskDtos onto fft_tasks_queue
             -> magellon_fft_plugin container drains, runs FFT, writes PNG
                -> emits started/progress/completed envelopes onto NATS+RMQ
                   -> backend's forwarder writes job_event rows AND
                      runs StepEventJobStateProjector to flip image_job /
                      image_job_task statuses, then fans out to Socket.IO
                      <- this test's socketio.AsyncClient reads them

Asserts the *whole* state machine, not just the wire events:

  Pre-dispatch  : no rows for our run_id
  Post-dispatch : ImageJob status=QUEUED(0), 10 ImageJobTask status=QUEUED(0)
  Post-events   : 10 magellon.step.started + 10 magellon.step.completed,
                  >=20 progress, 0 failed; all targeted at job_id
  Post-complete : ImageJob status=COMPLETED(2), processed_json.progress=100,
                  processed_json.completed_tasks length=10,
                  all 10 ImageJobTask status=COMPLETED(2),
                  exactly 20 job_event rows (started + completed; progress
                  is filtered at the writer by design)
  Filesystem    : every reported output PNG exists on the host

Skip rules
----------
Gated on ``MAGELLON_E2E_STACK=up`` so the test never runs accidentally
in a unit-test loop. Operator workflow:

    cd Docker && docker compose up -d
    set MAGELLON_E2E_STACK=up
    set MAGELLON_GPFS_HOST_PATH=c:\\magellon\\gpfs   # whatever .env points at
    pytest tests/integration/test_fft_full_stack_e2e.py -v

If ``MAGELLON_GPFS_HOST_PATH`` is unset we fall back to ``c:\\magellon\\gpfs``;
if ``MAGELLON_E2E_DB_URL`` is unset we fall back to root@127.0.0.1:3306 with
the password baked into Docker/.env.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

logger = logging.getLogger(__name__)

# 10 FFTs over a real socket fan-out — each task is sub-second on
# 256x256 images, so 90s gives ~80s of headroom for cold container
# RMQ reconnect / NATS handshake jitter.
TEST_BUDGET = 90.0

BACKEND_URL = os.environ.get("MAGELLON_BACKEND_URL", "http://127.0.0.1:8000")
SUPER_USER = os.environ.get("MAGELLON_E2E_USER", "super")
SUPER_PASS = os.environ.get("MAGELLON_E2E_PASS", "behd1d2")
DB_URL = os.environ.get(
    "MAGELLON_E2E_DB_URL",
    "mysql+pymysql://root:behd1d2@127.0.0.1:3306/magellon01",
)


pytestmark = [pytest.mark.integration_e2e]


def _gpfs_host_root() -> Path:
    """Host directory the FFT plugin reads inputs from and writes outputs to.

    In direct-run mode (no compose) the plugin process is on the host, so
    the ``image_path`` we dispatch with must be a real host path. Default
    ``C:/temp/magellon/gpfs`` matches the throwaway test layout; override
    via env when you point at a different scratch root.
    """
    raw = os.environ.get("MAGELLON_GPFS_HOST_PATH", r"C:\temp\magellon\gpfs")
    return Path(raw)


def _magellon_home_root() -> Path:
    """Where ``task_output_processor`` lands the projected PNGs.

    Mirrors ``MAGELLON_HOME_DIR`` from the running CoreService — the test
    has to know it to assert the file ended up where the projector put it.
    Default matches ``configs/app_settings_dev.yaml``.
    """
    raw = os.environ.get("MAGELLON_HOME_DIR", r"C:\magellon\home")
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


def _batch_dispatch(token: str, image_paths_in_container: List[str],
                    job_id: uuid.UUID, name: str) -> dict:
    """POST /image/fft/batch_dispatch — returns {job_id, task_ids, target_paths}."""
    import requests

    resp = requests.post(
        f"{BACKEND_URL}/image/fft/batch_dispatch",
        json={
            "image_paths": image_paths_in_container,
            "job_id": str(job_id),
            "name": name,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    assert resp.status_code == 200, f"batch_dispatch failed: {resp.status_code} {resp.text[:400]}"
    return resp.json()


# ---- DB helpers --------------------------------------------------------------

def _db_engine():
    """Lazy import + memoize — keeps unit-test collectors that import this
    module from also dragging in SQLAlchemy when the e2e stack isn't up."""
    if not hasattr(_db_engine, "_e"):
        from sqlalchemy import create_engine
        _db_engine._e = create_engine(DB_URL, pool_pre_ping=True, future=True)
    return _db_engine._e


def _get_image_job(job_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    from sqlalchemy import text

    with _db_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT BIN_TO_UUID(oid) AS oid, name, plugin_id, status_id, "
                "processed_json, start_date, end_date "
                "FROM image_job WHERE oid = UUID_TO_BIN(:jid)"
            ),
            {"jid": str(job_id)},
        ).mappings().first()
    return dict(row) if row else None


def _get_image_job_tasks(job_id: uuid.UUID) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    with _db_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT BIN_TO_UUID(oid) AS oid, status_id, processed_json "
                "FROM image_job_task WHERE job_id = UUID_TO_BIN(:jid) "
                "ORDER BY oid"
            ),
            {"jid": str(job_id)},
        ).mappings().all()
    return [dict(r) for r in rows]


def _get_job_events(job_id: uuid.UUID) -> List[Dict[str, Any]]:
    from sqlalchemy import text

    with _db_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT event_id, event_type, step, ts "
                "FROM job_event WHERE job_id = UUID_TO_BIN(:jid) "
                "ORDER BY ts"
            ),
            {"jid": str(job_id)},
        ).mappings().all()
    return [dict(r) for r in rows]


def _processed(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Tolerant unwrap: MySQL JSON columns surface as either dicts (when
    PyMySQL has json deserialization on) or strings. Tests don't care."""
    if not row:
        return {}
    raw = row.get("processed_json")
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw if isinstance(raw, dict) else {}
    import json
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ---- Socket.IO subscriber ----------------------------------------------------

async def _subscribe_dispatch_drain(job_id: uuid.UUID, expected_completed: int,
                                    deadline: float, dispatch_callable):
    """Join the job room *before* dispatching, then drain ``step_event``
    payloads until ``expected_completed`` completed events arrive or
    ``deadline`` elapses.

    The original shape connected after dispatch, which races the plugin —
    a fast plugin can fire ``started`` events before the subscriber is in
    the room, and Socket.IO doesn't replay missed emits. Subscribing
    first is the only way to make ``len(started) == 10`` deterministic.

    ``dispatch_callable`` is the blocking HTTP call; it runs in a worker
    thread so the Socket.IO event loop keeps draining incoming frames
    concurrently. Returns ``(events, dispatch_body)``.
    """
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

        dispatch_body = await asyncio.to_thread(dispatch_callable)

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

    return received, dispatch_body


# ---- the test ----------------------------------------------------------------

def test_full_stack_dispatches_ten_ffts_and_streams_events(tmp_path):
    gpfs_root = _gpfs_host_root()
    gpfs_root.mkdir(parents=True, exist_ok=True)

    run_id = uuid.uuid4().hex[:8]
    rel_dir = f"fft_e2e_{run_id}"
    host_dir = gpfs_root / rel_dir
    # Direct-run: backend, plugin, and test all share the host filesystem,
    # so the path we dispatch with is the same path the plugin opens. No
    # /gpfs/ container-prefix translation needed.
    dispatch_dir = str(host_dir).replace("\\", "/")

    images = _generate_input_images(host_dir, count=10)
    assert len(images) == 10
    for p in images:
        assert p.exists() and p.stat().st_size > 0

    token = _login()
    job_id = uuid.uuid4()

    # -- pre-dispatch: nothing in the DB for this job yet --------------------
    assert _get_image_job(job_id) is None
    assert _get_image_job_tasks(job_id) == []
    assert _get_job_events(job_id) == []

    # -- subscribe BEFORE dispatch so no early started events are missed -----
    in_container = [f"{dispatch_dir}/{img.name}" for img in images]

    def _do_dispatch():
        return _batch_dispatch(token, in_container, job_id, name=f"e2e {run_id}")

    deadline = time.monotonic() + TEST_BUDGET
    events, body = asyncio.run(
        _subscribe_dispatch_drain(
            job_id=job_id,
            expected_completed=10,
            deadline=deadline,
            dispatch_callable=_do_dispatch,
        )
    )

    assert body["job_id"] == str(job_id)
    assert len(body["task_ids"]) == 10
    expected_outputs_container = set(body["target_paths"])
    # task_output_processor moves each PNG from where the plugin wrote it
    # (sibling of the input) to MAGELLON_HOME_DIR/<session>/ffts/<stem>/.
    # No session_name in the dispatch payload, so the session segment is
    # empty: MAGELLON_HOME_DIR/ffts/<stem>/<stem>_FFT.png.
    home_root = _magellon_home_root()
    expected_outputs_host = [
        home_root / "ffts" / Path(img).stem / (Path(img).stem + "_FFT.png")
        for img in images
    ]

    # -- post-dispatch: JobManager has persisted everything --------
    # (state already advanced past QUEUED by the time events drained)
    job_row = _get_image_job(job_id)
    assert job_row is not None, "ImageJob not persisted by /fft/batch_dispatch"
    assert job_row["plugin_id"] == "magellon_fft_plugin"
    proc = _processed(job_row)
    assert proc.get("expected_tasks") == 10, proc

    task_rows = _get_image_job_tasks(job_id)
    assert len(task_rows) == 10, f"expected 10 tasks, got {len(task_rows)}"

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

    # -- post-completion: projector flipped DB state through to COMPLETED ----
    # The projector runs in the forwarder's downstream chain BEFORE Socket.IO
    # emit, so by the time we received the last completed envelope above the
    # DB row should already be settled. Allow a brief grace window for the
    # final commit + the second forwarder (RMQ) finishing its own write.
    deadline_db = time.monotonic() + 10.0
    while time.monotonic() < deadline_db:
        job_row = _get_image_job(job_id)
        if job_row and job_row["status_id"] == 2:
            break
        time.sleep(0.25)

    assert job_row is not None
    assert job_row["status_id"] == 2, (
        f"expected COMPLETED(2), got {job_row['status_id']} — "
        f"projector did not flip job state"
    )
    proc = _processed(job_row)
    assert proc.get("progress") == 100, proc
    completed_task_ids = proc.get("completed_tasks") or []
    assert len(completed_task_ids) == 10, (
        f"expected 10 completed_tasks recorded, got {len(completed_task_ids)}: {proc}"
    )

    task_rows = _get_image_job_tasks(job_id)
    assert len(task_rows) == 10
    bad = [r for r in task_rows if r["status_id"] != 2]
    assert not bad, f"non-COMPLETED tasks remain: {[(r['oid'], r['status_id']) for r in bad]}"

    # job_event log: exactly 20 lifecycle rows. Progress envelopes are
    # filtered at the writer (live-only). The same logical event arriving
    # via NATS *and* RMQ dedups on event_id, so we expect 10+10, not 40.
    event_rows = _get_job_events(job_id)
    by_event_type: Dict[str, List[Dict[str, Any]]] = {}
    for r in event_rows:
        by_event_type.setdefault(r["event_type"], []).append(r)

    assert "magellon.step.progress" not in by_event_type, (
        "progress events leaked into job_event — writer filter regressed"
    )
    assert len(by_event_type.get("magellon.step.started", [])) == 10, by_event_type
    assert len(by_event_type.get("magellon.step.completed", [])) == 10, by_event_type
    assert "magellon.step.failed" not in by_event_type, by_event_type
    assert len(event_rows) == 20, f"expected 20 lifecycle rows, got {len(event_rows)}"
