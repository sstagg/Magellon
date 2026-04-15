"""Characterization tests for Socket.IO emit payload shapes.

The React app consumes these events by name and by key. A silent change to
the payload keys breaks the live progress UI without any type-checker
warning — these tests close that gap.

We swap the Socket.IO server's ``emit`` for an async spy, invoke the
public helpers (``emit_job_update``, ``emit_log``), and assert the exact
event name, room, and payload keys.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from core import socketio_server
from core.socketio_server import emit_job_update, emit_log


class EmitSpy:
    """Records every `sio.emit(event, data, room=...)` call."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, event, data=None, *, room=None, **_):
        self.calls.append({"event": event, "data": data, "room": room})


@pytest.fixture
def spy(monkeypatch) -> EmitSpy:
    spy = EmitSpy()
    monkeypatch.setattr(socketio_server.sio, "emit", spy)
    return spy


@pytest.mark.characterization
@pytest.mark.asyncio
async def test_emit_job_update_unicast_shape(spy):
    job_data = {"job_id": "abc", "status": "running", "progress": 42}
    await emit_job_update("sid-xyz", job_data)

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["event"] == "job_update"
    assert call["room"] == "sid-xyz"
    assert call["data"] == job_data


@pytest.mark.characterization
@pytest.mark.asyncio
async def test_emit_job_update_broadcast_shape(spy):
    """When sid is None the frame broadcasts (no room keyword)."""
    job_data = {"job_id": "abc", "status": "completed"}
    await emit_job_update(None, job_data)

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["event"] == "job_update"
    assert call["room"] is None
    assert call["data"] == job_data


@pytest.mark.characterization
@pytest.mark.asyncio
async def test_emit_log_shape(spy):
    await emit_log("info", "ctf/ctffind", "fitting defocus")

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["event"] == "log_entry"
    # emit_log broadcasts — no room kwarg.
    assert call["room"] is None

    entry = call["data"]
    assert set(entry.keys()) == {"id", "timestamp", "level", "source", "message"}
    assert entry["level"] == "info"
    assert entry["source"] == "ctf/ctffind"
    assert entry["message"] == "fitting defocus"
    # timestamp is HH:MM:SS.
    assert len(entry["timestamp"].split(":")) == 3
    # id is prefixed "log-".
    assert entry["id"].startswith("log-")


@pytest.mark.characterization
@pytest.mark.asyncio
async def test_emit_log_swallows_client_errors(monkeypatch):
    """Target behaviour: emit_log must not raise if the broadcast fails.

    The plugin runtime calls emit_log from a background thread; an exception
    here would surface as an unhandled error in the run_coroutine_threadsafe
    future and leave the job in an inconsistent state.
    """
    async def boom(*a, **kw):
        raise RuntimeError("no clients")

    monkeypatch.setattr(socketio_server.sio, "emit", boom)
    # Must return cleanly.
    await emit_log("error", "plugin", "test")


@pytest.mark.characterization
@pytest.mark.asyncio
async def test_emit_job_update_swallows_errors(monkeypatch):
    async def boom(*a, **kw):
        raise RuntimeError("broken")

    monkeypatch.setattr(socketio_server.sio, "emit", boom)
    await emit_job_update("sid-x", {"job_id": "x"})


@pytest.mark.characterization
def test_socketio_server_event_surface():
    """The Socket.IO handler set should not shrink silently.

    React code subscribes to these exact event names; removing one breaks
    the UI without a typecheck failure.
    """
    expected_emitted_events = {
        "server_message",    # connect welcome
        "pong",              # ping response
        "job_progress",      # demo simulation
        "server_broadcast",  # broadcast demo
        "log_entry",         # emit_log
        "job_update",        # emit_job_update
    }
    # Read the server module's source as the source of truth — socketio
    # doesn't expose a stable "list of emitted events" API.
    import inspect
    src = inspect.getsource(socketio_server)
    for event in expected_emitted_events:
        assert f"'{event}'" in src or f'"{event}"' in src, (
            f"Expected emitted event {event!r} not found in socketio_server.py"
        )
