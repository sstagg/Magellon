"""Verify ``do_execute`` emits the right step events in the right order.

Mirror of the CTF plugin's wiring tests — the contract is the same
across plugins, so the tests are too. If you change one, change both.

Notable difference from CTF: motioncor's ``do_execute`` returns
``result`` directly when ``do_motioncor`` produces one (instead of a
fixed dict), and falls through to ``{"message": ...}`` only when the
work returned None. The completed emit must fire on both paths.
"""
from __future__ import annotations

import sys
import types
from uuid import uuid4

import pytest

# Stub cv2 — it's a heavy native dep that ``utils`` imports at module
# load but no event-emit code path actually calls into it. PIL,
# tifffile, matplotlib are real and available.
if "cv2" not in sys.modules:
    sys.modules["cv2"] = types.ModuleType("cv2")


class RecordingPublisher:
    def __init__(self):
        self.calls = []

    async def started(self, **kw):
        self.calls.append(("started", kw))

    async def completed(self, **kw):
        self.calls.append(("completed", kw))

    async def failed(self, **kw):
        self.calls.append(("failed", kw))


@pytest.fixture()
def recording_publisher(monkeypatch):
    pub = RecordingPublisher()
    from service import step_events
    from service import service as svc_mod

    async def _get_publisher():
        return pub

    monkeypatch.setattr(step_events, "get_publisher", _get_publisher)
    monkeypatch.setattr(svc_mod, "get_publisher", _get_publisher)
    return pub


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_completed_when_work_returns_result(
    recording_publisher, monkeypatch
):
    from service import service as svc_mod

    async def _fake_do_motioncor(params):
        return {"some": "result"}

    monkeypatch.setattr(svc_mod, "do_motioncor", _fake_do_motioncor)
    # push_result_to_out_queue would try to talk to RMQ; stub it.
    monkeypatch.setattr(svc_mod, "push_result_to_out_queue", lambda *_a, **_kw: None)

    params = _task_dto()
    result = await svc_mod.do_execute(params)

    assert result == {"some": "result"}
    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "completed"]
    for _, kw in recording_publisher.calls:
        assert kw["job_id"] == params.job_id
        assert kw["task_id"] == params.id
        assert kw["step"] == "motioncor"


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_completed_when_work_returns_none(
    recording_publisher, monkeypatch
):
    from service import service as svc_mod

    async def _fake_do_motioncor(params):
        return None

    monkeypatch.setattr(svc_mod, "do_motioncor", _fake_do_motioncor)

    result = await svc_mod.do_execute(_task_dto())

    assert result == {"message": "Motioncor successfully executed"}
    assert [c[0] for c in recording_publisher.calls] == ["started", "completed"]


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_failed_on_error(
    recording_publisher, monkeypatch
):
    from service import service as svc_mod

    async def _boom(params):
        raise RuntimeError("motioncor crashed")

    monkeypatch.setattr(svc_mod, "do_motioncor", _boom)

    result = await svc_mod.do_execute(_task_dto())

    assert result == {"error": "motioncor crashed"}
    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "failed"]
    assert recording_publisher.calls[1][1]["error"] == "motioncor crashed"


@pytest.mark.asyncio
async def test_no_emits_when_publisher_disabled(monkeypatch):
    from service import service as svc_mod

    async def _no_pub():
        return None

    monkeypatch.setattr(svc_mod, "get_publisher", _no_pub)

    async def _fake_do_motioncor(params):
        return None

    monkeypatch.setattr(svc_mod, "do_motioncor", _fake_do_motioncor)

    result = await svc_mod.do_execute(_task_dto())
    assert result == {"message": "Motioncor successfully executed"}


def _task_dto():
    from magellon_sdk.models.tasks import TaskDto

    return TaskDto(id=uuid4(), job_id=uuid4(), data={})
