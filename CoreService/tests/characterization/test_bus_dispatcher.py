"""MB3.1 — verify _BusTaskDispatcher dispatches tasks through the bus.

Pins the runtime contract that characterization tests alone don't
cover:

  - dispatch(task) wraps the TaskDto in a CloudEvents envelope
  - the envelope's ``data`` is the original task
  - the envelope's ``subject`` matches the route
  - ``bus.tasks.send`` is called on the overridden (mock) bus
  - the dispatcher propagates ``receipt.ok`` as its return value
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from core.dispatcher_registry import _BusTaskDispatcher
from magellon_sdk.bus import DefaultMessageBus, PublishReceipt, get_bus
from magellon_sdk.bus.binders.mock import MockBinder
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.categories.contract import CTF
from magellon_sdk.models import CTF_TASK, TaskDto


@pytest.fixture
def mock_bus():
    """Inject a mock bus for the duration of the test. Clean up after
    so subsequent tests don't inherit the override."""
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.override(bus)
    try:
        yield bus, binder
    finally:
        get_bus.reset()
        bus.close()


def _task() -> TaskDto:
    return TaskDto(
        id=uuid4(),
        job_id=uuid4(),
        type=CTF_TASK,
        data={"image_path": "/gpfs/x.mrc"},
    )


def test_dispatch_wraps_task_in_cloudevents_envelope(mock_bus):
    bus, binder = mock_bus
    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF), name="bus:ctf"
    )
    task = _task()

    ok = disp.dispatch(task)

    assert ok is True
    assert len(binder.published_tasks) == 1
    subject, envelope = binder.published_tasks[0]

    # Route subject matches the envelope subject + the wire address
    assert subject == "magellon.tasks.ctf"
    assert envelope.subject == "magellon.tasks.ctf"
    # CloudEvents envelope fields set by the dispatcher
    assert envelope.source == "magellon/core_service/dispatcher"
    assert envelope.type == "magellon.task.dispatch"
    # Task survives wrapping — handler on the other side gets it back
    assert envelope.data == task


def test_dispatch_returns_false_when_bus_reports_not_ok(mock_bus):
    """Publish failures shouldn't bubble as exceptions; the dispatcher
    returns False so callers (push_task_to_task_queue) can log and
    move on. Matches the legacy ``publish_message_to_queue`` contract."""
    bus, binder = mock_bus
    disp = _BusTaskDispatcher(
        route=TaskRoute.for_category(CTF), name="bus:ctf"
    )

    # Replace the mock binder's publish with one that fails
    def _fail(route, envelope):
        return PublishReceipt(ok=False, message_id=str(envelope.id), error="broker down")

    binder.publish_task = _fail

    ok = disp.dispatch(_task())
    assert ok is False
