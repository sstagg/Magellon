"""Policy and config value objects for the MessageBus.

Kept intentionally plain (dataclasses, no broker imports) so this
module can be imported by routes, binders, and callers without
pulling in ``pika`` or ``nats-py``.

See ``Documentation/MESSAGE_BUS_SPEC_AND_PLAN.md`` §4 (Bus API) and
§7 (Audit, observability, DLQ) for the motivating design.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class PublishReceipt:
    """Result of a ``bus.tasks.send`` or ``bus.events.publish``.

    Non-blocking observability: callers that care log the receipt;
    callers that don't discard it. Binders must return one even for
    fire-and-forget publishes — a local enqueue failure still wants to
    surface as ``ok=False`` so tests can assert.
    """

    ok: bool
    message_id: str
    error: Optional[str] = None


@dataclass(frozen=True)
class TaskConsumerPolicy:
    """Transport-portable knobs for ``bus.tasks.consumer``.

    Defaults preserve today's behavior (spec §4.2 notes):

    - ``prefetch=None`` — keep today's unlimited pika default. Callers
      opt into backpressure by passing ``prefetch=1`` explicitly.
      Flipping the default is a separate phase gated on benchmarks.
    - ``max_retries=3`` — matches the existing ``classify_exception``
      contract (REQUEUE until this count, then DLQ).
    - ``dlq_enabled=True`` — binder routes poison to DLQ. Existing
      production queues lack DLQ topology; MB6.4 migrates them.
    - ``concurrency=1`` — one handler invocation at a time per
      registration. Matches today's single-threaded pika callback.
    """

    prefetch: Optional[int] = None
    max_retries: int = 3
    dlq_enabled: bool = True
    concurrency: int = 1


@dataclass(frozen=True)
class AuditLogConfig:
    """Declarative binder-level audit configuration (spec §7.1).

    Audit is a binder built-in feature, not user-extensible
    middleware. The binder writes ``<root>/<subject>/messages.json``
    at publish time (before the broker call) — same trigger point and
    same file layout as today's
    ``CoreService/core/helper.py::publish_message_to_queue``.

    ``routes`` is a tuple of subject strings (not ``TaskRoute``
    objects) so this module stays import-light. Callers construct::

        AuditLogConfig(
            enabled=True,
            root="/magellon/messages",
            routes=(TaskRoute.for_category(CTF).subject, ...),
        )

    Default is disabled so plugin binders don't spam audit files;
    CoreService enables it at boot for the routes it originates.
    """

    enabled: bool = False
    root: str = "/magellon/messages"
    routes: Tuple[str, ...] = field(default_factory=tuple)

    def applies_to(self, subject: str) -> bool:
        """Is auditing enabled for this subject?"""
        return self.enabled and subject in self.routes


__all__ = [
    "AuditLogConfig",
    "PublishReceipt",
    "TaskConsumerPolicy",
]
