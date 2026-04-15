"""Shape + room tests for :func:`core.socketio_server.emit_step_event`.

We intercept ``sio.emit`` on the real async server so we can assert the
event name, room, and payload keys without spinning up a network
listener. Goal: lock the wire shape the frontend binds to.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from magellon_sdk.envelope import Envelope
from magellon_sdk.events import STEP_COMPLETED, STEP_PROGRESS


@pytest.fixture()
def captured_emits(monkeypatch):
    """Replace ``sio.emit`` with a recorder."""
    from core import socketio_server as mod

    calls = []

    async def _capture(event_name, payload, room=None, **kw):
        calls.append({"event": event_name, "payload": payload, "room": room})

    monkeypatch.setattr(mod.sio, "emit", _capture)
    return calls


@pytest.mark.asyncio
async def test_emit_step_event_targets_job_room(captured_emits):
    from core.socketio_server import emit_step_event

    job_id = uuid4()
    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type=STEP_COMPLETED,
        subject=f"magellon.job.{job_id}.step.ctf",
        data={"job_id": str(job_id), "step": "ctf", "task_id": None},
    )

    await emit_step_event(env)

    assert len(captured_emits) == 1
    call = captured_emits[0]
    assert call["event"] == "step_event"
    assert call["room"] == f"job:{job_id}"
    payload = call["payload"]
    assert payload["id"] == env.id
    assert payload["type"] == STEP_COMPLETED
    assert payload["subject"] == env.subject
    assert payload["data"]["step"] == "ctf"


@pytest.mark.asyncio
async def test_emit_step_event_forwards_progress_events(captured_emits):
    """Progress events are live-only in the DB but must still reach
    the room — that's the whole point of Socket.IO forwarding."""
    from core.socketio_server import emit_step_event

    job_id = uuid4()
    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type=STEP_PROGRESS,
        subject=f"magellon.job.{job_id}.step.ctf",
        data={"job_id": str(job_id), "step": "ctf", "percent": 42.0},
    )

    await emit_step_event(env)

    assert captured_emits[0]["event"] == "step_event"
    assert captured_emits[0]["room"] == f"job:{job_id}"
    assert captured_emits[0]["payload"]["data"]["percent"] == 42.0


@pytest.mark.asyncio
async def test_emit_step_event_drops_envelope_without_job_id(captured_emits):
    """No job_id in data → nothing to route to. Silently drop rather
    than broadcast to a bogus room."""
    from core.socketio_server import emit_step_event

    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type=STEP_COMPLETED,
        subject="magellon.job.x.step.ctf",
        data={"step": "ctf"},  # missing job_id
    )

    await emit_step_event(env)
    assert captured_emits == []
