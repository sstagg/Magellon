"""Broker-based plugin discovery + heartbeat (P6 + MB5.1).

**Plugin authors should not import from this module.** It's the
announce / heartbeat wiring that :class:`PluginBrokerRunner` uses
internally. Plugins that need to announce themselves do so by
running a ``PluginBrokerRunner`` — the runner wires up discovery
for them. Reaching :class:`DiscoveryPublisher` directly bypasses
the runner's lifecycle management and is explicitly NOT part of
the public contract (see ``magellon-sdk/CONTRACT.md`` §3).

:class:`Announce` and :class:`Heartbeat` Pydantic models ARE public
— a host that receives these messages needs to decode them. Those
shapes are part of the wire contract and frozen behind SemVer like
any other public Pydantic model.

Replaces Consul service registration. The premise: a plugin connecting
to RabbitMQ already proves its existence to the broker — anything that
requires a *separate* registration step (Consul, etcd) is duplicate
state that can drift.

Two channels:

  - ``magellon.plugins.announce.<category>.<plugin>`` — published once
    when the plugin starts up (and again on reconnect). Carries the
    full :class:`PluginManifest` so a late-joining CoreService instance
    can reconstruct the registry without restarting plugins.

  - ``magellon.plugins.heartbeat.<category>.<plugin>`` — published on a
    timer. Carries a compact :class:`Heartbeat` record so the manager
    can age out plugins that stop pulsing (process crash, container
    OOM-kill, network partition).

Both are pure pub/sub on a topic exchange — no request/response. A
listening manager subscribes with a wildcard binding key
(``magellon.plugins.heartbeat.#``) and updates an in-memory liveness
table. Persisting that table is out of scope; the source of truth
stays in the broker stream.

MB5.1 re-routed the publisher through ``bus.events.publish`` on
:class:`AnnounceRoute` / :class:`HeartbeatRoute`. The binder's
CloudEvents binary content mode means the AMQP body is still the
``Announce``/``Heartbeat`` JSON (metadata rides in ``ce-*`` headers),
so consumers decoding the body with ``Announce.model_validate_json``
keep working without change. That lets the subscriber side (liveness
registry) migrate separately in MB5.4a.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.routes.event_route import AnnounceRoute, HeartbeatRoute
from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.envelope import Envelope
from magellon_sdk.models.manifest import PluginManifest

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Heartbeat(BaseModel):
    """Compact liveness pulse.

    Kept small on purpose — these are emitted on a timer, sometimes
    every few seconds, across N plugins. Putting the manifest in here
    would pointlessly multiply broker bytes; the announce channel
    already carries that.
    """

    plugin_id: str
    """Matches PluginInfo.name (and the provenance plugin_id on results)."""

    plugin_version: str

    category: str
    """Lowercased TaskCategory name — same convention as the subject path."""

    instance_id: str = Field(default_factory=lambda: str(uuid4()))
    """Per-process random id. Lets a manager distinguish two replicas
    of the same plugin running in parallel."""

    ts: datetime = Field(default_factory=_now_utc)

    status: str = "ready"
    """Free-form status string — 'ready', 'busy', 'draining'. The
    manager treats this as a hint, not a state machine."""


class Announce(BaseModel):
    """One-shot manifest publish at plugin startup or reconnect.

    Wraps :class:`PluginManifest` with the same instance_id / category
    fields the heartbeat carries so the manager can correlate the
    two streams trivially.
    """

    plugin_id: str
    plugin_version: str
    category: str
    instance_id: str = Field(default_factory=lambda: str(uuid4()))
    ts: datetime = Field(default_factory=_now_utc)
    manifest: PluginManifest
    task_queue: Optional[str] = None
    """Routing key (RMQ) / subject the plugin consumes TaskMessage deliveries
    from. Added in SDK 1.1 so a dispatcher can target a specific
    implementation when multiple impls coexist in the same category
    (hub phase H1). ``None`` for older plugins or plugins that don't
    consume tasks; in that case the dispatcher falls back to the legacy
    category-scoped queue."""
    backend_id: Optional[str] = None
    """Substitutable identity within the category (SDK 1.3+).

    Mirrors :attr:`PluginManifest.backend_id` so the liveness registry
    can index by ``(category, backend_id)`` without unpacking the
    manifest. Two announces with the same ``(category, backend_id)``
    but different ``plugin_version`` are flagged as a duplicate-backend
    conflict; pick a different id or upgrade in lockstep."""
    http_endpoint: Optional[str] = None
    """Base URL of the plugin's FastAPI host (PT-1, 2026-05-04).

    Format: ``http://<host>:<port>``. When ``None`` the plugin doesn't
    expose synchronous HTTP — bus dispatch (RMQ / NATS) is the only
    way to reach it. Plugins that advertise :attr:`Capability.SYNC`
    or :attr:`Capability.PREVIEW` MUST set this.

    CoreService's sync_dispatcher reads this to route low-latency
    interactive calls (preview, retune, sync /execute) directly to
    the plugin process without round-tripping through the broker."""


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

# Legacy constant exported for modules that imported it before MB5.1
# (``config_broker.py`` did this pre-MB5.2). Kept as a deprecated
# re-export — the RMQ binder owns exchange naming via
# ``magellon_sdk.bus.binders.rmq.topology``. Remove once MB6.2 has
# landed and no external module imports this.
DEFAULT_EXCHANGE = "magellon.plugins"

_ENVELOPE_SOURCE = "magellon/plugin/discovery"
_ANNOUNCE_TYPE = "magellon.plugin.announce.v1"
_HEARTBEAT_TYPE = "magellon.plugin.heartbeat.v1"


class DiscoveryPublisher:
    """Fire-and-forget publisher for announce + heartbeat messages.

    Delegates to ``bus.events.publish`` on :class:`AnnounceRoute` /
    :class:`HeartbeatRoute`. Failures are logged and swallowed —
    discovery is best-effort, not part of the plugin's correctness
    path. The bus's own RMQ binder owns the pika connection + its
    lifecycle; this class carries no transport state of its own.

    Constructor signatures kept as-is for backcompat with pre-MB5.1
    callers (``lifecycle.py``, test harnesses). The ``settings`` arg
    is no longer consulted — the bus was already configured at
    startup from the same settings. A future PR can drop the
    argument once all callers stop passing it.

    Tests that want a mock bus pass it via the ``bus=`` kwarg.
    """

    def __init__(
        self,
        settings: Any = None,
        *,
        bus: Optional[MessageBus] = None,
    ) -> None:
        # settings is legacy — retained so the pre-MB5.1 call site
        # (DiscoveryPublisher(settings)) keeps working during the
        # migration chain.
        self._settings = settings
        self._bus = bus

    def _resolve_bus(self) -> MessageBus:
        return self._bus if self._bus is not None else get_bus()

    def announce(self, contract: CategoryContract, message: Announce) -> None:
        route = AnnounceRoute.for_plugin(contract, message.plugin_id)
        self._publish(route, _ANNOUNCE_TYPE, message)

    def heartbeat(self, contract: CategoryContract, message: Heartbeat) -> None:
        route = HeartbeatRoute.for_plugin(contract, message.plugin_id)
        self._publish(route, _HEARTBEAT_TYPE, message)

    def _publish(self, route: Any, event_type: str, data: BaseModel) -> None:
        try:
            envelope = Envelope.wrap(
                source=_ENVELOPE_SOURCE,
                type=event_type,
                subject=route.subject,
                data=data,
            )
            self._resolve_bus().events.publish(route, envelope)
        except Exception as exc:
            # Discovery is best-effort. A broker hiccup must not take the
            # plugin's main consumer down with it; we'll try again on the
            # next heartbeat tick.
            logger.warning(
                "DiscoveryPublisher: publish to %s failed: %s", route.subject, exc
            )

    def close(self) -> None:
        """No-op. The binder owns the broker connection; nothing for
        the publisher itself to clean up. Retained for API symmetry
        with pre-MB5.1 callers."""
        return None


# ---------------------------------------------------------------------------
# Heartbeat thread
# ---------------------------------------------------------------------------

class HeartbeatLoop:
    """Periodic heartbeat publisher running on a daemon thread.

    Started by :class:`PluginBrokerRunner` after the consumer is up.
    Publishes a fresh :class:`Heartbeat` every ``interval_seconds``
    until ``stop()`` is called. Safe to ``stop()`` more than once.
    """

    def __init__(
        self,
        *,
        publisher: DiscoveryPublisher,
        contract: CategoryContract,
        plugin_id: str,
        plugin_version: str,
        instance_id: str,
        interval_seconds: float = 15.0,
    ) -> None:
        self.publisher = publisher
        self.contract = contract
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.instance_id = instance_id
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        # First pulse goes immediately — manager picks the plugin up
        # without waiting one full interval.
        while not self._stop.is_set():
            try:
                self.publisher.heartbeat(
                    self.contract,
                    Heartbeat(
                        plugin_id=self.plugin_id,
                        plugin_version=self.plugin_version,
                        category=self.contract.category.name.lower(),
                        instance_id=self.instance_id,
                    ),
                )
            except Exception as exc:
                logger.warning("HeartbeatLoop: publish failed: %s", exc)
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()


__all__ = [
    "Announce",
    "DEFAULT_EXCHANGE",
    "DiscoveryPublisher",
    "Heartbeat",
    "HeartbeatLoop",
]
