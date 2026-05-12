"""Centerpiece e2e: install → lifecycle → dispatch → verify → uninstall.

The full Phase 0–4 arc in one narrative test:

  1. Install the FFT plugin from a .mpn archive (Phase 4 install pipeline,
     used with a local archive — Phase 4 hub path covered separately by
     test_install_from_hub_e2e.py).
  2. Verify the plugin reaches the running lifecycle state AND announces
     on the bus (BackendLifecycle status vs liveness registry — two
     independent signals that must both flip green).
  3. Exercise every lifecycle verb introduced in Phase 1+2:
        start / stop / restart / pause / unpause
     and confirm GET /admin/plugins/{id}/status reflects the expected
     state after each.
  4. Dispatch a single FFT task via the operator's batch endpoint.
  5. Observe the four step events (started, progress 25, progress 90,
     completed) over Socket.IO — the "progress events" half of the
     done-signal trio.
  6. Verify the output PNG exists on disk under MAGELLON_HOME_DIR — the
     "done file" half. FFT doesn't write a .done sentinel; the PNG IS
     the terminal artifact, signaled by magellon.step.completed.
  7. Verify the DB row reached status_id=2 (COMPLETED) — the third leg
     of the done signal.
  8. Uninstall and confirm the plugin is gone.

Gated on MAGELLON_E2E_STACK=up. Total budget ~3 minutes (most is install
cold-start; the task itself runs in seconds).
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List

import pytest

from tests.integration._e2e_helpers.install import (
    install_plugin_from_archive,
    uninstall_plugin,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


# Stage 6 (events) + Stage 7 (DB) are the slowest steps; budget covers
# the install cold-start which can hit ~60s when docker pulls a fresh
# base image.
INSTALL_TIMEOUT = 120.0
LIFECYCLE_TRANSITION_TIMEOUT = 30.0
DISPATCH_BUDGET = 60.0


# ---------------------------------------------------------------------------
# DB helpers — lifted from test_fft_full_stack_e2e for parity
# ---------------------------------------------------------------------------


def _db_engine(db_url: str):
    from sqlalchemy import create_engine
    if not hasattr(_db_engine, "_e"):
        _db_engine._e = create_engine(db_url, pool_pre_ping=True, future=True)
    return _db_engine._e


def _get_image_job(db_url: str, job_id: uuid.UUID):
    from sqlalchemy import text
    with _db_engine(db_url).connect() as conn:
        row = conn.execute(
            text(
                "SELECT BIN_TO_UUID(oid) AS oid, status_id, processed_json "
                "FROM image_job WHERE oid = UUID_TO_BIN(:jid)"
            ),
            {"jid": str(job_id)},
        ).mappings().first()
    return dict(row) if row else None


def _get_image_job_tasks(db_url: str, job_id: uuid.UUID) -> List[Dict]:
    from sqlalchemy import text
    with _db_engine(db_url).connect() as conn:
        rows = conn.execute(
            text(
                "SELECT BIN_TO_UUID(oid) AS oid, status_id "
                "FROM image_job_task WHERE job_id = UUID_TO_BIN(:jid) "
                "ORDER BY oid"
            ),
            {"jid": str(job_id)},
        ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_install_lifecycle_dispatch_full_arc(
    e2e_stack,
    admin_client,
    fft_mpn_archive,
    step_event_collector,
    tmp_path,
):
    """The full install → lifecycle → dispatch → done arc.

    Each section guards against the previous test's residue: if FFT is
    already installed from a prior run, we uninstall first so the
    install endpoint sees a clean slate. Same on the way out.
    """
    plugin_id = "fft"

    # ---- 1. Pre-condition: ensure FFT is NOT already installed -----------
    # A 409 ("already installed") on install would be a real failure;
    # uninstalling pre-emptively keeps the test re-runnable.
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        logger.info("FFT pre-installed from prior run — uninstalling first")
        uninstall_plugin(admin_client, plugin_id)
        # Give docker a moment to actually release the container name.
        time.sleep(2.0)

    # ---- 2. Install from local .mpn -------------------------------------
    install_body = install_plugin_from_archive(
        admin_client, fft_mpn_archive, timeout=INSTALL_TIMEOUT,
    )
    assert install_body["plugin_id"] == plugin_id
    assert install_body["install_method"] in ("uv", "docker"), install_body

    install_method = install_body["install_method"]
    expect_pause_support = install_method == "docker"

    # ---- 3. Wait for both readiness signals -----------------------------
    # Supervisor / lifecycle state — for docker installs this confirms
    # the container is running; for uv it confirms the supervisor sees
    # a tracked PID (UvLifecycle returns RUNNING when is_running is True).
    lifecycle_status = wait_for_lifecycle_status(
        admin_client, plugin_id, "running",
        timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )
    assert lifecycle_status["installed"] is True
    assert lifecycle_status["supports_pause"] == expect_pause_support, (
        f"supports_pause should be {expect_pause_support} for "
        f"install_method={install_method!r}, got {lifecycle_status!r}"
    )

    # Bus announce — independent of supervisor state. This is what the
    # React /plugins page reads for the Conditions chip cluster.
    conditions = wait_for_plugin_announce(
        admin_client, plugin_id, timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )
    live = next((c for c in conditions if c["type"] == "Live"), None)
    assert live is not None and live["status"] == "True", conditions

    # ---- 4. Lifecycle exercise ------------------------------------------
    # The order matters: pause requires running, restart leaves running,
    # stop ends in stopped, start brings us back to running for the
    # dispatch in section 5. Each verb asserts the post-state via
    # GET /admin/plugins/{id}/status (typed `status` field, Phase 2).

    if expect_pause_support:
        # Pause → docker container should be paused.
        resp = admin_client.post(f"/admin/plugins/{plugin_id}/pause")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "paused"
        wait_for_lifecycle_status(
            admin_client, plugin_id, "paused",
            timeout=LIFECYCLE_TRANSITION_TIMEOUT,
        )

        # Unpause → back to running.
        resp = admin_client.post(f"/admin/plugins/{plugin_id}/unpause")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "running"
        wait_for_lifecycle_status(
            admin_client, plugin_id, "running",
            timeout=LIFECYCLE_TRANSITION_TIMEOUT,
        )
    else:
        # uv install — pause should be refused with the docker-only message.
        resp = admin_client.post(f"/admin/plugins/{plugin_id}/pause")
        assert resp.status_code == 409, resp.text
        assert "docker-only" in resp.json()["detail"]

    # Restart — both backends. Native `docker restart` for docker;
    # stop+start through the supervisor for uv.
    resp = admin_client.post(f"/admin/plugins/{plugin_id}/restart")
    assert resp.status_code == 200, resp.text
    wait_for_lifecycle_status(
        admin_client, plugin_id, "running",
        timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )
    # Re-announce after restart can take a beat; wait for the bus side too.
    wait_for_plugin_announce(
        admin_client, plugin_id, timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )

    # Stop → status=stopped.
    resp = admin_client.post(f"/admin/plugins/{plugin_id}/stop")
    assert resp.status_code == 200, resp.text
    wait_for_lifecycle_status(
        admin_client, plugin_id, "stopped",
        timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )

    # Start → back to running (this is the state we need for the
    # dispatch in section 5).
    resp = admin_client.post(f"/admin/plugins/{plugin_id}/start")
    assert resp.status_code == 200, resp.text
    wait_for_lifecycle_status(
        admin_client, plugin_id, "running",
        timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )
    wait_for_plugin_announce(
        admin_client, plugin_id, timeout=LIFECYCLE_TRANSITION_TIMEOUT,
    )

    # ---- 5. Dispatch a single FFT task ----------------------------------
    # Use the existing batch endpoint with a single image so the test
    # exercises the operator's real dispatch path. The endpoint creates
    # ImageJob + ImageJobTask rows and publishes to fft_tasks_queue.
    run_id = uuid.uuid4().hex[:8]
    rel_dir = f"fft_install_e2e_{run_id}"
    host_dir = e2e_stack.gpfs_host_root / rel_dir
    host_dir.mkdir(parents=True, exist_ok=True)

    # Single deterministic input — matches generate_input_image's seed
    # but inlined to avoid a helper just for one image.
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed=42)
    arr = (rng.random((256, 256)) * 255).astype("uint8")
    img_path = host_dir / "sample.png"
    Image.fromarray(arr, mode="L").save(img_path)
    assert img_path.exists() and img_path.stat().st_size > 0

    dispatch_path = str(img_path).replace("\\", "/")
    job_id = uuid.uuid4()

    # ---- 6. Subscribe BEFORE dispatch -----------------------------------
    # Same race-avoidance trick as test_fft_full_stack_e2e.py:241–290 —
    # if we connect after dispatch, a fast plugin can fire `started`
    # before our subscriber is in the room, and Socket.IO doesn't
    # replay missed emits.
    with step_event_collector(
        job_id, until_completed=1, timeout=DISPATCH_BUDGET,
    ) as events:
        dispatch_resp = admin_client.post(
            "/image/fft/batch_dispatch",
            json={
                "image_paths": [dispatch_path],
                "job_id": str(job_id),
                "name": f"install_e2e {run_id}",
            },
            timeout=30.0,
        )
        assert dispatch_resp.status_code == 200, (
            f"batch_dispatch failed: {dispatch_resp.status_code} "
            f"{dispatch_resp.text[:400]}"
        )
        dispatch_body = dispatch_resp.json()
        assert dispatch_body["job_id"] == str(job_id)
        assert len(dispatch_body["task_ids"]) == 1

    # ---- 7. Assert the event sequence -----------------------------------
    by_type: dict = {}
    for env in events:
        by_type.setdefault(env.get("type"), []).append(env)

    started = by_type.get("magellon.step.started", [])
    progress = by_type.get("magellon.step.progress", [])
    completed = by_type.get("magellon.step.completed", [])
    failed = by_type.get("magellon.step.failed", [])

    assert len(failed) == 0, f"unexpected failed events: {failed}"
    assert len(started) == 1, f"started={len(started)} types={list(by_type)}"
    assert len(completed) == 1, f"completed={len(completed)} types={list(by_type)}"
    # FFT emits progress at 25% (loading) + 90% (writing). Lower bound 2.
    assert len(progress) >= 2, (
        f"progress={len(progress)} (expected >= 2) types={list(by_type)}"
    )

    # All events belong to this job.
    for env in events:
        assert env["data"]["job_id"] == str(job_id), env

    # Completed envelope must name the output PNG.
    completed_data = completed[0]["data"]
    assert completed_data.get("output_files"), completed_data
    output_path_on_wire = completed_data["output_files"][0]
    assert output_path_on_wire.endswith("_FFT.png"), output_path_on_wire

    # ---- 8. Verify the "done file" exists on the host -------------------
    # task_output_processor moves the PNG to:
    #   MAGELLON_HOME_DIR/<session>/ffts/<image_stem>/<image_stem>_FFT.png
    # The batch endpoint doesn't take session_name, so the session
    # segment is empty — final layout is MAGELLON_HOME_DIR/ffts/<stem>/...
    image_stem = Path(dispatch_body["target_paths"][0]).stem.replace("_FFT", "")
    expected_host_path = (
        e2e_stack.magellon_home_root / "ffts" / image_stem
        / f"{image_stem}_FFT.png"
    )
    assert expected_host_path.exists(), (
        f"output PNG missing on host: {expected_host_path}\n"
        f"wire path was: {output_path_on_wire}\n"
        f"completed envelope: {completed_data}"
    )
    assert expected_host_path.stat().st_size > 0, (
        f"output PNG is empty: {expected_host_path}"
    )

    # ---- 9. Verify the DB row reached COMPLETED -------------------------
    # Allow a brief grace window — the projector runs in the forwarder's
    # downstream chain so it might lag the final completed envelope by a
    # commit boundary.
    deadline_db = time.monotonic() + 10.0
    job_row = None
    while time.monotonic() < deadline_db:
        job_row = _get_image_job(e2e_stack.db_url, job_id)
        if job_row and job_row.get("status_id") == 2:
            break
        time.sleep(0.5)
    assert job_row is not None, "ImageJob not persisted"
    assert job_row["status_id"] == 2, f"ImageJob did not reach COMPLETED: {job_row}"

    task_rows = _get_image_job_tasks(e2e_stack.db_url, job_id)
    assert len(task_rows) == 1, task_rows
    assert task_rows[0]["status_id"] == 2, task_rows[0]

    # ---- 10. Uninstall + verify cleanup ---------------------------------
    uninstall_plugin(admin_client, plugin_id)

    # GET /admin/plugins/{id}/status should report not installed.
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        resp = admin_client.get(f"/admin/plugins/{plugin_id}/status")
        if resp.status_code == 200 and not resp.json().get("installed"):
            break
        time.sleep(0.5)
    else:
        pytest.fail(
            f"FFT still reports installed after uninstall: "
            f"{resp.status_code} {resp.text[:200]}"
        )
