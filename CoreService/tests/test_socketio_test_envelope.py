"""Shape + room tests for :func:`core.socketio_server.emit_test_envelope`.

The test panel binds to the ``plugin_test_envelope`` event in the
``job:{job_id}`` room. Lock that contract here.
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest


@pytest.fixture()
def captured_emits(monkeypatch):
    from core import socketio_server as mod

    calls = []

    async def _capture(event_name, payload, room=None, **kw):
        calls.append({"event": event_name, "payload": payload, "room": room})

    monkeypatch.setattr(mod.sio, "emit", _capture)
    return calls


@pytest.mark.asyncio
async def test_emit_test_envelope_outgoing_task(captured_emits):
    from core.socketio_server import emit_test_envelope

    job_id = uuid4()
    payload = {"job_id": str(job_id), "task_id": "tid-1", "type": {"code": 1}}

    await emit_test_envelope("out", "task", str(job_id), payload, queue="fft_tasks_queue")

    assert len(captured_emits) == 1
    call = captured_emits[0]
    assert call["event"] == "plugin_test_envelope"
    assert call["room"] == f"job:{job_id}"
    frame = call["payload"]
    assert frame["direction"] == "out"
    assert frame["kind"] == "task"
    assert frame["transport"] == "bus"
    assert frame["queue"] == "fft_tasks_queue"
    assert frame["payload"] == payload


@pytest.mark.asyncio
async def test_emit_test_envelope_incoming_result(captured_emits):
    from core.socketio_server import emit_test_envelope

    job_id = uuid4()
    payload = {"job_id": str(job_id), "task_id": "tid-1", "status": "ok"}

    await emit_test_envelope("in", "result", str(job_id), payload)

    assert len(captured_emits) == 1
    call = captured_emits[0]
    assert call["event"] == "plugin_test_envelope"
    assert call["room"] == f"job:{job_id}"
    frame = call["payload"]
    assert frame["direction"] == "in"
    assert frame["kind"] == "result"
    assert frame["transport"] == "bus"
    assert frame["queue"] is None


@pytest.mark.asyncio
async def test_emit_test_envelope_drops_without_job_id(captured_emits):
    from core.socketio_server import emit_test_envelope

    await emit_test_envelope("out", "task", None, {"foo": "bar"})

    assert captured_emits == []


@pytest.mark.asyncio
async def test_schedule_test_envelope_runs_on_captured_loop(captured_emits):
    """The sync wrapper schedules the coroutine on the asgi loop so it
    can be called from any thread. Verify it actually fires."""
    from core import socketio_server as mod

    mod.set_asgi_loop(asyncio.get_running_loop())
    try:
        job_id = uuid4()
        mod.schedule_test_envelope(
            "out", "task", str(job_id), {"job_id": str(job_id)},
        )
        # Give the scheduled coroutine a chance to run.
        await asyncio.sleep(0)
        # Drain pending tasks if any
        for _ in range(3):
            if captured_emits:
                break
            await asyncio.sleep(0.01)
        assert len(captured_emits) == 1
        assert captured_emits[0]["event"] == "plugin_test_envelope"
        assert captured_emits[0]["room"] == f"job:{job_id}"
    finally:
        mod.set_asgi_loop(None)


def test_schedule_test_envelope_noop_without_loop():
    """Outside the asgi runtime (e.g. early boot, import-time helpers)
    schedule_* must not raise."""
    from core import socketio_server as mod

    mod.set_asgi_loop(None)
    # Should not raise even with no captured loop.
    mod.schedule_test_envelope("out", "task", "job-1", {"x": 1})
