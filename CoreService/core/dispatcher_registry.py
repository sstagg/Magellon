"""Process-wide :class:`TaskDispatcherRegistry` backed by the MessageBus (MB3).

Pre-MB3 this module constructed :class:`RabbitmqTaskDispatcher`
instances directly. MB3 replaces those with :class:`_BusTaskDispatcher`
which wraps the task in a CloudEvents :class:`Envelope` and delegates
to :func:`get_bus` — the underlying transport (RMQ today) is now a
binder behind the bus, not a direct pika dependency of this module.

The registry's public API is unchanged: callers still use
``get_task_dispatcher_registry().dispatch(task)``.

Bus wiring strategy:

- On import, this module registers a **default bus factory** with
  ``get_bus.set_factory(...)`` that builds an :class:`RmqBinder` with
  a ``legacy_queue_map`` drawn from ``app_settings.rabbitmq_settings``.
  The map translates bus subjects (e.g. ``magellon.tasks.ctf``) to
  today's legacy queue names (e.g. ``ctf_tasks_queue``) so existing
  plugin consumers keep receiving on the same queue.
- Factory runs lazily on first ``get_bus()`` call — keeps test
  startup cheap. Tests that want a mock bus call
  ``get_bus.override(mock)`` before the first dispatch.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from magellon_sdk.bus import DefaultMessageBus, get_bus
from magellon_sdk.bus.binders.rmq import RmqBinder
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.categories.contract import CTF, FFT, MOTIONCOR_CATEGORY
from magellon_sdk.dispatcher import TaskDispatcherRegistry
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import CTF_TASK, FFT_TASK, MOTIONCOR, TaskDto

from config import app_settings

if TYPE_CHECKING:
    from magellon_sdk.bus import MessageBus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TaskDispatcher Protocol impl: adapts bus.tasks.send → registry call sites
# ---------------------------------------------------------------------------

class _BusTaskDispatcher:
    """Wraps a :class:`TaskDto` in a CloudEvents envelope and sends
    via ``bus.tasks.send``. Satisfies :class:`TaskDispatcher` Protocol
    structurally.

    Instances are lightweight — no bus call at construction time.
    Dispatch retrieves the bus lazily via :func:`get_bus`, so the
    registry can be built before the bus is wired.
    """

    _ENVELOPE_TYPE = "magellon.task.dispatch"
    _ENVELOPE_SOURCE = "magellon/core_service/dispatcher"

    def __init__(self, *, route: TaskRoute, name: str) -> None:
        self.route = route
        self.name = name

    def dispatch(self, task: TaskDto) -> bool:
        envelope = Envelope.wrap(
            source=self._ENVELOPE_SOURCE,
            type=self._ENVELOPE_TYPE,
            subject=self.route.subject,
            data=task,
        )
        receipt = get_bus().tasks.send(self.route, envelope)
        if not receipt.ok:
            logger.error(
                "bus dispatch failed on %s: %s", self.route.subject, receipt.error
            )
        return receipt.ok


# ---------------------------------------------------------------------------
# Default production bus factory
# ---------------------------------------------------------------------------

def _build_legacy_queue_map() -> dict[str, str]:
    """Map bus subjects to today's production queue names.

    Bus routes use category-scoped subjects (``magellon.tasks.ctf``);
    plugin consumers bind to physical queues named
    ``ctf_tasks_queue`` etc. Populated from
    ``app_settings.rabbitmq_settings`` so the mapping stays
    environment-configurable.
    """
    rmq = app_settings.rabbitmq_settings
    mapping: dict[str, str] = {}

    def _map(contract, task_queue: str, result_queue: str) -> None:
        mapping[TaskRoute.for_category(contract).subject] = task_queue
        mapping[TaskResultRoute.for_category(contract).subject] = result_queue

    _map(CTF, rmq.CTF_QUEUE_NAME, rmq.CTF_OUT_QUEUE_NAME)
    _map(MOTIONCOR_CATEGORY, rmq.MOTIONCOR_QUEUE_NAME, rmq.MOTIONCOR_OUT_QUEUE_NAME)
    _map(FFT, rmq.FFT_QUEUE_NAME, rmq.FFT_OUT_QUEUE_NAME)
    return mapping


def _default_bus_factory() -> "MessageBus":
    """Build the production bus: RmqBinder with legacy queue map, started."""
    rmq = app_settings.rabbitmq_settings
    binder = RmqBinder(
        settings=rmq,
        legacy_queue_map=_build_legacy_queue_map(),
    )
    bus = DefaultMessageBus(binder)
    bus.start()
    return bus


# Register the default factory on module import. Idempotent in practice:
# if a test has already set a factory (or overridden the bus), we leave
# their override in place so test fixtures retain precedence.
if get_bus._factory is None:
    get_bus.set_factory(_default_bus_factory)


# ---------------------------------------------------------------------------
# Public: TaskDispatcherRegistry wired for the three live categories
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_task_dispatcher_registry() -> TaskDispatcherRegistry:
    """Return the process-wide registry, building it on first call.

    Cached so every caller shares one instance — avoids rebuilding
    dispatcher objects on each task and keeps the ``name`` field
    stable for log correlation.
    """
    registry = TaskDispatcherRegistry()

    registry.register(
        CTF_TASK,
        _BusTaskDispatcher(route=TaskRoute.for_category(CTF), name="bus:ctf"),
    )
    registry.register(
        MOTIONCOR,
        _BusTaskDispatcher(
            route=TaskRoute.for_category(MOTIONCOR_CATEGORY), name="bus:motioncor"
        ),
    )
    registry.register(
        FFT_TASK,
        _BusTaskDispatcher(route=TaskRoute.for_category(FFT), name="bus:fft"),
    )
    return registry


__all__ = ["get_task_dispatcher_registry"]
