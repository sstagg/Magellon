"""Tests for the in-process result-consumer wiring (P3).

Focus: the broker callback's three branches — ack on success, DLQ on
JSON decode failure, DLQ on processor exception. The full DB write
path is covered by ``test_task_output_processor.py``; here we patch
``TaskOutputProcessor`` and assert the ack/nack contract.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

import core.result_consumer as rc


def _build_valid_body() -> bytes:
    """Smallest valid TaskResultDto JSON. The processor is mocked so
    the contents don't have to satisfy any business rule beyond passing
    Pydantic validation."""
    from models.plugins_models import TaskResultDto

    return TaskResultDto(
        task_id=uuid4(),
        image_id=uuid4(),
        code=200,
        message="ok",
    ).model_dump_json().encode("utf-8")


def _ch_method():
    """Stub of the (channel, method) tuple pika hands to callbacks."""
    ch = MagicMock()
    method = MagicMock()
    method.delivery_tag = 42
    return ch, method


def test_callback_acks_on_successful_processing():
    """Happy path: decode + process succeed → basic_ack with the
    delivery tag, no nack."""
    factory = MagicMock()
    cb = rc._make_callback(factory)
    ch, method = _ch_method()

    with patch.object(rc, "TaskOutputProcessor") as mock_proc_cls:
        mock_proc_cls.return_value.process.return_value = {"message": "ok"}
        cb(ch, method, properties=None, body=_build_valid_body())

    ch.basic_ack.assert_called_once_with(delivery_tag=42)
    ch.basic_nack.assert_not_called()
    factory.assert_called_once()  # one fresh session per delivery


def test_callback_dlqs_on_undecodable_body():
    """Garbage in → DLQ (basic_nack with requeue=False). Requeuing a
    poison message would loop the consumer forever."""
    factory = MagicMock()
    cb = rc._make_callback(factory)
    ch, method = _ch_method()

    cb(ch, method, properties=None, body=b"not json at all")

    ch.basic_ack.assert_not_called()
    ch.basic_nack.assert_called_once_with(delivery_tag=42, requeue=False)
    # No session opened — we failed before reaching the processor.
    factory.assert_not_called()


def test_callback_dlqs_when_processor_raises():
    """Processor exception → DLQ. The processor's own try/except has
    already attempted the FAILED-state best-effort write; the broker
    just needs to clear the message."""
    factory = MagicMock()
    cb = rc._make_callback(factory)
    ch, method = _ch_method()

    with patch.object(rc, "TaskOutputProcessor") as mock_proc_cls:
        mock_proc_cls.return_value.process.side_effect = RuntimeError("boom")
        cb(ch, method, properties=None, body=_build_valid_body())

    ch.basic_ack.assert_not_called()
    ch.basic_nack.assert_called_once_with(delivery_tag=42, requeue=False)


def test_engine_stays_dormant_when_no_out_queues_configured(monkeypatch):
    """Empty OUT_QUEUES = no consumer started. This is the safety valve
    for deployments that haven't migrated off the legacy plugin yet —
    starting both would consume the same queue twice."""
    monkeypatch.setattr(rc.app_settings.rabbitmq_settings, "OUT_QUEUES", [])

    with patch.object(rc, "RabbitmqClient") as mock_client_cls:
        rc.result_consumer_engine(session_factory=MagicMock())

    mock_client_cls.assert_not_called()
