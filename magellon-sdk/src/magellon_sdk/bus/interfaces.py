"""MessageBus Protocols — the caller-facing surface (L2) and the
binder SPI (L3).

This module defines shape, not behavior. Concrete classes land in:

- ``magellon_sdk/bus/routes/`` — MB1.2 (route and pattern value objects)
- ``magellon_sdk/bus/binders/mock.py`` — MB1.3 (in-memory test binder)
- ``magellon_sdk/bus/binders/rmq/`` — MB2 (the RabbitMQ binder)

Design reference: ``Documentation/MESSAGE_BUS_SPEC_AND_PLAN.md`` §3
(four-layer architecture), §4 (bus API), §5 (binder SPI).
"""
from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Callable,
    ContextManager,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)

from magellon_sdk.bus.policy import (
    PublishReceipt,
    TaskConsumerPolicy,
)
from magellon_sdk.envelope import Envelope


# ---------------------------------------------------------------------------
# Route + pattern Protocols
# ---------------------------------------------------------------------------
# Concrete Route classes (TaskRoute, TaskResultRoute, StepEventRoute,
# HeartbeatRoute, AnnounceRoute, ConfigRoute) land in MB1.2 and each
# carries a ``subject: str`` — satisfying RouteRef structurally.
# Patterns wrap a glob (RMQ ``#`` / NATS ``>``) that the binder maps
# to its native wildcard syntax.

@runtime_checkable
class RouteRef(Protocol):
    """Anything carrying a broker-neutral subject string.

    MB1.2's concrete ``TaskRoute`` / ``EventRoute`` dataclasses
    satisfy this structurally.
    """

    subject: str


@runtime_checkable
class PatternRef(Protocol):
    """A subscription pattern. ``subject_glob`` uses ``*`` for a
    single segment and ``>`` for multi-segment tail (NATS style). The
    binder translates to its native syntax — ``*`` and ``#`` on RMQ
    topic exchanges, unchanged on NATS.
    """

    subject_glob: str


# ---------------------------------------------------------------------------
# Handler signatures
# ---------------------------------------------------------------------------
# Task handlers return either an Envelope (which the binder publishes
# to the result route) or None (ack-only). Async handlers allowed —
# binder handles the sync/async boundary.
#
# Event handlers are fire-and-forget. Return value is ignored.

TaskHandler = Callable[[Envelope], Union[Optional[Envelope], Awaitable[Optional[Envelope]]]]
EventHandler = Callable[[Envelope], Union[None, Awaitable[None]]]


# ---------------------------------------------------------------------------
# Handles — returned from registration, closable
# ---------------------------------------------------------------------------

@runtime_checkable
class ConsumerHandle(Protocol):
    """Handle to a registered ``bus.tasks.consumer``.

    Returned from imperative registration::

        handle = bus.tasks.consumer(route, handler, policy=...)
        try:
            handle.run_until_shutdown()
        finally:
            handle.close()

    The decorator form ``@bus.tasks.consumer(route)`` returns the
    handle too, though most callers never reference it — the runner
    or a context manager owns cleanup.
    """

    def close(self) -> None:
        """Unsubscribe and release resources. Safe to call twice."""
        ...

    def run_until_shutdown(self) -> None:
        """Block the calling thread until the binder is closed or a
        stop signal arrives. For runners that want a foreground loop."""
        ...


@runtime_checkable
class SubscriptionHandle(Protocol):
    """Handle to a ``bus.events.subscribe``. Events are fire-and-forget
    so no ``run_until_shutdown`` — the binder's consumer thread runs
    until the handle is closed."""

    def close(self) -> None:
        """Unsubscribe. Safe to call twice."""
        ...


# ---------------------------------------------------------------------------
# Bus Protocols (L2)
# ---------------------------------------------------------------------------

class TasksBus(Protocol):
    """Work-queue surface. Commands, durable, ack-required, DLQ-capable."""

    def send(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        """Publish a task envelope to ``route``. Returns non-blocking
        receipt; broker errors surface as ``ok=False``, not exceptions."""
        ...

    def consumer(
        self,
        route: RouteRef,
        handler: Optional[TaskHandler] = None,
        *,
        policy: Optional[TaskConsumerPolicy] = None,
    ) -> Any:
        """Register a task handler.

        Dual form (spec §4.2):

        - ``handler=None`` returns a decorator::

              @bus.tasks.consumer(route, policy=TaskConsumerPolicy(...))
              def handle(env): ...

        - ``handler`` set returns a :class:`ConsumerHandle`
          immediately — for bound methods on class-based services::

              self._handle = bus.tasks.consumer(route, self._handle_task)

        Handler semantics:
        - return ``Envelope`` → binder publishes to the result route
        - return ``None`` → ack only
        - raise → :func:`classify_exception` picks ACK / REQUEUE / DLQ
        """
        ...

    def purge(self, route: RouteRef) -> int:
        """Drain pending messages from ``route``. Returns the count
        drained. Operator primitive — used by cancellation endpoints."""
        ...


class EventsBus(Protocol):
    """Pub-sub surface. Fanout, fire-and-forget, N subscribers, no ack."""

    def publish(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        """Publish an event. Non-blocking; receipt indicates local
        accept, not delivery."""
        ...

    def subscribe(
        self,
        pattern: PatternRef,
        handler: Optional[EventHandler] = None,
    ) -> Any:
        """Register an event handler.

        Dual form, mirrors :meth:`TasksBus.consumer`:

        - ``handler=None`` returns a decorator.
        - ``handler`` set returns a :class:`SubscriptionHandle`.

        Handler is invoked once per delivery across all bindings
        matching ``pattern.subject_glob``.
        """
        ...


# ---------------------------------------------------------------------------
# Binder SPI (L3)
# ---------------------------------------------------------------------------

class Binder(Protocol):
    """One binder per transport per process (spec §5).

    Lifecycle:

    - :meth:`start` establishes the long-lived connection, declares
      exchanges + durable queues + DLQ topology, installs binder
      features (audit log, trace context).
    - :meth:`close` drains in-flight consumers and shuts the connection.
    - Reconnect is internal to the binder; callers never retry.

    The bus Protocols above are thin facades over these methods.
    """

    name: str

    def start(self) -> None:
        """Connect + declare topology. Safe to call once per process."""
        ...

    def close(self) -> None:
        """Release the connection. Safe to call twice."""
        ...

    # Work queue
    def publish_task(self, route: RouteRef, envelope: Envelope) -> PublishReceipt: ...
    def consume_tasks(
        self,
        route: RouteRef,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
    ) -> ConsumerHandle: ...
    def purge_tasks(self, route: RouteRef) -> int: ...

    # Events
    def publish_event(self, route: RouteRef, envelope: Envelope) -> PublishReceipt: ...
    def subscribe_events(
        self,
        pattern: PatternRef,
        handler: EventHandler,
    ) -> SubscriptionHandle: ...


# ---------------------------------------------------------------------------
# MessageBus facade (L2 composite)
# ---------------------------------------------------------------------------

class MessageBus(Protocol):
    """Composite surface: ``bus.tasks`` + ``bus.events`` + lifecycle.

    Constructed by :func:`get_bus` (lands in MB1.3) from process
    config. One instance per process; not a module-level singleton —
    see spec §4.1 on why.
    """

    tasks: TasksBus
    events: EventsBus

    def start(self) -> ContextManager[None]:
        """Start the underlying binder. Idempotent.

        Returns a context manager so callers can write::

            with get_bus().start():
                ...  # bus is live, binder connected

        or the imperative equivalent ``bus.start()`` / ``bus.close()``.
        """
        ...

    def close(self) -> None:
        """Stop the underlying binder. Safe to call twice."""
        ...


__all__ = [
    "Binder",
    "ConsumerHandle",
    "EventHandler",
    "EventsBus",
    "MessageBus",
    "PatternRef",
    "RouteRef",
    "SubscriptionHandle",
    "TaskHandler",
    "TasksBus",
]
