"""Process-wide :class:`TaskDispatcherRegistry` backed by the MessageBus (MB3).

Pre-MB3 this module constructed :class:`RabbitmqTaskDispatcher`
instances directly. MB3 replaces those with :class:`_BusTaskDispatcher`
which wraps the task in a CloudEvents :class:`Envelope` and delegates
to :func:`get_bus` — the underlying transport (RMQ today) is now a
binder behind the bus, not a direct pika dependency of this module.

The registry's public API is unchanged: callers still use
``get_task_dispatcher_registry().dispatch(task)``.

X.1 (2026-04-27): when ``task.target_backend`` is set, the dispatcher
asks :func:`_resolve_backend_queue` to map ``(category, backend_id)``
to a live plugin's task queue and publishes there directly. Unset
falls back to the category-default route (today's behaviour).

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
from typing import Callable, Optional

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.bootstrap import install_rmq_bus
from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.categories.contract import (
    CTF,
    DENOISE,
    FFT,
    HOLE_DETECT,
    MOTIONCOR_CATEGORY,
    SQUARE_DETECT,
    TOPAZ_PICK,
    CategoryContract,
)
from magellon_sdk.dispatcher import TaskDispatcherRegistry
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import CTF_TASK, FFT_TASK, MOTIONCOR, TaskDto
from magellon_sdk.models.tasks import (
    HOLE_DETECTION,
    MICROGRAPH_DENOISING,
    SQUARE_DETECTION,
    TOPAZ_PARTICLE_PICKING,
)

from config import app_settings

logger = logging.getLogger(__name__)


class BackendNotLive(RuntimeError):
    """Raised when ``target_backend`` is set but no live plugin matches.

    The dispatch contract: pinning is a hard request, not a hint. The
    caller asked for a specific backend and got none. Falling back
    silently to whatever happens to be the category default would
    bury the configuration mistake (operator pinned a backend that
    isn't running) inside an unrelated plugin's logs.
    """


BackendQueueResolver = Callable[[CategoryContract, str], Optional[str]]
"""Maps ``(category, backend_id)`` to the physical queue a live plugin
consumes from. Returns ``None`` when no live plugin matches.

Production resolver consults :class:`PluginLivenessRegistry`; tests
inject a stub. Kept as a free function rather than an interface so
the dispatcher's constructor stays uncoupled from CoreService."""


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

    When ``task.target_backend`` is set, the dispatcher consults its
    ``backend_resolver`` to find the live plugin's queue and publishes
    there. When unset, it routes to the category-default subject.
    """

    _ENVELOPE_TYPE = "magellon.task.dispatch"
    _ENVELOPE_SOURCE = "magellon/core_service/dispatcher"

    def __init__(
        self,
        *,
        route: TaskRoute,
        name: str,
        contract: CategoryContract,
        backend_resolver: Optional[BackendQueueResolver] = None,
    ) -> None:
        self.route = route
        self.name = name
        self.contract = contract
        self.backend_resolver = backend_resolver

    def dispatch(self, task: TaskDto) -> bool:
        route = self._route_for(task)
        envelope = Envelope.wrap(
            source=self._ENVELOPE_SOURCE,
            type=self._ENVELOPE_TYPE,
            subject=route.subject,
            data=task,
        )
        receipt = get_bus().tasks.send(route, envelope)
        if not receipt.ok:
            logger.error(
                "bus dispatch failed on %s: %s", route.subject, receipt.error
            )
        return receipt.ok

    def _route_for(self, task: TaskDto) -> TaskRoute:
        """Choose category-default vs backend-pinned route for ``task``.

        Pinning is binding: a task with ``target_backend`` set MUST go
        to that backend or fail loudly. Falling back to the default
        would mask configuration errors and surface as wrong-result
        bugs hours later.
        """
        target = getattr(task, "target_backend", None)
        if not target:
            return self.route
        if self.backend_resolver is None:
            raise BackendNotLive(
                f"task {task.id} pinned to backend={target!r} on category "
                f"{self.contract.category.name!r}, but no backend resolver "
                f"is wired into the dispatcher; the registry was constructed "
                f"without one."
            )
        queue = self.backend_resolver(self.contract, target)
        if not queue:
            raise BackendNotLive(
                f"task {task.id} pinned to backend={target!r} on category "
                f"{self.contract.category.name!r}, but no live plugin claims "
                f"that backend_id; refusing to fall back to the category "
                f"default to avoid silently mis-routing."
            )
        # Use the symbolic backend-pinned subject for logs/audit; the
        # binder still publishes to the resolved queue via the
        # legacy_queue_map seam.
        return TaskRoute.named(queue)


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
    _map(TOPAZ_PICK, rmq.TOPAZ_PICK_QUEUE_NAME, rmq.TOPAZ_PICK_OUT_QUEUE_NAME)
    _map(DENOISE, rmq.MICROGRAPH_DENOISE_QUEUE_NAME, rmq.MICROGRAPH_DENOISE_OUT_QUEUE_NAME)
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

def _live_backend_queue(contract: CategoryContract, backend_id: str) -> Optional[str]:
    """Production :data:`BackendQueueResolver`: read the live registry.

    Iterates the live plugins for ``contract.category`` and returns the
    ``task_queue`` of the first one whose ``backend_id`` matches.
    ``None`` if no live plugin claims that backend.

    Live = within the heartbeat staleness window. A backend that
    crashed mid-task is treated as unavailable for new pins; the
    in-flight task may still complete via its existing consumer.
    """
    # Local import avoids a startup-time cycle: this module is imported
    # by main.py before the liveness module, which lazily imports
    # bus.services on its own first call.
    from core.plugin_liveness_registry import get_registry as get_liveness_registry

    target_category = contract.category.name.lower()
    target_backend = backend_id.lower()
    for entry in get_liveness_registry().list_live():
        if (entry.category or "").lower() != target_category:
            continue
        if (entry.backend_id or "").lower() != target_backend:
            continue
        if entry.task_queue:
            return entry.task_queue
    return None


@lru_cache(maxsize=1)
def get_task_dispatcher_registry() -> TaskDispatcherRegistry:
    """Return the process-wide registry, building it on first call.

    Cached so every caller shares one instance — avoids rebuilding
    dispatcher objects on each task and keeps the ``name`` field
    stable for log correlation.
    """
    return _build_registry(backend_resolver=_live_backend_queue)


def _build_registry(
    *, backend_resolver: Optional[BackendQueueResolver]
) -> TaskDispatcherRegistry:
    """Pure-function registry builder.

    Tests inject a stub ``backend_resolver`` here without touching the
    ``lru_cache`` on :func:`get_task_dispatcher_registry`.
    """
    registry = TaskDispatcherRegistry()

    def _make(category_const, contract: CategoryContract, name: str) -> None:
        registry.register(
            category_const,
            _BusTaskDispatcher(
                route=TaskRoute.for_category(contract),
                name=name,
                contract=contract,
                backend_resolver=backend_resolver,
            ),
        )

    _make(CTF_TASK, CTF, "bus:ctf")
    _make(MOTIONCOR, MOTIONCOR_CATEGORY, "bus:motioncor")
    _make(FFT_TASK, FFT, "bus:fft")
    _make(SQUARE_DETECTION, SQUARE_DETECT, "bus:square_detection")
    _make(HOLE_DETECTION, HOLE_DETECT, "bus:hole_detection")
    _make(TOPAZ_PARTICLE_PICKING, TOPAZ_PICK, "bus:topaz_pick")
    _make(MICROGRAPH_DENOISING, DENOISE, "bus:micrograph_denoise")
    return registry


__all__ = [
    "BackendNotLive",
    "BackendQueueResolver",
    "get_task_dispatcher_registry",
    "install_core_bus",
]
