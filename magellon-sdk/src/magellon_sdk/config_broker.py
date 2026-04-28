"""Broker-based dynamic configuration (P7 + MB5.2 + persistent flag).

Replaces Consul KV. The premise: configuration that needs to reach a
fleet of plugin replicas should ride the same broker the tasks do.
That keeps the moving parts down (no second service to babysit) and
removes the polling pattern Consul KV pushed us toward.

Two channels match the discovery layout:

  - ``magellon.plugins.config.<category>`` — settings every plugin in a
    category should pick up (e.g., a new GPFS root for all CTF plugins).

  - ``magellon.plugins.config.broadcast`` — settings every plugin should
    pick up regardless of category (e.g., a global log-level change).

A plugin's :class:`ConfigSubscriber` runs on its own daemon thread
(binder-managed post-MB5.2) and just buffers the latest merged
settings under a lock. The harness drains the buffer *between
deliveries* and feeds it to :meth:`PluginBase.configure` — so a
config update never races a running ``execute()`` call. The cost is
one config-tick lag per update, which is acceptable: ops never push
config faster than the slowest task in the queue.

Wire shape is intentionally permissive: ``settings`` is ``Dict[str,
Any]``. The category contract doesn't pin config schemas because
plugins inside a category can have wildly different knobs (CTFFind's
search range vs. gctf's iteration count). A schema would force the
category to know things only the plugin should know.

**Persistence (``ConfigUpdate.persistent``).** A push marked
``persistent=True`` is also written to a per-replica local file by
the subscriber so the value survives a plugin restart. On boot the
subscriber loads the file and primes its buffer — the very first
``configure()`` call sees the persisted state. This solves the
"operator pushed max_defocus=5.0 last week, plugin restarted, lost
it" gap. It does NOT solve cross-replica consistency: a replica
that was offline during the push has a stale local copy, and a new
replica added later starts empty. The full fix is a centralized
config store fronting the bus (Spring Cloud Config / Consul KV
pattern) — tracked separately. See ``Documentation/BROKER_PATTERNS.md``
§8.3 for the gap discussion.

MB5.2 re-routed publisher + subscriber through the MessageBus
(``bus.events.publish`` / ``bus.events.subscribe``). The binder owns
the pika connection lifecycle; this module contains no transport
state. Wire format stays CloudEvents binary content mode — the AMQP
body is ``ConfigUpdate.model_dump_json()`` exactly as before.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.interfaces import MessageBus, SubscriptionHandle
from magellon_sdk.bus.routes.event_route import ConfigRoute
from magellon_sdk.categories.contract import (
    CONFIG_BROADCAST_SUBJECT,
    CategoryContract,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ConfigUpdate(BaseModel):
    """Single config push.

    ``settings`` is shallow-merged into the plugin's running config —
    keys not in the message are left alone, keys in the message
    overwrite. To clear a key, send it explicitly with a ``None``
    value (the plugin decides what that means).

    ``version`` lets the subscriber drop out-of-order deliveries.
    Optional because the simple "last write wins" mode is fine for
    the common case (a single operator pushing). Set it when a
    publisher runs in HA and ordering matters.
    """

    target: str
    """Either the lowercased category name (``"ctf"``) or the literal
    ``"broadcast"``. Mirrors the subject the message was published on
    so a subscriber receiving on the wildcard binding can tell which
    bucket the update came from."""

    settings: Dict[str, Any]
    ts: datetime = Field(default_factory=_now_utc)
    version: Optional[int] = None
    persistent: bool = False
    """When True, subscribers configured with a persisted-config path
    write these settings to disk so they survive a plugin restart.
    Subscribers without a path silently ignore the flag — they apply
    the settings in-memory like any other push.

    Use for operator-tuned runtime values that should hold across
    restarts (e.g., ``max_defocus`` adjusted during a session).
    Don't use for credentials or infrastructure config — those
    belong in env vars or YAML, where the deploy system can manage
    them. See ``Documentation/BROKER_PATTERNS.md`` §8.3."""


_ENVELOPE_SOURCE = "magellon/plugin/config"
_CONFIG_TYPE = "magellon.plugin.config.update.v1"


# ---------------------------------------------------------------------------
# Publisher (used by CoreService or an operator CLI)
# ---------------------------------------------------------------------------

class ConfigPublisher:
    """Fire-and-forget publisher for category + broadcast config pushes.

    Post-MB5.2 delegates to ``bus.events.publish`` on
    :class:`ConfigRoute.for_category` / :meth:`ConfigRoute.broadcast`.
    Failures are logged and swallowed — config is operational state,
    not part of any task's correctness path; a failed publish logs
    loudly but never crashes the caller.

    ``settings`` argument is retained for backcompat with pre-MB5.2
    callers; no longer consulted. Tests that want a mock bus pass
    it via the ``bus=`` kwarg.
    """

    def __init__(
        self,
        settings: Any = None,
        *,
        bus: Optional[MessageBus] = None,
    ) -> None:
        self._settings = settings
        self._bus = bus

    def _resolve_bus(self) -> MessageBus:
        return self._bus if self._bus is not None else get_bus()

    def publish_to_category(
        self,
        contract: CategoryContract,
        settings: Dict[str, Any],
        *,
        version: Optional[int] = None,
        persistent: bool = False,
    ) -> None:
        target = contract.category.name.lower()
        msg = ConfigUpdate(
            target=target,
            settings=settings,
            version=version,
            persistent=persistent,
        )
        self._publish(ConfigRoute.for_category(contract), msg)

    def publish_broadcast(
        self,
        settings: Dict[str, Any],
        *,
        version: Optional[int] = None,
        persistent: bool = False,
    ) -> None:
        msg = ConfigUpdate(
            target="broadcast",
            settings=settings,
            version=version,
            persistent=persistent,
        )
        self._publish(ConfigRoute.broadcast(), msg)

    def _publish(self, route: ConfigRoute, message: ConfigUpdate) -> None:
        try:
            envelope = Envelope.wrap(
                source=_ENVELOPE_SOURCE,
                type=_CONFIG_TYPE,
                subject=route.subject,
                data=message,
            )
            self._resolve_bus().events.publish(route, envelope)
        except Exception as exc:
            logger.warning("ConfigPublisher: publish to %s failed: %s", route.subject, exc)

    def close(self) -> None:
        """No-op. The binder owns the broker connection; nothing to
        clean up here. Retained for API symmetry with pre-MB5.2 callers."""
        return None


# ---------------------------------------------------------------------------
# Subscriber (used by PluginBrokerRunner)
# ---------------------------------------------------------------------------

ConfigCallback = Callable[[Dict[str, Any]], None]


class ConfigSubscriber:
    """Daemon-thread subscriber that buffers the latest merged settings.

    Post-MB5.2 the broker connection is the binder's job — this class
    subscribes via ``bus.events.subscribe(ConfigRoute.all(), handler)``
    and filters incoming updates by ``target`` so only pushes for
    this category (plus broadcasts) land in the buffer. That matches
    the pre-MB5.2 behavior where the broker-side bindings did the
    filtering.

    Concurrency model: the binder's consumer thread hands us each
    delivery; we drop the settings into ``_pending`` under a lock,
    key-by-key last-write-wins. The harness calls :meth:`take_pending`
    between task deliveries; if the buffer is non-empty it gets handed
    off and cleared atomically. This avoids the obvious race where a
    config update fires while ``execute()`` is mid-flight.

    ``settings`` argument retained for backcompat with pre-MB5.2
    callers; no longer consulted. ``queue_name`` retained as a no-op
    for the same reason.
    """

    def __init__(
        self,
        settings: Any = None,
        *,
        contract: CategoryContract,
        exchange: str = "magellon.plugins",
        queue_name: Optional[str] = None,
        bus: Optional[MessageBus] = None,
        persisted_path: Optional[Path] = None,
    ) -> None:
        self._settings = settings
        self.contract = contract
        self.exchange = exchange  # Legacy; binder owns exchange naming now.
        self.queue_name = queue_name  # Legacy; binder picks a per-subscription queue.
        self._bus = bus
        self._persisted_path = persisted_path

        self._target = contract.category.name.lower()
        self._pending: Dict[str, Any] = {}
        # Cumulative state of persistent pushes only — written to disk on each
        # persistent delivery, loaded from disk on boot. Independent from
        # _pending (which is the runner's drain buffer): a non-persistent push
        # lands in _pending but not in _persisted_state.
        self._persisted_state: Dict[str, Any] = {}
        self._last_version: Optional[int] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._handle: Optional[SubscriptionHandle] = None

        if self._persisted_path is not None:
            self._load_persisted()

    def _resolve_bus(self) -> MessageBus:
        return self._bus if self._bus is not None else get_bus()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Register the bus subscription. Idempotent — calling twice
        leaves the existing handle in place."""
        if self._handle is not None:
            return
        try:
            self._handle = self._resolve_bus().events.subscribe(
                ConfigRoute.all(), self._on_event
            )
            logger.info(
                "ConfigSubscriber: subscribed to magellon.plugins.config.> "
                "(filtering for target=%s|broadcast)",
                self._target,
            )
        except Exception:
            logger.exception("ConfigSubscriber: subscribe failed")

    def stop(self) -> None:
        self._stop.set()
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                logger.exception("ConfigSubscriber: handle close failed")
            self._handle = None

    def take_pending(self) -> Optional[Dict[str, Any]]:
        """Return + clear buffered settings, or ``None`` if nothing new.

        The harness calls this between task deliveries. Returning
        ``None`` rather than an empty dict lets the harness skip the
        ``configure()`` call entirely on idle ticks instead of churning
        through a no-op every time.
        """
        with self._lock:
            if not self._pending:
                return None
            out = self._pending
            self._pending = {}
            return out

    def deliver(self, message: ConfigUpdate) -> None:
        """Inject a config update directly. Public for tests + for any
        in-process publisher that wants to skip the broker round-trip."""
        snapshot_to_write: Optional[Dict[str, Any]] = None
        with self._lock:
            if (
                message.version is not None
                and self._last_version is not None
                and message.version <= self._last_version
            ):
                # Out-of-order or duplicate — drop.
                return
            if message.version is not None:
                self._last_version = message.version
            self._pending.update(message.settings)
            if message.persistent and self._persisted_path is not None:
                self._persisted_state.update(message.settings)
                snapshot_to_write = dict(self._persisted_state)
        # File I/O happens outside the lock — never hold the buffer
        # lock across a disk write. Best-effort: failure is logged
        # but doesn't disturb the in-memory apply path.
        if snapshot_to_write is not None:
            self._write_persisted(snapshot_to_write)

    def _load_persisted(self) -> None:
        """Read persisted settings from disk and prime the buffer.

        Called once at construction when a path is configured. The
        loaded state goes into both ``_persisted_state`` (so the next
        persistent push merges with it instead of overwriting) and
        ``_pending`` (so the first ``take_pending()`` after boot
        returns the persisted values for the runner to apply via
        ``plugin.configure(...)``).

        A missing file or malformed JSON is logged and treated as
        "no persisted state" — the plugin boots from YAML defaults
        as before. We never raise from here; failing to load
        persisted state must not prevent the plugin from starting.
        """
        assert self._persisted_path is not None  # narrow Optional for mypy
        try:
            if not self._persisted_path.exists():
                return
            text = self._persisted_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "ConfigSubscriber: cannot read persisted config %s: %s — "
                "starting with no persisted state",
                self._persisted_path, exc,
            )
            return

        try:
            loaded = json.loads(text)
        except ValueError as exc:
            logger.warning(
                "ConfigSubscriber: persisted config %s is not valid JSON: %s — "
                "starting with no persisted state",
                self._persisted_path, exc,
            )
            return

        if not isinstance(loaded, dict):
            logger.warning(
                "ConfigSubscriber: persisted config %s is not a JSON object — "
                "starting with no persisted state",
                self._persisted_path,
            )
            return

        with self._lock:
            self._persisted_state = dict(loaded)
            self._pending.update(loaded)
        logger.info(
            "ConfigSubscriber: loaded %d persisted setting(s) from %s",
            len(loaded), self._persisted_path,
        )

    def _write_persisted(self, state: Dict[str, Any]) -> None:
        """Atomic write via temp file + rename.

        ``Path.replace`` is atomic on POSIX and on Windows (since
        Python 3.3 it maps to ``MoveFileExW(REPLACE_EXISTING)``), so
        a crash mid-write leaves either the old file or the new
        file — never a half-written one. Failure to write is logged
        but never raises; persistence is best-effort, not part of
        the task correctness path.
        """
        assert self._persisted_path is not None
        try:
            self._persisted_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._persisted_path.with_suffix(
                self._persisted_path.suffix + ".tmp"
            )
            tmp.write_text(
                json.dumps(state, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            tmp.replace(self._persisted_path)
            logger.info(
                "ConfigSubscriber: persisted %d setting(s) to %s",
                len(state), self._persisted_path,
            )
        except OSError as exc:
            logger.warning(
                "ConfigSubscriber: failed to persist config to %s: %s",
                self._persisted_path, exc,
            )

    # ------------------------------------------------------------------
    # Bus handler
    # ------------------------------------------------------------------

    def _on_event(self, envelope: Envelope) -> None:
        """Handle one config-push delivery from the bus.

        The wildcard subscription means we receive every category's
        pushes; filter by ``target`` so only our category + broadcasts
        make it into the buffer. Malformed payloads raise
        :class:`PermanentError` so the binder routes them to the DLQ
        instead of redelivering forever — a bad wire shape won't decode
        on retry either.
        """
        try:
            update = ConfigUpdate.model_validate(envelope.data)
        except Exception as exc:
            raise PermanentError(f"ConfigSubscriber: undecodable payload: {exc}") from exc

        if update.target not in (self._target, "broadcast"):
            # Different category's push — acked silently (return None).
            return

        self.deliver(update)


__all__ = [
    "ConfigCallback",
    "ConfigPublisher",
    "ConfigSubscriber",
    "ConfigUpdate",
]
