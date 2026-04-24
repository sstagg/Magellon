"""Unit tests for the ptolemy dispatch helpers.

Mocks the bus so we don't need RabbitMQ. Asserts the task envelope has
the right category code, carries a PtolemyTaskData shape, and gets
routed to the per-category subject.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from magellon_sdk.bus import get_bus
from magellon_sdk.models.tasks import HOLE_DETECTION, PtolemyTaskData, SQUARE_DETECTION


@pytest.fixture
def fake_bus():
    """Override the process-wide bus with a MagicMock and capture sends."""
    bus = MagicMock()
    bus.tasks.send.return_value = MagicMock(ok=True, error=None)
    get_bus.override(bus)
    # Reset the cached dispatcher registry so it re-reads get_bus()
    from core.dispatcher_registry import get_task_dispatcher_registry

    get_task_dispatcher_registry.cache_clear()
    yield bus
    get_bus.override(None)
    get_task_dispatcher_registry.cache_clear()


def _last_send(bus: MagicMock):
    assert bus.tasks.send.called, "bus.tasks.send was not called"
    route, envelope = bus.tasks.send.call_args.args
    return route, envelope


def test_square_dispatch_uses_correct_category_and_subject(fake_bus):
    from core.helper import dispatch_square_detection_task

    ok = dispatch_square_detection_task(
        image_path="/magellon/session/atlas.mrc",
        job_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        image_id=uuid.uuid4(),
    )
    assert ok is True

    route, envelope = _last_send(fake_bus)
    assert route.subject == "magellon.tasks.squaredetection"

    task = envelope.data
    assert task.type.code == SQUARE_DETECTION.code
    assert task.type.name == SQUARE_DETECTION.name

    # Validate the payload parses as PtolemyTaskData
    parsed = PtolemyTaskData.model_validate(task.data)
    assert parsed.input_file == "/magellon/session/atlas.mrc"
    assert parsed.image_path == "/magellon/session/atlas.mrc"
    assert parsed.image_name == "atlas"


def test_hole_dispatch_uses_correct_category_and_subject(fake_bus):
    from core.helper import dispatch_hole_detection_task

    ok = dispatch_hole_detection_task(
        image_path="/magellon/session/square17.mrc",
        session_name="24mar28a",
    )
    assert ok is True

    route, envelope = _last_send(fake_bus)
    assert route.subject == "magellon.tasks.holedetection"

    task = envelope.data
    assert task.type.code == HOLE_DETECTION.code
    assert task.type.name == HOLE_DETECTION.name
    assert task.session_name == "24mar28a"

    parsed = PtolemyTaskData.model_validate(task.data)
    assert parsed.input_file == "/magellon/session/square17.mrc"


def test_helpers_return_false_when_bus_send_fails(fake_bus):
    from core.helper import dispatch_square_detection_task

    fake_bus.tasks.send.return_value = MagicMock(
        ok=False, error="transport unavailable"
    )
    ok = dispatch_square_detection_task(
        image_path="/does/not/matter.mrc",
    )
    assert ok is False
