"""Process-wide :class:`TaskDispatcherRegistry` backed by the MessageBus (MB3).

Pre-MB3 this module constructed :class:`RabbitmqTaskDispatcher`
instances directly. MB3 replaces those with :class:`_BusTaskDispatcher`
which wraps the task in a CloudEvents :class:`Envelope` and delegates
to :func:`get_bus` — the underlying transport (RMQ today) is now a
binder behind the bus, not a direct pika dependency of this module.

The registry's public API is unchanged: callers still use
``get_task_dispatcher_registry().dispatch(task)``.

Bus wiring strategy:

- CoreService startup (``main.py``) calls :func:`install_core_bus`
  explicitly *before* any consumer thread spawns. It builds an
  :class:`RmqBinder` with a ``legacy_queue_map`` drawn from
  ``app_settings.rabbitmq_settings`` — the map translates bus
  subjects (e.g. ``magellon.tasks.ctf``) to today's legacy queue
  names (e.g. ``ctf_tasks_queue``) so existing plugin consumers
  keep receiving on the same queue.
- Tests that want a mock bus call ``get_bus.override(mock)`` before
  the first dispatch; they never invoke :func:`install_core_bus`.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.bootstrap import install_rmq_bus
from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.categories.contract import (
    CTF,
    FFT,
    HOLE_DETECT,
    MOTIONCOR_CATEGORY,
    SQUARE_DETECT,
)
from magellon_sdk.dispatcher import TaskDispatcherRegistry
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import CTF_TASK, FFT_TASK, MOTIONCOR, TaskDto
from magellon_sdk.models.tasks import HOLE_DETECTION, SQUARE_DETECTION

from config import app_settings

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
    _map(SQUARE_DETECT, rmq.SQUARE_DETECTION_QUEUE_NAME, rmq.SQUARE_DETECTION_OUT_QUEUE_NAME)
    _map(HOLE_DETECT, rmq.HOLE_DETECTION_QUEUE_NAME, rmq.HOLE_DETECTION_OUT_QUEUE_NAME)
    return mapping


def install_core_bus() -> MessageBus:
    """Install the production RMQ-backed bus as the process-wide bus.

    Must be called once at CoreService startup *before* any thread
    that calls ``get_bus()`` (result consumer, step-event forwarder,
    liveness listener). Idempotent-safe when called a second time
    only in the sense that ``get_bus.override`` replaces the instance;
    the previous binder is leaked, so don't do that in production.
    """
    return install_rmq_bus(
        app_settings.rabbitmq_settings,
        legacy_queue_map=_build_legacy_queue_map(),
    )


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
    registry.register(
        SQUARE_DETECTION,
        _BusTaskDispatcher(
            route=TaskRoute.for_category(SQUARE_DETECT), name="bus:square_detection"
        ),
    )
    registry.register(
        HOLE_DETECTION,
        _BusTaskDispatcher(
            route=TaskRoute.for_category(HOLE_DETECT), name="bus:hole_detection"
        ),
    )
    return registry


__all__ = ["get_task_dispatcher_registry", "install_core_bus"]
