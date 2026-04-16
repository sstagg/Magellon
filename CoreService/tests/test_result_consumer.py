"""Tests for the in-process result-consumer wiring (P3 + MB4.5).

Post-MB4.5 the consumer runs behind the MessageBus — the direct
``RabbitmqClient`` loop + pika-shaped callback are gone. These tests
pin the remaining behavior:

- ``_make_handler`` returns an envelope handler that decodes the
  result, hands it to ``TaskOutputProcessor``, and raises on errors
  so the binder's classifier routes to DLQ.
- ``start_result_consumers`` registers one bus consumer per
  ``OUT_QUEUES`` entry and returns their handles.
- ``result_consumer_engine`` (legacy shim) stays dormant when
  ``OUT_QUEUES`` is empty.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

import core.result_consumer as rc
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError


def _valid_envelope() -> Envelope:
    """Smallest envelope whose ``.data`` round-trips into a TaskResultDto.

    The processor is mocked so the contents don't have to satisfy any
    business rule beyond passing Pydantic validation."""
    from models.plugins_models import TaskResultDto

    dto = TaskResultDto(
        task_id=uuid4(),
        image_id=uuid4(),
        code=200,
        message="ok",
    )
    return Envelope.wrap(
        source="test", type="magellon.task.result",
        subject="ctf_out_tasks_queue", data=dto.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# _make_handler
# ---------------------------------------------------------------------------

def test_handler_invokes_processor_on_successful_decode():
    """Happy path: envelope decodes → TaskOutputProcessor.process runs
    on a fresh session → handler returns None (binder acks)."""
    factory = MagicMock()
    handler = rc._make_handler(factory)

    with patch.object(rc, "TaskOutputProcessor") as mock_proc_cls:
        mock_proc_cls.return_value.process.return_value = {"message": "ok"}
        result = handler(_valid_envelope())

    assert result is None
    factory.assert_called_once()  # one fresh session per delivery
    mock_proc_cls.return_value.process.assert_called_once()


def test_handler_raises_permanent_error_on_undecodable_payload():
    """Garbage in → PermanentError so classify_exception routes to DLQ.
    Requeuing a poison message would loop the consumer forever."""
    factory = MagicMock()
    handler = rc._make_handler(factory)

    bad_envelope = Envelope.wrap(
        source="test", type="x", subject="y",
        data={"task_id": "not-a-uuid", "code": "not-an-int"},
    )

    with pytest.raises(PermanentError, match="undecodable TaskResultDto"):
        handler(bad_envelope)

    # No session opened — we failed before reaching the processor.
    factory.assert_not_called()


def test_handler_raises_permanent_error_when_processor_fails():
    """Processor exception → PermanentError so classify routes to DLQ.
    The processor's own try/except has already attempted the FAILED-
    state best-effort write; the bus just needs to clear the message."""
    factory = MagicMock()
    handler = rc._make_handler(factory)

    with patch.object(rc, "TaskOutputProcessor") as mock_proc_cls:
        mock_proc_cls.return_value.process.side_effect = RuntimeError("boom")
        with pytest.raises(PermanentError, match="processor failed"):
            handler(_valid_envelope())


# ---------------------------------------------------------------------------
# start_result_consumers + engine dormancy
# ---------------------------------------------------------------------------

def test_start_result_consumers_registers_one_per_out_queue(monkeypatch):
    """Each OUT_QUEUES entry becomes a bus consumer on a TaskRoute
    named for the legacy queue name (MB3's legacy_queue_map path)."""
    fake_out_queues = [
        MagicMock(name="ctf_out_tasks_queue"),
        MagicMock(name="motioncor_out_tasks_queue"),
    ]
    fake_out_queues[0].name = "ctf_out_tasks_queue"
    fake_out_queues[1].name = "motioncor_out_tasks_queue"
    monkeypatch.setattr(
        rc.app_settings.rabbitmq_settings, "OUT_QUEUES", fake_out_queues
    )

    mock_bus = MagicMock()
    mock_bus.tasks.consumer.return_value = MagicMock()
    with patch.object(rc, "get_bus", return_value=mock_bus):
        handles = rc.start_result_consumers(session_factory=MagicMock())

    assert len(handles) == 2
    assert mock_bus.tasks.consumer.call_count == 2
    registered_subjects = [
        call.args[0].subject for call in mock_bus.tasks.consumer.call_args_list
    ]
    assert registered_subjects == [
        "ctf_out_tasks_queue", "motioncor_out_tasks_queue",
    ]


def test_engine_stays_dormant_when_no_out_queues_configured(monkeypatch):
    """Empty OUT_QUEUES = no consumer started. This is the safety
    valve for deployments that haven't migrated off the legacy plugin
    yet — starting both would consume the same queue twice."""
    monkeypatch.setattr(rc.app_settings.rabbitmq_settings, "OUT_QUEUES", [])

    with patch.object(rc, "get_bus") as mock_get_bus:
        rc.result_consumer_engine(session_factory=MagicMock())

    mock_get_bus.assert_not_called()
