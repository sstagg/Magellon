"""Live plugin registry fed by broker discovery (P6).

CoreService used to learn about plugins via Consul service registration.
This module replaces that with a pure-broker listener: every plugin's
:class:`magellon_sdk.discovery.DiscoveryPublisher` posts to the
``magellon.plugins`` topic exchange, and we maintain an in-memory table
keyed by ``(plugin_id, instance_id)`` with the last manifest + last
heartbeat timestamp.

The registry is the source of truth for "which plugins are alive right
now"; it is intentionally non-persistent. A CoreService restart picks
the table up from the *next* heartbeat round (≤15s by default). This is
fine because the broker — not the registry — is what carries tasks; a
plugin that's silent here is still reachable via its work queue if it
recovers.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from magellon_sdk.discovery import (
    DEFAULT_EXCHANGE,
    Announce,
    Heartbeat,
)
from magellon_sdk.transport.rabbitmq_events import (
    RabbitmqEventConsumer,  # reuse: same topic-consumer pattern
)

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
    ) -> None:
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.category = category
        self.instance_id = instance_id
        self.manifest = manifest
        self.last_heartbeat = last_heartbeat
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_version": self.plugin_version,
            "category": self.category,
            "instance_id": self.instance_id,
            "manifest": self.manifest.model_dump() if self.manifest else None,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "status": self.status,
        }


class PluginLivenessRegistry:
    """Thread-safe in-memory table of live plugins.

    Designed to be a singleton per CoreService process. The
    :func:`run_listener` helper subscribes to the discovery exchange
    and feeds this object on every announce/heartbeat.
    """

    def __init__(self, *, stale_after_seconds: float = 60.0) -> None:
        # Stale-threshold defaults to 4× the plugin's default heartbeat
        # interval (15s) — three missed pulses before we hide it.
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self._entries: Dict[tuple, PluginLivenessEntry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(plugin_id: str, instance_id: str) -> tuple:
        return (plugin_id, instance_id)

    def record_announce(self, msg: Announce) -> None:
        with self._lock:
            key = self._key(msg.plugin_id, msg.instance_id)
            entry = self._entries.get(key)
            if entry is None:
                entry = PluginLivenessEntry(
                    plugin_id=msg.plugin_id,
                    plugin_version=msg.plugin_version,
                    category=msg.category,
                    instance_id=msg.instance_id,
                    manifest=msg.manifest,
                    last_heartbeat=msg.ts,
                )
                self._entries[key] = entry
            else:
                entry.manifest = msg.manifest
                entry.plugin_version = msg.plugin_version
                entry.last_heartbeat = msg.ts

    def record_heartbeat(self, msg: Heartbeat) -> None:
        with self._lock:
            key = self._key(msg.plugin_id, msg.instance_id)
            entry = self._entries.get(key)
            if entry is None:
                # Heartbeat arrived before announce (or after we restarted
                # and missed the announce). Materialize a stub entry —
                # next announce will fill in the manifest. Without this
                # the plugin would stay invisible until restart.
                entry = PluginLivenessEntry(
                    plugin_id=msg.plugin_id,
                    plugin_version=msg.plugin_version,
                    category=msg.category,
                    instance_id=msg.instance_id,
                    last_heartbeat=msg.ts,
                    status=msg.status,
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


# Process-wide singleton — pattern matches the rest of CoreService
# (app_settings, dispatcher_registry).
_REGISTRY: Optional[PluginLivenessRegistry] = None


def get_registry() -> PluginLivenessRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = PluginLivenessRegistry()
    return _REGISTRY


# ---------------------------------------------------------------------------
# Listener wiring
# ---------------------------------------------------------------------------

def _route_envelope(body: bytes, registry: PluginLivenessRegistry) -> None:
    """Try Announce first, then Heartbeat. Both are JSON, distinguished
    by the ``manifest`` key being present."""
    import json

    payload = json.loads(body.decode("utf-8"))
    if "manifest" in payload and payload["manifest"] is not None:
        registry.record_announce(Announce.model_validate(payload))
    else:
        registry.record_heartbeat(Heartbeat.model_validate(payload))


def start_liveness_listener(
    settings: Any,
    *,
    queue_name: str = "magellon.plugins.liveness",
    registry: Optional[PluginLivenessRegistry] = None,
) -> RabbitmqEventConsumer:
    """Start a daemon-thread consumer feeding the liveness registry.

    Subscribes with binding key ``#`` against the
    :data:`magellon_sdk.discovery.DEFAULT_EXCHANGE` topic exchange so a
    single queue receives both announce.* and heartbeat.* deliveries.
    """
    target = registry or get_registry()

    def _callback(envelope_or_body):
        # The events consumer hands us an Envelope[Any] for the step-event
        # case; here we re-purpose only its connection mgmt and ignore
        # the envelope wrapping by going through a thin shim. To keep
        # the change small we wrap the consumer directly.
        raise NotImplementedError(
            "use the raw-body consumer below — kept for type docs"
        )

    # We can't reuse RabbitmqEventConsumer directly because it forces an
    # Envelope decode. Build a minimal sibling here.
    from magellon_sdk.transport.rabbitmq import RabbitmqClient

    class _LivenessConsumer:
        def __init__(self):
            self._thread: Optional[threading.Thread] = None
            self._client: Optional[RabbitmqClient] = None
            self._running = False

        def start(self):
            if self._thread is not None:
                return

            def _run():
                client = RabbitmqClient(settings)
                try:
                    client.connect()
                    client.channel.exchange_declare(
                        exchange=DEFAULT_EXCHANGE,
                        exchange_type="topic",
                        durable=True,
                    )
                    client.channel.queue_declare(queue=queue_name, durable=True)
                    client.channel.queue_bind(
                        exchange=DEFAULT_EXCHANGE,
                        queue=queue_name,
                        routing_key="#",
                    )

                    def _on_message(ch, method, properties, body):
                        try:
                            _route_envelope(body, target)
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                        except Exception as exc:
                            logger.warning(
                                "liveness listener: bad payload (%s) — DLQing", exc
                            )
                            ch.basic_nack(
                                delivery_tag=method.delivery_tag, requeue=False
                            )

                    client.channel.basic_consume(
                        queue=queue_name, on_message_callback=_on_message
                    )
                    self._client = client
                    self._running = True
                    logger.info("liveness listener: bound %s to %s", queue_name, DEFAULT_EXCHANGE)
                    client.channel.start_consuming()
                except Exception:
                    if self._running:
                        logger.exception("liveness listener: consume loop crashed")

            self._thread = threading.Thread(target=_run, daemon=True)
            self._thread.start()

        def stop(self):
            self._running = False
            if self._client and self._client.channel:
                try:
                    self._client.channel.stop_consuming()
                except Exception:
                    pass
                self._client.close_connection()

    consumer = _LivenessConsumer()
    consumer.start()
    return consumer  # type: ignore[return-value]


__all__ = [
    "PluginLivenessEntry",
    "PluginLivenessRegistry",
    "get_registry",
    "start_liveness_listener",
]
