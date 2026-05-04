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

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.routes.event_route import AnnounceRoute, HeartbeatRoute
from magellon_sdk.bus.services.liveness_registry import (
    LivenessListener,
    PluginLivenessEntry,
    PluginLivenessRegistry,
    get_registry,
)
from magellon_sdk.discovery import Announce, Heartbeat
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

from services.plugin_catalog_persistence import persist_announce, persist_heartbeat

logger = logging.getLogger(__name__)


def start_liveness_listener(
    settings: Any = None,
    *,
    queue_name: str = "magellon.plugins.liveness",
    registry: Optional[PluginLivenessRegistry] = None,
    bus: Optional[MessageBus] = None,
) -> LivenessListener:
    """Subscribe to liveness messages and mirror discovery into SQL.

    Pre-MB5.4a this opened a pika BlockingConnection and bound a
    single queue with routing_key=``#`` to the magellon.plugins
    exchange. Post-MB5.4a it subscribes via ``bus.events.subscribe``
    on :class:`AnnounceRoute.all` and :class:`HeartbeatRoute.all`
    patterns. Config-broker messages no longer land here (they used
    to arrive, fail to parse as Heartbeat, and get nacked) — the
    route-specific patterns filter them out at the bind layer.
    """
    target = registry or get_registry()
    resolved_bus = bus if bus is not None else get_bus()

    def _on_announce(envelope: Envelope) -> None:
        try:
            msg = Announce.model_validate(envelope.data)
        except Exception as exc:
            raise PermanentError(f"liveness: bad Announce payload: {exc}") from exc
        target.record_announce(msg)
        try:
            persist_announce(msg)
        except Exception:
            logger.exception(
                "liveness listener: failed to persist announce for plugin_id=%s",
                msg.plugin_id,
            )

    def _on_heartbeat(envelope: Envelope) -> None:
        try:
            msg = Heartbeat.model_validate(envelope.data)
        except Exception as exc:
            raise PermanentError(f"liveness: bad Heartbeat payload: {exc}") from exc
        target.record_heartbeat(msg)
        try:
            persist_heartbeat(msg)
        except Exception:
            logger.exception(
                "liveness listener: failed to persist heartbeat for plugin_id=%s",
                msg.plugin_id,
            )

    announce_handle = resolved_bus.events.subscribe(AnnounceRoute.all(), _on_announce)
    heartbeat_handle = resolved_bus.events.subscribe(HeartbeatRoute.all(), _on_heartbeat)
    logger.info("liveness listener: subscribed to announce + heartbeat")

    return LivenessListener(
        registry=target,
        announce_handle=announce_handle,
        heartbeat_handle=heartbeat_handle,
    )


__all__ = [
    "LivenessListener",
    "PluginLivenessEntry",
    "PluginLivenessRegistry",
    "get_registry",
    "start_liveness_listener",
]
