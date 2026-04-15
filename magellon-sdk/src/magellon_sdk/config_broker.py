"""Broker-based dynamic configuration (P7).

Replaces Consul KV. The premise: configuration that needs to reach a
fleet of plugin replicas should ride the same broker the tasks do.
That keeps the moving parts down (no second service to babysit) and
removes the polling pattern Consul KV pushed us toward.

Two channels match the discovery layout:

  - ``magellon.plugins.config.<category>`` — settings every plugin in a
    category should pick up (e.g., a new GPFS root for all CTF plugins).

  - ``magellon.plugins.config.broadcast`` — settings every plugin should
    pick up regardless of category (e.g., a global log-level change).

A plugin's :class:`ConfigSubscriber` runs on its own daemon thread and
just buffers the latest merged settings under a lock. The harness
drains the buffer *between deliveries* and feeds it to
:meth:`PluginBase.configure` — so a config update never races a
running ``execute()`` call. The cost is one config-tick lag per
update, which is acceptable: ops never push config faster than the
slowest task in the queue.

Wire shape is intentionally permissive: ``settings`` is ``Dict[str,
Any]``. The category contract doesn't pin config schemas because
plugins inside a category can have wildly different knobs (CTFFind's
search range vs. gctf's iteration count). A schema would force the
category to know things only the plugin should know.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import pika
from pydantic import BaseModel, Field

from magellon_sdk.categories.contract import (
    CONFIG_BROADCAST_SUBJECT,
    CategoryContract,
    config_subject,
)
from magellon_sdk.discovery import DEFAULT_EXCHANGE

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


# ---------------------------------------------------------------------------
# Publisher (used by CoreService or an operator CLI)
# ---------------------------------------------------------------------------

class ConfigPublisher:
    """Fire-and-forget publisher for category + broadcast config pushes.

    Mirrors :class:`magellon_sdk.discovery.DiscoveryPublisher` — short-
    lived connection, best-effort error handling. Config is operational
    state, not part of any task's correctness path; a failed publish
    should log loudly but never crash the caller.
    """

    def __init__(
        self,
        settings: Any,
        *,
        exchange: str = DEFAULT_EXCHANGE,
    ) -> None:
        self.settings = settings
        self.exchange = exchange
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Any = None

    def _ensure_open(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return
        credentials = pika.PlainCredentials(
            self.settings.USER_NAME, self.settings.PASSWORD
        )
        params = pika.ConnectionParameters(
            host=self.settings.HOST_NAME,
            credentials=credentials,
            heartbeat=30,
        )
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.exchange_declare(
            exchange=self.exchange, exchange_type="topic", durable=True
        )

    def publish_to_category(
        self, contract: CategoryContract, settings: Dict[str, Any], *, version: Optional[int] = None
    ) -> None:
        target = contract.category.name.lower()
        msg = ConfigUpdate(target=target, settings=settings, version=version)
        self._publish(config_subject(contract.category.name), msg)

    def publish_broadcast(
        self, settings: Dict[str, Any], *, version: Optional[int] = None
    ) -> None:
        msg = ConfigUpdate(target="broadcast", settings=settings, version=version)
        self._publish(CONFIG_BROADCAST_SUBJECT, msg)

    def _publish(self, routing_key: str, message: ConfigUpdate) -> None:
        try:
            self._ensure_open()
            self._channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=message.model_dump_json().encode("utf-8"),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )
        except Exception as exc:
            logger.warning("ConfigPublisher: publish to %s failed: %s", routing_key, exc)
            self._reset()

    def _reset(self) -> None:
        if self._connection is not None:
            try:
                if not self._connection.is_closed:
                    self._connection.close()
            except Exception:
                pass
        self._connection = None
        self._channel = None

    def close(self) -> None:
        self._reset()


# ---------------------------------------------------------------------------
# Subscriber (used by PluginBrokerRunner)
# ---------------------------------------------------------------------------

ConfigCallback = Callable[[Dict[str, Any]], None]


class ConfigSubscriber:
    """Daemon-thread subscriber that buffers the latest merged settings.

    The subscriber owns its own RMQ connection so the plugin's main
    consumer is unaffected by config-channel hiccups. It binds an
    *exclusive, auto-delete* queue to both the category subject and
    the broadcast subject — exclusive so two replicas of the same
    plugin each get their own copy, auto-delete so a process exit
    cleans up after itself.

    Concurrency model: the consumer thread drops each delivery's
    ``settings`` into ``_pending`` under a lock, doing key-by-key
    last-write-wins. The harness calls :meth:`take_pending` between
    task deliveries; if the buffer is non-empty it gets handed off
    and cleared atomically. This avoids the obvious race where a
    config update fires while ``execute()`` is mid-flight.
    """

    def __init__(
        self,
        settings: Any,
        *,
        contract: CategoryContract,
        exchange: str = DEFAULT_EXCHANGE,
        queue_name: Optional[str] = None,
    ) -> None:
        self.settings = settings
        self.contract = contract
        self.exchange = exchange
        # Per-instance queue name keeps replicas separate. Random
        # suffix prevents collisions when a process restarts before
        # the broker has reaped the old auto-delete queue.
        self.queue_name = queue_name or f"magellon.plugins.config.{contract.category.name.lower()}.{uuid4().hex[:8]}"
        self._pending: Dict[str, Any] = {}
        self._last_version: Optional[int] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Any = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="config-sub")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._channel is not None:
            try:
                self._channel.stop_consuming()
            except Exception:
                pass
        if self._connection is not None:
            try:
                if not self._connection.is_closed:
                    self._connection.close()
            except Exception:
                pass

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

    # ------------------------------------------------------------------
    # Broker loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            credentials = pika.PlainCredentials(
                self.settings.USER_NAME, self.settings.PASSWORD
            )
            params = pika.ConnectionParameters(
                host=self.settings.HOST_NAME,
                credentials=credentials,
                heartbeat=30,
            )
            self._connection = pika.BlockingConnection(params)
            self._channel = self._connection.channel()
            self._channel.exchange_declare(
                exchange=self.exchange, exchange_type="topic", durable=True
            )
            self._channel.queue_declare(
                queue=self.queue_name, exclusive=True, auto_delete=True
            )
            self._channel.queue_bind(
                exchange=self.exchange,
                queue=self.queue_name,
                routing_key=config_subject(self.contract.category.name),
            )
            self._channel.queue_bind(
                exchange=self.exchange,
                queue=self.queue_name,
                routing_key=CONFIG_BROADCAST_SUBJECT,
            )

            def _on_message(ch, method, properties, body):
                try:
                    payload = json.loads(body.decode("utf-8"))
                    update = ConfigUpdate.model_validate(payload)
                    self.deliver(update)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as exc:
                    logger.warning("ConfigSubscriber: bad payload (%s) — dropping", exc)
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            self._channel.basic_consume(
                queue=self.queue_name, on_message_callback=_on_message
            )
            logger.info(
                "ConfigSubscriber: bound %s to %s + %s",
                self.queue_name,
                config_subject(self.contract.category.name),
                CONFIG_BROADCAST_SUBJECT,
            )
            self._channel.start_consuming()
        except Exception:
            if not self._stop.is_set():
                logger.exception("ConfigSubscriber: consume loop crashed")


__all__ = [
    "ConfigCallback",
    "ConfigPublisher",
    "ConfigSubscriber",
    "ConfigUpdate",
]
