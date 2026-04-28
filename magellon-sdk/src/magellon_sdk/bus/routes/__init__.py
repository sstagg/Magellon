"""Route value objects — the typed surface that replaces magic
routing-key strings at call sites.

Every concrete route carries a ``subject: str`` that a binder
translates to its native form (RMQ routing key, NATS subject). For
category-scoped routes, the subject comes from
:class:`CategoryContract` — the single source of truth.

See ``Documentation/MESSAGE_BUS_SPEC.md`` §4.3.
"""
from magellon_sdk.bus.routes.event_route import (
    AnnounceRoute,
    ConfigRoute,
    HeartbeatRoute,
    StepEventRoute,
)
from magellon_sdk.bus.routes.patterns import EventPattern
from magellon_sdk.bus.routes.task_route import TaskResultRoute, TaskRoute

__all__ = [
    "AnnounceRoute",
    "ConfigRoute",
    "EventPattern",
    "HeartbeatRoute",
    "StepEventRoute",
    "TaskResultRoute",
    "TaskRoute",
]
