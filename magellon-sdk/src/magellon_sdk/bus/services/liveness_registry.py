"""Live plugin registry fed by broker discovery (MB5.4a).

Relocated from ``CoreService/core/plugin_liveness_registry.py``. The
data structures + singleton + the listener wiring are all
transport-neutral — they consume :class:`Announce` and
:class:`Heartbeat` Pydantic shapes via ``bus.events.subscribe`` on
:class:`AnnounceRoute` / :class:`HeartbeatRoute` patterns. CoreService
keeps a thin re-export wrapper so existing imports
(``from core.plugin_liveness_registry import ...``) keep working.

CoreService used to learn about plugins via Consul service registration.
The plugin-platform refactor (P6) replaced that with a pure-broker
listener: every plugin's :class:`DiscoveryPublisher` posts to the
``magellon.plugins`` topic exchange, and we maintain an in-memory
table keyed by ``(plugin_id, instance_id)`` with the last manifest +
last heartbeat timestamp.

The registry is the source of truth for "which plugins are alive right
now"; it is intentionally non-persistent. A CoreService restart picks
the table up from the *next* heartbeat round (≤15s by default). This is
fine because the broker — not the registry — is what carries tasks; a
plugin that's silent here is still reachable via its work queue if it
recovers.

MB5.4a changes vs. the pre-move version:

- Two explicit subscriptions (announce + heartbeat) instead of one
  wildcard ``#`` binding. Cleaner separation — the pre-move listener
  used ``if "manifest" in payload`` to discriminate, which swallowed
  config-broker messages (same exchange) as malformed heartbeats. The
  bus-side route filter means only announce and heartbeat deliveries
  reach this module.
- No pika: binder owns the connection, ack/nack/DLQ classification,
  and reconnect. ``PermanentError`` on malformed payloads routes to
  DLQ explicitly.
- Listener's consumer handles are returned + stored; stop() closes
  them cleanly instead of hanging on a blocking ``start_consuming``.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.interfaces import MessageBus, SubscriptionHandle
from magellon_sdk.bus.routes.event_route import AnnounceRoute, HeartbeatRoute
from magellon_sdk.discovery import Announce, Heartbeat
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class PluginLivenessEntry:
    """One row in the live-registry table.

    Holds the last manifest seen via Announce + the latest heartbeat
    timestamp + status. Mutated in place by the listener thread; the
    read API copies before returning so callers can iterate safely.
    """

    __slots__ = (
        "plugin_id",
        "plugin_version",
        "category",
        "instance_id",
        "manifest",
        "last_heartbeat",
        "status",
        "task_queue",
        "backend_id",
    )

    def __init__(
        self,
        *,
        plugin_id: str,
        plugin_version: str,
        category: str,
        instance_id: str,
        manifest: Optional[Any] = None,
        last_heartbeat: Optional[datetime] = None,
        status: str = "ready",
        task_queue: Optional[str] = None,
        backend_id: Optional[str] = None,
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.category = category
        self.instance_id = instance_id
        self.manifest = manifest
        self.last_heartbeat = last_heartbeat
        self.status = status
        # Plugin-declared task queue (SDK 1.1+ Announce.task_queue).
        # ``None`` for pre-1.1 plugins; the dispatcher falls back to
        # the category-scoped legacy route in that case.
        self.task_queue = task_queue
        # Substitutable identity within the category (SDK 1.3+).
        # When ``None`` the registry hasn't seen a 1.3+ announce; the
        # dispatcher treats ``plugin_id`` as a structural fallback so
        # legacy plugins remain reachable for category-wide dispatch
        # (just not for ``target_backend`` pinning).
        self.backend_id = backend_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "category": self.category,
            "instance_id": self.instance_id,
            "manifest": self.manifest.model_dump() if self.manifest else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "status": self.status,
            "task_queue": self.task_queue,
            "backend_id": self.backend_id,
        }


class PluginLivenessRegistry:
    """Thread-safe in-memory table of live plugins.

    Designed to be a singleton per process. The
    :func:`start_liveness_listener` helper subscribes to the discovery
    exchange and feeds this object on every announce/heartbeat.
    """

    def __init__(self, *, stale_after_seconds: float = 60.0) -> None:
        # Stale-threshold defaults to 4× the plugin's default heartbeat
        # interval (15s) — three missed pulses before we hide it.
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self._entries: Dict[Tuple[str, str], PluginLivenessEntry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(plugin_id: str, instance_id: str) -> Tuple[str, str]:
        return (plugin_id, instance_id)

    def record_announce(self, msg: Announce) -> None:
        with self._lock:
            key = self._key(msg.plugin_id, msg.instance_id)
            task_queue = getattr(msg, "task_queue", None)
            # Pre-1.3 announces won't carry backend_id directly; fall
            # back to the manifest helper so the dispatcher's pinning
            # path still has something to match against. Hidden third
            # fallback: a slug of plugin_id, in case the manifest is
            # malformed.
            backend_id = getattr(msg, "backend_id", None)
            if backend_id is None and msg.manifest is not None:
                try:
                    backend_id = msg.manifest.resolved_backend_id()
                except Exception:  # noqa: BLE001
                    backend_id = None
            if backend_id is None:
                backend_id = "-".join(msg.plugin_id.strip().lower().split()) or None

            entry = self._entries.get(key)
            if entry is None:
                # Cross-instance duplicate-backend check: a different
                # live entry in the same category claims this backend_id
                # under a different plugin_version. That is the
                # configuration mistake the doc warns about (two engines
                # both calling themselves "ctffind4"). Log loudly so
                # operators see it.
                if backend_id is not None:
                    self._warn_duplicate_backend(msg, backend_id)
                entry = PluginLivenessEntry(
                    plugin_id=msg.plugin_id,
                    plugin_version=msg.plugin_version,
                    category=msg.category,
                    instance_id=msg.instance_id,
                    manifest=msg.manifest,
                    last_heartbeat=msg.ts,
                    task_queue=task_queue,
                    backend_id=backend_id,
                )
                self._entries[key] = entry
            else:
                entry.manifest = msg.manifest
                entry.plugin_version = msg.plugin_version
                entry.last_heartbeat = msg.ts
                # Re-announces can update the queue (config change,
                # plugin upgrade). Only overwrite when the new announce
                # actually carried a value — avoid wiping on pre-1.1
                # plugins that re-announce without the field.
                if task_queue is not None:
                    entry.task_queue = task_queue
                if backend_id is not None:
                    entry.backend_id = backend_id

    def _warn_duplicate_backend(self, msg: Announce, backend_id: str) -> None:
        """Log when a second live plugin claims the same backend_id.

        Same plugin_id under a different instance_id (scale-out replicas)
        is fine — they're the *same* backend. We only flag the case
        where two distinct plugin_ids in the same category collide on
        backend_id, which is the misconfiguration to surface.
        """
        for other in self._entries.values():
            if (
                other.category == msg.category
                and other.backend_id == backend_id
                and other.plugin_id != msg.plugin_id
            ):
                logger.warning(
                    "DUP_BACKEND_ID: backend_id=%r in category=%r is claimed by "
                    "both plugin_id=%r (version=%s) and plugin_id=%r (version=%s). "
                    "Dispatcher will prefer the first one it finds. "
                    "Rename one of them.",
                    backend_id, msg.category,
                    other.plugin_id, other.plugin_version,
                    msg.plugin_id, msg.plugin_version,
                )

    def record_heartbeat(self, msg: Heartbeat) -> None:
        with self._lock:
            key = self._key(msg.plugin_id, msg.instance_id)
            entry = self._entries.get(key)
            if entry is None:
                # Heartbeat arrived before announce (or after we restarted
                # and missed the announce). Materialize a stub entry —
                # next announce will fill in the manifest. Without this
                # the plugin would stay invisible until restart.
                # backend_id is best-guessed from plugin_id; the next
                # announce overwrites with the manifest-declared value.
                fallback_backend = "-".join(msg.plugin_id.strip().lower().split()) or None
                entry = PluginLivenessEntry(
                    plugin_id=msg.plugin_id,
                    plugin_version=msg.plugin_version,
                    category=msg.category,
                    instance_id=msg.instance_id,
                    last_heartbeat=msg.ts,
                    status=msg.status,
                    backend_id=fallback_backend,
                )
                self._entries[key] = entry
            else:
                entry.last_heartbeat = msg.ts
                entry.status = msg.status

    def list_live(self, *, now: Optional[datetime] = None) -> List[PluginLivenessEntry]:
        """Return entries whose last heartbeat is within the stale window."""
        cutoff = (now or _now_utc()) - self.stale_after
        with self._lock:
            return [
                e
                for e in self._entries.values()
                if e.last_heartbeat is not None and e.last_heartbeat >= cutoff
            ]

    def reap_stale(self, *, now: Optional[datetime] = None) -> int:
        """Drop entries past the stale window. Returns count removed."""
        cutoff = (now or _now_utc()) - self.stale_after
        with self._lock:
            stale_keys = [
                k
                for k, e in self._entries.items()
                if e.last_heartbeat is None or e.last_heartbeat < cutoff
            ]
            for k in stale_keys:
                del self._entries[k]
            return len(stale_keys)

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._entries.values()]


# ---------------------------------------------------------------------------
# Process-wide singleton + listener
# ---------------------------------------------------------------------------

_REGISTRY: Optional[PluginLivenessRegistry] = None


def get_registry() -> PluginLivenessRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = PluginLivenessRegistry()
    return _REGISTRY


class LivenessListener:
    """Holder for the pair of bus subscriptions feeding the registry.

    Kept as an object rather than a bare function-return so callers can
    stop() cleanly on shutdown. Previous pika-based listener returned
    a consumer object with start/stop; preserving that shape keeps
    CoreService's ``main.py`` wiring unchanged.
    """

    def __init__(
        self,
        *,
        registry: PluginLivenessRegistry,
        announce_handle: SubscriptionHandle,
        heartbeat_handle: SubscriptionHandle,
    ) -> None:
        self.registry = registry
        self._announce_handle = announce_handle
        self._heartbeat_handle = heartbeat_handle

    def stop(self) -> None:
        for handle in (self._announce_handle, self._heartbeat_handle):
            try:
                handle.close()
            except Exception:  # noqa: BLE001 — shutdown best-effort
                logger.exception("liveness listener: handle close failed")


def start_liveness_listener(
    *,
    registry: Optional[PluginLivenessRegistry] = None,
    bus: Optional[MessageBus] = None,
) -> LivenessListener:
    """Subscribe to announce + heartbeat patterns and feed ``registry``.

    Two bus subscriptions:

    - ``AnnounceRoute.all()`` → ``magellon.plugins.announce.>``
    - ``HeartbeatRoute.all()`` → ``magellon.plugins.heartbeat.>``

    Each delivery's ``envelope.data`` decodes into the matching Pydantic
    shape and is handed to ``registry.record_*``. Malformed payloads
    raise :class:`PermanentError` so the binder routes them to the DLQ
    — a bad shape won't decode on retry either.

    Returns a :class:`LivenessListener` whose ``stop()`` closes both
    subscriptions. The binder owns the threads + reconnect.
    """
    target = registry or get_registry()
    resolved_bus = bus if bus is not None else get_bus()

    def _on_announce(envelope: Envelope) -> None:
        try:
            msg = Announce.model_validate(envelope.data)
        except Exception as exc:
            raise PermanentError(f"liveness: bad Announce payload: {exc}") from exc
        target.record_announce(msg)

    def _on_heartbeat(envelope: Envelope) -> None:
        try:
            msg = Heartbeat.model_validate(envelope.data)
        except Exception as exc:
            raise PermanentError(f"liveness: bad Heartbeat payload: {exc}") from exc
        target.record_heartbeat(msg)

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
