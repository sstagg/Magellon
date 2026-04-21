"""CoreService wrapper over ``magellon_sdk.bus.services.liveness_registry``.

MB5.4a moved the registry data structures + listener wiring into the
SDK so any deployment that wants a broker-fed liveness table can use
the same code. CoreService's callers (``main.py``, ``plugins/
controller.py``, ``services/broker_inspector_service.py``, tests) still
import from here — this module re-exports for backcompat.

The listener signature keeps the legacy ``settings`` arg for callers
that still pass it; the bus is resolved via ``get_bus()`` and the
argument is no longer consulted. ``queue_name`` is retained for the
same reason (the binder picks a per-subscription queue).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.services.liveness_registry import (
    LivenessListener,
    PluginLivenessEntry,
    PluginLivenessRegistry,
    get_registry,
    start_liveness_listener as _sdk_start_liveness_listener,
)

logger = logging.getLogger(__name__)


def start_liveness_listener(
    settings: Any = None,
    *,
    queue_name: str = "magellon.plugins.liveness",
    registry: Optional[PluginLivenessRegistry] = None,
    bus: Optional[MessageBus] = None,
) -> LivenessListener:
    """Thin wrapper over the SDK listener.

    Pre-MB5.4a this opened a pika BlockingConnection and bound a
    single queue with routing_key=``#`` to the magellon.plugins
    exchange. Post-MB5.4a it subscribes via ``bus.events.subscribe``
    on :class:`AnnounceRoute.all` and :class:`HeartbeatRoute.all`
    patterns. Config-broker messages no longer land here (they used
    to arrive, fail to parse as Heartbeat, and get nacked) — the
    route-specific patterns filter them out at the bind layer.
    """
    return _sdk_start_liveness_listener(registry=registry, bus=bus)


__all__ = [
    "LivenessListener",
    "PluginLivenessEntry",
    "PluginLivenessRegistry",
    "get_registry",
    "start_liveness_listener",
]
