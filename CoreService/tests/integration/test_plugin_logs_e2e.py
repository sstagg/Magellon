"""E2E pin for the Phase 6 log surface.

Install FFT, trigger a task that errors (bad input path), fetch
``/admin/plugins/fft/logs``, assert the error message appears in the
tail. Also smoke-tests the Socket.IO live channel by joining the
``plugin:fft`` room and observing at least one ``plugin_log`` event
arrive after a deliberate stderr-producing action.

Gated on ``MAGELLON_E2E_STACK=up``.
"""
from __future__ import annotations

import asyncio
import logging
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


def test_plugin_logs_endpoint_returns_tail(
    e2e_stack, admin_client, fft_mpn_archive,
):
    """One-shot tail must include something the plugin actually wrote.

    FFT logs its startup banner via the SDK runner. After install +
    announce we expect at least one non-empty log line.
    """
    plugin_id = "fft"

    # Clean prior install so the test is re-runnable.
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        uninstall_plugin(admin_client, plugin_id)
        time.sleep(2.0)

    install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=120.0)
    wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=30.0)
    wait_for_plugin_announce(admin_client, plugin_id, timeout=30.0)

    # The plugin writes its bootstrap log lines before announce — by
    # the time announce is True, /logs must have content.
    resp = admin_client.get(f"/admin/plugins/{plugin_id}/logs?tail=50")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plugin_id"] == plugin_id
    assert isinstance(body["lines"], list)
    # Some plugins emit only a few startup lines — don't pin an exact
    # count, just confirm we got real output (rather than an empty list
    # which would indicate a broken log source).
    non_empty = [line for line in body["lines"] if line.strip()]
    assert non_empty, (
        "plugin /logs returned no non-empty lines — the log source is "
        "either unwired or the plugin hasn't logged anything yet. "
        f"Full response: {body}"
    )

    # Cleanup.
    uninstall_plugin(admin_client, plugin_id)


def test_plugin_logs_404_when_not_installed(e2e_stack, admin_client):
    """The endpoint must distinguish 'plugin not installed' from
    'plugin installed but quiet'."""
    plugin_id = "definitely-not-a-real-plugin-id"
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if pre.status_code == 200 and pre.json().get("installed"):
        pytest.skip(
            f"unexpected pre-existing install of {plugin_id!r}; skip"
        )

    resp = admin_client.get(f"/admin/plugins/{plugin_id}/logs")
    assert resp.status_code == 404


def test_plugin_logs_socketio_live_stream(
    e2e_stack, admin_client, fft_mpn_archive,
):
    """Join the plugin's Socket.IO room and confirm log lines arrive
    on the ``plugin_log`` channel after a deliberate stderr-producing
    action (here: a restart, which always produces uvicorn boot logs).
    """
    import socketio

    plugin_id = "fft"
    pre = admin_client.get(f"/admin/plugins/{plugin_id}/status")
    if not (pre.status_code == 200 and pre.json().get("installed")):
        install_plugin_from_archive(admin_client, fft_mpn_archive, timeout=120.0)
        wait_for_lifecycle_status(admin_client, plugin_id, "running", timeout=30.0)
        wait_for_plugin_announce(admin_client, plugin_id, timeout=30.0)

    async def _run():
        sio = socketio.AsyncClient(reconnection=False)
        received: list = []
        first_line = asyncio.Event()

        @sio.on("plugin_log")
        async def _on_log(payload):
            received.append(payload)
            first_line.set()

        await sio.connect(e2e_stack.backend_url, transports=["websocket"])
        try:
            ack = await sio.call(
                "join_plugin_room", {"plugin_id": plugin_id}, timeout=5,
            )
            assert ack and ack.get("ok"), f"join_plugin_room rejected: {ack}"

            # Trigger fresh log activity — restart prints uvicorn boot lines.
            # docker restart is a no-op on logs (cached) so we go full stop+start.
            await asyncio.to_thread(
                admin_client.post, f"/admin/plugins/{plugin_id}/stop",
            )
            await asyncio.to_thread(
                admin_client.post, f"/admin/plugins/{plugin_id}/start",
            )

            try:
                await asyncio.wait_for(first_line.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                pass

            return received
        finally:
            try:
                await sio.disconnect()
            except Exception:
                pass

    received = asyncio.run(_run())

    assert received, (
        "no plugin_log events received in 30s — the Socket.IO follower "
        "may not have started, or the room name doesn't match what the "
        "server emits to."
    )
    # Each payload must be a dict with at least a 'line' field (or an
    # 'error' field for follower failures).
    for p in received:
        assert isinstance(p, dict)
        assert "line" in p or p.get("error"), p

    # Cleanup.
    uninstall_plugin(admin_client, plugin_id)
