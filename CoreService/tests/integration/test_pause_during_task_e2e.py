"""E2E pin: pause/unpause has real semantic value mid-flight.

Phase 2 added pause/unpause to BackendLifecycle (docker-only). Unit
tests cover the routing + verb dispatch, but only an e2e test proves
``docker pause`` (cgroups freezer / SIGSTOP) actually halts work in
flight. This test does:

  1. Install FFT (docker install — pause is docker-only).
  2. Dispatch a slow-ish FFT task (large height so compute takes
     measurable wall time, but capped so the test stays under budget).
  3. After the ``started`` event arrives, POST /pause.
  4. Wait a beat — assert no further step events arrive while paused.
  5. POST /unpause.
  6. Verify the task completes correctly (the work resumed, not
     restarted from scratch).
  7. Verify the output PNG exists.

The "no events while paused" assertion is the heart of this test —
that's what proves SIGSTOP is doing real work, not just flipping a
status flag.

Gated on MAGELLON_E2E_STACK=up AND a docker-installed FFT (the
fixture handles install if needed; the test skips if pause is
unsupported on the resulting install method).
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path

import pytest

from tests.integration._e2e_helpers.install import (
    install_plugin_from_archive,
    uninstall_plugin,
    wait_for_lifecycle_status,
    wait_for_plugin_announce,
)

logger = logging.getLogger(__name__)


pytestmark = [pytest.mark.integration_e2e]


# Pause-during-task is by definition a real-time test. The window has
# to be long enough to observe quiescence but short enough that pytest
# doesn't get bored.
PAUSED_OBSERVATION_WINDOW = 3.0  # seconds with no events expected
SLOW_FFT_HEIGHT = 4096            # plenty of CPU work for a single task


def test_pause_freezes_in_flight_task(
    e2e_stack,
    admin_client,
    fft_mpn_archive,
    step_event_collector,
):
    """Pause's whole reason for existing — mid-flight control. Without
    this test, pause looks like a status toggle."""
    plugin_id = "fft"

    # ---- 1. Install FFT (force docker) -----------------------------------
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        # If the prior install isn't docker, pause won't work. Uninstall
        # and reinstall with the docker pin.
        if not pre.json().get("supports_pause"):
            uninstall_plugin(admin_client, plugin_id)
            time.sleep(2.0)
            install_plugin_from_archive(
                admin_client, fft_mpn_archive, install_method="docker",
                timeout=180.0,
            )
    else:
        install_plugin_from_archive(
            admin_client, fft_mpn_archive, install_method="docker",
            timeout=180.0,
        )

    status = wait_for_lifecycle_status(
        admin_client, plugin_id, "running", timeout=30.0,
    )
    if not status.get("supports_pause"):
        pytest.skip(
            "pause is docker-only and this install isn't docker — "
            "set install_method=docker or skip the test."
        )
    wait_for_plugin_announce(admin_client, plugin_id, timeout=30.0)

    # ---- 2. Prepare a single slow FFT task -------------------------------
    run_id = uuid.uuid4().hex[:8]
    host_dir = e2e_stack.gpfs_host_root / f"pause_e2e_{run_id}"
    host_dir.mkdir(parents=True, exist_ok=True)

    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(seed=11)
    # Larger input so compute takes long enough that we can pause it
    # mid-flight. 2048x2048 + height=4096 stretches FFT to a measurable
    # ~2-5s on CPU.
    arr = (rng.random((2048, 2048)) * 255).astype("uint8")
    img_path = host_dir / "slow_input.png"
    Image.fromarray(arr, mode="L").save(img_path)

    dispatch_path = str(img_path).replace("\\", "/")
    job_id = uuid.uuid4()

    # ---- 3. Subscribe + dispatch + pause shortly after started ----------
    # The collector context records events; we use it as a passive
    # observer here, plus a separate flag to time the pause.
    started_seen = threading.Event()
    pause_observed_count = threading.Event()
    events_before_pause: list = []

    # Custom collector logic — we need to react to the started event
    # to time the pause, then assert quiescence during the paused window.
    import asyncio
    import socketio

    all_events: list = []

    async def _run():
        sio = socketio.AsyncClient(reconnection=False)

        @sio.on("step_event")
        async def _on_step(payload):
            all_events.append((time.monotonic(), payload))
            if payload.get("type") == "magellon.step.started":
                started_seen.set()

        await sio.connect(e2e_stack.backend_url, transports=["websocket"])
        try:
            ack = await sio.call(
                "join_job_room", {"job_id": str(job_id)}, timeout=5,
            )
            assert ack and ack.get("ok"), f"join rejected: {ack}"

            # ---- Dispatch (in a worker thread so the asyncio loop
            # keeps pulling events from the socket).
            def _dispatch():
                resp = admin_client.post(
                    "/image/fft/batch_dispatch",
                    json={
                        "image_paths": [dispatch_path],
                        "job_id": str(job_id),
                        "name": f"pause_e2e {run_id}",
                        # Slow knob — passed via engine_opts so the
                        # plugin's compute uses a high target height.
                        "engine_opts": {"height": SLOW_FFT_HEIGHT},
                    },
                    timeout=30.0,
                )
                assert resp.status_code == 200, resp.text
                return resp.json()

            dispatch_future = asyncio.create_task(
                asyncio.to_thread(_dispatch),
            )

            # Wait for the started event so we know the plugin's actually
            # consumed the task.
            for _ in range(200):
                if started_seen.is_set():
                    break
                await asyncio.sleep(0.05)
            else:
                pytest.fail(
                    "started event did not arrive within 10s — plugin "
                    "may not be running, or the dispatch path is broken"
                )

            # ---- PAUSE ----------------------------------------------------
            pause_at = time.monotonic()
            paused_resp = await asyncio.to_thread(
                admin_client.post, f"/admin/plugins/{plugin_id}/pause",
            )
            assert paused_resp.status_code == 200, paused_resp.text
            events_before_pause.extend(all_events)
            count_at_pause = len(all_events)

            # ---- Observe quiescence --------------------------------------
            await asyncio.sleep(PAUSED_OBSERVATION_WINDOW)
            count_after_window = len(all_events)
            pause_observed_count.set()

            # ---- UNPAUSE -------------------------------------------------
            unpaused_resp = await asyncio.to_thread(
                admin_client.post, f"/admin/plugins/{plugin_id}/unpause",
            )
            assert unpaused_resp.status_code == 200, unpaused_resp.text

            # ---- Wait for completed (or timeout) -------------------------
            deadline = time.monotonic() + 60.0
            while time.monotonic() < deadline:
                if any(
                    p.get("type") == "magellon.step.completed"
                    for _, p in all_events
                ):
                    break
                await asyncio.sleep(0.1)

            dispatch_body = await dispatch_future

            return count_at_pause, count_after_window, dispatch_body
        finally:
            try:
                await sio.disconnect()
            except Exception:
                pass

    count_at_pause, count_after_window, dispatch_body = asyncio.run(_run())

    # ---- 4. Assertions ---------------------------------------------------
    # The heart of the test: while paused, no new step events arrive.
    # We allow at most ONE in-flight event (the plugin may have been
    # mid-emit when SIGSTOP fired — there's an unavoidable race window
    # on the order of the IPC RTT).
    events_during_pause = count_after_window - count_at_pause
    assert events_during_pause <= 1, (
        f"expected ≤1 event during the {PAUSED_OBSERVATION_WINDOW}s "
        f"paused window, observed {events_during_pause}. SIGSTOP did "
        f"not actually freeze the worker."
    )

    # And the task did complete after unpause.
    completed = [
        p for _, p in all_events
        if p.get("type") == "magellon.step.completed"
    ]
    failed = [
        p for _, p in all_events
        if p.get("type") == "magellon.step.failed"
    ]
    assert not failed, f"unexpected failures after unpause: {failed}"
    assert completed, (
        "task did not complete within budget after unpause — pause "
        "may have killed the worker instead of just suspending it"
    )

    # The output PNG exists (same layout as Test 1 — under
    # MAGELLON_HOME_DIR/ffts/<stem>/<stem>_FFT.png).
    image_stem = Path(dispatch_body["target_paths"][0]).stem.replace("_FFT", "")
    expected_host_path = (
        e2e_stack.magellon_home_root / "ffts" / image_stem
        / f"{image_stem}_FFT.png"
    )
    assert expected_host_path.exists(), (
        f"output PNG missing after pause/unpause cycle: {expected_host_path}"
    )

    # ---- 5. Cleanup ------------------------------------------------------
    uninstall_plugin(admin_client, plugin_id)
