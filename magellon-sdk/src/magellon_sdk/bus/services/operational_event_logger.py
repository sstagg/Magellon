"""Operational event tap for Magellon bus events.

This is intentionally a logging subscriber, not an event store. It uses
normal ``bus.events.subscribe`` semantics, so RabbitMQ creates anonymous
exclusive auto-delete queues for the process. If CoreService is down,
events are not retained here and no durable backlog is created.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional

from magellon_sdk.bus.interfaces import MessageBus, SubscriptionHandle
from magellon_sdk.bus.routes.event_route import StepEventRoute
from magellon_sdk.bus.routes.patterns import EventPattern
from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)


DEFAULT_OPERATIONAL_EVENT_PATTERNS = (
    EventPattern("magellon.plugins.>"),
    StepEventRoute.all(),
)


@dataclass(frozen=True)
class OperationalEventLogRecord:
    """Small, stable summary of one CloudEvent for log sinks."""

    event_id: str
    event_type: str
    subject: Optional[str]
    source: str
    data_summary: str


def _summarize_data(data: object, *, max_keys: int = 8) -> str:
    if isinstance(data, dict):
        keys = sorted(str(k) for k in data.keys())
        shown = keys[:max_keys]
        suffix = "" if len(keys) <= max_keys else f",+{len(keys) - max_keys}"
        return "dict:" + ",".join(shown) + suffix
    if isinstance(data, list):
        return f"list:{len(data)}"
    if data is None:
        return "none"
    return type(data).__name__


def summarize_event(envelope: Envelope) -> OperationalEventLogRecord:
    """Return the operator-facing event summary used by the logger."""

    return OperationalEventLogRecord(
        event_id=str(envelope.id),
        event_type=str(envelope.type),
        subject=envelope.subject,
        source=str(envelope.source),
        data_summary=_summarize_data(envelope.data),
    )


class OperationalEventLogger:
    """Ephemeral subscriber that writes concise operational event logs."""

    def __init__(
        self,
        bus: MessageBus,
        *,
        patterns: Iterable[EventPattern] = DEFAULT_OPERATIONAL_EVENT_PATTERNS,
        log: logging.Logger = logger,
    ) -> None:
        self._bus = bus
        self._patterns = tuple(patterns)
        self._log = log
        self._handles: list[SubscriptionHandle] = []

    def start(self) -> None:
        if self._handles:
            return
        self._handles = [
            self._bus.events.subscribe(pattern, self.handle)
            for pattern in self._patterns
        ]
        self._log.info(
            "OperationalEventLogger started: patterns=%s",
            ",".join(p.subject_glob for p in self._patterns),
        )

    def stop(self) -> None:
        handles = self._handles
        self._handles = []
        for handle in handles:
            try:
                handle.close()
            except Exception:
                self._log.exception("OperationalEventLogger: handle close failed")
        if handles:
            self._log.info("OperationalEventLogger stopped")

    def handle(self, envelope: Envelope) -> None:
        record = summarize_event(envelope)
        self._log.info(
            "bus.event id=%s type=%s subject=%s source=%s data=%s",
            record.event_id,
            record.event_type,
            record.subject,
            record.source,
            record.data_summary,
        )


def start_operational_event_logger(
    *,
    bus: MessageBus,
    patterns: Iterable[EventPattern] = DEFAULT_OPERATIONAL_EVENT_PATTERNS,
    log: logging.Logger = logger,
) -> OperationalEventLogger:
    """Create and start the operational event logger."""

    service = OperationalEventLogger(bus, patterns=patterns, log=log)
    service.start()
    return service


__all__ = [
    "DEFAULT_OPERATIONAL_EVENT_PATTERNS",
    "OperationalEventLogRecord",
    "OperationalEventLogger",
    "start_operational_event_logger",
    "summarize_event",
]
