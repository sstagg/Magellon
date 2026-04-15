"""Verify ``do_execute`` emits the right step events in the right order.

NATS is stubbed with a recorder so we can assert the sequence without
running a broker. The invariants locked down:

- started → completed on the happy path
- started → failed on exception (and do_execute still returns a dict,
  not raises — consumer callback expects that)
- no emits if publisher is disabled (opt-in flag off)
- emitter exceptions never break do_execute — observability must be
  best-effort
"""
from __future__ import annotations

from uuid import uuid4

import pytest


class RecordingPublisher:
    """Stands in for :class:`StepEventPublisher` — records every emit
    keyword-args list so tests can assert ordering + contents."""

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

    async def _get_publisher():
        return pub

    monkeypatch.setattr(step_events, "get_publisher", _get_publisher)
    # do_execute imports these names at module-load, so patch there too.
    from service import service as svc_mod

    monkeypatch.setattr(svc_mod, "get_publisher", _get_publisher)
    return pub


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_completed_on_success(
    recording_publisher, monkeypatch
):
    from service import service as svc_mod

    async def _fake_do_ctf(params):
        return None  # short-circuit: skip push_result_to_out_queue branch

    monkeypatch.setattr(svc_mod, "do_ctf", _fake_do_ctf)

    params = _task_dto()
    result = await svc_mod.do_execute(params)

    assert result == {"message": "CTF successfully executed"}
    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "completed"]
    for _, kw in recording_publisher.calls:
        assert kw["job_id"] == params.job_id
        assert kw["task_id"] == params.id
        assert kw["step"] == "ctf"


@pytest.mark.asyncio
async def test_do_execute_emits_started_then_failed_on_error(
    recording_publisher, monkeypatch
):
    from service import service as svc_mod

    async def _boom(params):
        raise RuntimeError("ctf crashed")

    monkeypatch.setattr(svc_mod, "do_ctf", _boom)

    params = _task_dto()
    result = await svc_mod.do_execute(params)

    assert result == {"error": "ctf crashed"}
    names = [c[0] for c in recording_publisher.calls]
    assert names == ["started", "failed"]
    assert recording_publisher.calls[1][1]["error"] == "ctf crashed"


@pytest.mark.asyncio
async def test_no_emits_when_publisher_disabled(monkeypatch):
    """Opt-in off → get_publisher returns None → no emits, and
    do_execute works exactly as it did before P3."""
    from service import service as svc_mod

    async def _no_pub():
        return None

    monkeypatch.setattr(svc_mod, "get_publisher", _no_pub)

    async def _fake_do_ctf(params):
        return None

    monkeypatch.setattr(svc_mod, "do_ctf", _fake_do_ctf)

    result = await svc_mod.do_execute(_task_dto())
    assert result == {"message": "CTF successfully executed"}


@pytest.mark.asyncio
async def test_emitter_failure_does_not_break_do_execute(monkeypatch):
    """A dead NATS connection during .started must not fail the task —
    observability is best-effort."""
    from service import service as svc_mod

    class BoomPublisher:
        async def started(self, **kw):
            raise RuntimeError("nats is down")

        async def completed(self, **kw):
            raise RuntimeError("nats is down")

        async def failed(self, **kw):
            raise RuntimeError("nats is down")

    async def _get_publisher():
        return BoomPublisher()

    monkeypatch.setattr(svc_mod, "get_publisher", _get_publisher)

    async def _fake_do_ctf(params):
        return None

    monkeypatch.setattr(svc_mod, "do_ctf", _fake_do_ctf)

    result = await svc_mod.do_execute(_task_dto())
    assert result == {"message": "CTF successfully executed"}


def _task_dto():
    # Import inside to avoid pulling SDK at collection time if unavailable.
    from magellon_sdk.models.tasks import TaskDto

    return TaskDto(id=uuid4(), job_id=uuid4(), data={})
