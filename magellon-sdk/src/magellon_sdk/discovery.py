"""Broker-based plugin discovery + heartbeat (P6).

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
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

import pika
from pydantic import BaseModel, Field

from magellon_sdk.categories.contract import (
    CategoryContract,
    announce_subject,
    heartbeat_subject,
)
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


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------

# All discovery messages share the events-style topic exchange — same
# fabric the step-event mirror uses. Using one exchange means an
# operator only has to point one consumer at one place to see "what
# plugins are alive right now."
DEFAULT_EXCHANGE = "magellon.plugins"


class DiscoveryPublisher:
    """Fire-and-forget publisher for announce + heartbeat messages.

    Owns its own short-lived RMQ connection so the publishing thread
    can be killed without affecting the plugin's main consumer
    connection. Failures are logged and swallowed: discovery is best-
    effort, not part of the plugin's correctness path.
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

    def announce(self, contract: CategoryContract, message: Announce) -> None:
        subject = announce_subject(contract.category.name, message.plugin_id)
        self._publish(subject, message.model_dump_json().encode("utf-8"))

    def heartbeat(self, contract: CategoryContract, message: Heartbeat) -> None:
        subject = heartbeat_subject(contract.category.name, message.plugin_id)
        self._publish(subject, message.model_dump_json().encode("utf-8"))

    def _publish(self, routing_key: str, body: bytes) -> None:
        try:
            self._ensure_open()
            self._channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=body,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                ),
            )
        except Exception as exc:
            # Discovery is best-effort. A broker hiccup must not take the
            # plugin's main consumer down with it; we'll try again on the
            # next heartbeat tick.
            logger.warning("DiscoveryPublisher: publish to %s failed: %s", routing_key, exc)
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
