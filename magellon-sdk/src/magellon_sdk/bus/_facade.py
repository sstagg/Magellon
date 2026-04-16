"""Concrete :class:`MessageBus` facade over a :class:`Binder`.

Wraps a binder with the caller-facing ``tasks`` / ``events`` modules
and the dual-form ``consumer`` / ``subscribe`` sugar. The facade adds
no behavior — it's a thin Protocol-satisfying layer so the binder can
stay focused on transport and the caller API stays uniform.

See ``MESSAGE_BUS_SPEC_AND_PLAN.md`` §4.1.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, ContextManager, Iterator, Optional

from magellon_sdk.bus.interfaces import (
    Binder,
    ConsumerHandle,
    EventHandler,
    EventsBus,
    MessageBus,
    PatternRef,
    RouteRef,
    SubscriptionHandle,
    TaskHandler,
    TasksBus,
)
from magellon_sdk.bus.policy import PublishReceipt, TaskConsumerPolicy
from magellon_sdk.envelope import Envelope


# ---------------------------------------------------------------------------
# Sub-facades
# ---------------------------------------------------------------------------

class _TasksFacade:
    """Implements :class:`TasksBus` — thin wrapper over binder methods."""

    def __init__(self, binder: Binder) -> None:
        self._binder = binder

    def send(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        return self._binder.publish_task(route, envelope)

    def consumer(
        self,
        route: RouteRef,
        handler: Optional[TaskHandler] = None,
        *,
        policy: Optional[TaskConsumerPolicy] = None,
    ):
        """Dual-form: decorator when ``handler`` is ``None``, imperative
        otherwise. See :class:`TasksBus` for semantics."""
        p = policy or TaskConsumerPolicy()

        def _register(fn: TaskHandler) -> ConsumerHandle:
            return self._binder.consume_tasks(route, fn, p)

        return _register if handler is None else _register(handler)

    def purge(self, route: RouteRef) -> int:
        return self._binder.purge_tasks(route)


class _EventsFacade:
    """Implements :class:`EventsBus`."""

    def __init__(self, binder: Binder) -> None:
        self._binder = binder

    def publish(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        return self._binder.publish_event(route, envelope)

    def subscribe(
        self,
        pattern: PatternRef,
        handler: Optional[EventHandler] = None,
    ):
        def _register(fn: EventHandler) -> SubscriptionHandle:
            return self._binder.subscribe_events(pattern, fn)

        return _register if handler is None else _register(handler)


# ---------------------------------------------------------------------------
# MessageBus
# ---------------------------------------------------------------------------

class DefaultMessageBus:
    """Composite facade — ``.tasks`` + ``.events`` + lifecycle."""

    def __init__(self, binder: Binder) -> None:
        self._binder = binder
        self.tasks: TasksBus = _TasksFacade(binder)
        self.events: EventsBus = _EventsFacade(binder)

    def start(self) -> ContextManager[None]:
        self._binder.start()
        return self._context()

    @contextmanager
    def _context(self) -> Iterator[None]:
        try:
            yield
        finally:
            self.close()

    def close(self) -> None:
        self._binder.close()

    # Usable directly as a context manager too: ``with bus: ...``
    def __enter__(self) -> "DefaultMessageBus":
        self._binder.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Registry — get_bus() entry point
# ---------------------------------------------------------------------------

BusFactory = Callable[[], MessageBus]


class _BusRegistry:
    """Lazy registry for the process-wide MessageBus.

    ``get_bus()`` returns the instance; on first call it constructs
    from the registered factory. Tests call ``get_bus.override(bus)``
    to swap in a mock before any consumer registration runs, and
    ``get_bus.reset()`` to tear down.

    No module-level singleton means tests never race import order.
    """

    def __init__(self) -> None:
        self._bus: Optional[MessageBus] = None
        self._factory: Optional[BusFactory] = None

    def __call__(self) -> MessageBus:
        if self._bus is None:
            if self._factory is None:
                raise RuntimeError(
                    "No MessageBus configured. Call get_bus.set_factory(...) "
                    "at process boot, or get_bus.override(...) from a test "
                    "fixture."
                )
            self._bus = self._factory()
        return self._bus

    def set_factory(self, factory: BusFactory) -> None:
        """Register how to lazily build the default bus. Typical
        caller: CoreService startup reads settings and supplies a
        factory that constructs the RMQ binder + facade."""
        self._factory = factory

    def override(self, bus: MessageBus) -> None:
        """Swap in a specific bus instance — used by test fixtures."""
        self._bus = bus

    def reset(self) -> None:
        """Clear the current instance and any override. The next
        ``get_bus()`` call rebuilds via the factory if one is set."""
        self._bus = None


# Process-wide registry. Callers import ``get_bus`` directly.
get_bus = _BusRegistry()


__all__ = ["DefaultMessageBus", "get_bus"]
