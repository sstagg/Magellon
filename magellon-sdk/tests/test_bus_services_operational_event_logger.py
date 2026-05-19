from __future__ import annotations

import logging
from unittest.mock import MagicMock

from magellon_sdk.bus.routes.patterns import EventPattern
from magellon_sdk.bus.services.operational_event_logger import (
    OperationalEventLogger,
    start_operational_event_logger,
    summarize_event,
)
from magellon_sdk.envelope import Envelope


def _envelope() -> Envelope:
    return Envelope.wrap(
        source="plugin/ctf",
        type="magellon.step.completed",
        subject="job.job-1.step.ctf",
        data={"job_id": "job-1", "step": "ctf", "path": "/tmp/result.json"},
    )


def test_start_subscribes_to_operational_patterns():
    bus = MagicMock()
    service = OperationalEventLogger(bus)

    service.start()

    patterns = [c.args[0].subject_glob for c in bus.events.subscribe.call_args_list]
    handlers = [c.args[1] for c in bus.events.subscribe.call_args_list]
    assert patterns == ["magellon.plugins.>", "job.*.step.*"]
    assert all(h.__self__ is service for h in handlers)
    assert all(h.__func__ is service.handle.__func__ for h in handlers)


def test_start_is_idempotent():
    bus = MagicMock()
    service = OperationalEventLogger(bus)

    service.start()
    service.start()

    assert bus.events.subscribe.call_count == 2


def test_stop_closes_all_subscription_handles():
    bus = MagicMock()
    handle_a = MagicMock()
    handle_b = MagicMock()
    bus.events.subscribe.side_effect = [handle_a, handle_b]
    service = OperationalEventLogger(bus)
    service.start()

    service.stop()

    handle_a.close.assert_called_once()
    handle_b.close.assert_called_once()


def test_can_be_started_with_custom_patterns():
    bus = MagicMock()

    start_operational_event_logger(
        bus=bus,
        patterns=[EventPattern("magellon.plugins.heartbeat.>")],
    )

    pattern = bus.events.subscribe.call_args.args[0]
    assert pattern.subject_glob == "magellon.plugins.heartbeat.>"


def test_summarize_event_keeps_payload_out_of_logs():
    record = summarize_event(_envelope())

    assert record.event_type == "magellon.step.completed"
    assert record.subject == "job.job-1.step.ctf"
    assert record.source == "plugin/ctf"
    assert record.data_summary == "dict:job_id,path,step"


def test_handle_writes_concise_operational_log(caplog):
    log = logging.getLogger("test.operational.events")
    service = OperationalEventLogger(MagicMock(), log=log)

    with caplog.at_level(logging.INFO, logger=log.name):
        service.handle(_envelope())

    assert "bus.event id=" in caplog.text
    assert "type=magellon.step.completed" in caplog.text
    assert "subject=job.job-1.step.ctf" in caplog.text
    assert "data=dict:job_id,path,step" in caplog.text
    assert "/tmp/result.json" not in caplog.text
