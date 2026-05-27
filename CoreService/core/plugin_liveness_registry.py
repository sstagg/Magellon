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

from services.plugin_catalog_persistence import (
    persist_announce,
    persist_heartbeat,
    rehydrate_announces,
)

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

    # Plugin announces are one-shot at plugin startup. After a
    # CoreService restart, the only liveness traffic is heartbeats,
    # which materialize manifest-less stubs (no capabilities, no
    # schemas, no http_endpoint). Replay the persisted announce
    # catalog into the registry BEFORE we subscribe, so subsequent
    # heartbeats refresh real entries instead of stubs and downstream
    # consumers (side panel canPreview, sync_dispatcher endpoint
    # lookups) see the same state they did before the restart.
    try:
        seeded = rehydrate_announces(target)
        logger.info("liveness listener: rehydrated %d announce(s) from catalog", seeded)
    except Exception:
        logger.exception("liveness listener: rehydrate from catalog failed")

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
        _inherit_manifest_from_sibling(target, msg)
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


def _inherit_manifest_from_sibling(
    registry: PluginLivenessRegistry, msg: Heartbeat
) -> None:
    """Copy a sibling rehydrated entry's manifest onto a fresh heartbeat stub.

    The registry keys entries by ``(plugin_id, instance_id)``. After a
    CoreService restart, the rehydrator seeds entries under the
    *historic* instance_id stored in the catalog, but the plugin's
    current process heartbeats with a *fresh* instance_id (set on every
    plugin restart). That leaves us with two entries:

    1. The rehydrated one — has manifest / http_endpoint / schemas,
       but its ``last_heartbeat`` never refreshes in memory (only the
       persistence layer's DB row does), so it ages out after
       ``stale_after_seconds`` and disappears from ``list_live``.
    2. The live heartbeat stub — fresh ``last_heartbeat``, but no
       manifest. ``has_preview`` / ``has_sync`` flip to false; the
       side panel falls into its degraded branch.

    Hand the manifest from (1) onto (2) on every heartbeat so the live
    entry carries the right capabilities even though it never received
    a fresh Announce. The rehydrated entry then naturally ages out
    without taking the capabilities with it.

    No-op when:
    - the heartbeat already has a manifest (announce arrived first),
    - there's no sibling entry with a manifest under the same plugin_id,
    - any concurrent mutation makes the inheritance racy (best-effort).
    """
    try:
        with registry._lock:  # noqa: SLF001 — registry is in same package
            current = registry._entries.get(
                (msg.plugin_id, msg.instance_id)
            )
            if current is None or current.manifest is not None:
                return
            sibling = None
            for (pid, iid), entry in registry._entries.items():
                if pid != msg.plugin_id or iid == msg.instance_id:
                    continue
                if entry.manifest is None:
                    continue
                sibling = entry
                break
            if sibling is None:
                return
            current.manifest = sibling.manifest
            current.plugin_version = sibling.plugin_version or current.plugin_version
            current.backend_id = sibling.backend_id or current.backend_id
            current.task_queue = sibling.task_queue or current.task_queue
            current.http_endpoint = sibling.http_endpoint or current.http_endpoint
            current.input_schema = sibling.input_schema or current.input_schema
            current.output_schema = sibling.output_schema or current.output_schema
            current.category = current.category or sibling.category
    except Exception:
        logger.exception(
            "liveness listener: manifest inheritance failed for plugin_id=%s",
            msg.plugin_id,
        )


__all__ = [
    "LivenessListener",
    "PluginLivenessEntry",
    "PluginLivenessRegistry",
    "get_registry",
    "start_liveness_listener",
]
