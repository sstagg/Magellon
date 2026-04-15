"""Singleton :class:`TaskDispatcherRegistry` wired from ``app_settings``.

Replaces the hand-rolled ``if task_type.code == 5: return
MOTIONCOR_QUEUE_NAME; elif …`` switch in :mod:`core.helper` with a
Protocol-based lookup (Phase 6).

Today every plugin runs over RabbitMQ so every registered dispatcher
is a :class:`RabbitmqTaskDispatcher`. When a plugin wants to swap in
``InProcessTaskDispatcher`` (or a future Kubernetes/RunPod one), it
changes the single registration below — call sites stay the same.
"""
from __future__ import annotations

from functools import lru_cache

from magellon_sdk.dispatcher import RabbitmqTaskDispatcher, TaskDispatcherRegistry
from magellon_sdk.models import CTF_TASK, MOTIONCOR

from config import app_settings


@lru_cache(maxsize=1)
def get_task_dispatcher_registry() -> TaskDispatcherRegistry:
    """Return the process-wide registry, building it on first call.

    Cached via :func:`lru_cache` so every caller shares one instance —
    avoids re-reading settings on each dispatch and keeps the
    ``name`` field stable for log correlation.
    """
    registry = TaskDispatcherRegistry()
    rmq = app_settings.rabbitmq_settings

    registry.register(
        CTF_TASK,
        RabbitmqTaskDispatcher(
            queue_name=rmq.CTF_QUEUE_NAME,
            rabbitmq_settings=rmq,
            name="rabbitmq:ctf",
        ),
    )
    registry.register(
        MOTIONCOR,
        RabbitmqTaskDispatcher(
            queue_name=rmq.MOTIONCOR_QUEUE_NAME,
            rabbitmq_settings=rmq,
            name="rabbitmq:motioncor",
        ),
    )
    return registry


__all__ = ["get_task_dispatcher_registry"]
