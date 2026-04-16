"""Exchange, queue, and subject-glob topology for the RMQ binder.

Two topic exchanges carry all event traffic. Work queues are on the
default (direct) exchange, routed by queue name.

- ``magellon.plugins`` — announce, heartbeat, config (matches today's
  ``DiscoveryPublisher`` / ``ConfigPublisher`` usage)
- ``magellon.events``  — step events (matches today's
  ``RabbitmqEventPublisher`` usage)

Kept separate so a wildcard subscription on one doesn't incidentally
catch traffic from the other.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pika.channel

logger = logging.getLogger(__name__)


EXCHANGE_PLUGINS = "magellon.plugins"
"""Topic exchange for plugin lifecycle: announce / heartbeat / config."""

EXCHANGE_EVENTS = "magellon.events"
"""Topic exchange for job-scoped step events."""


def exchange_for_subject(subject: str) -> str:
    """Pick the exchange an event subject lives on.

    ``magellon.plugins.*`` goes on ``magellon.plugins``; everything
    else (``job.*.step.*`` today) on ``magellon.events``.
    """
    if subject.startswith("magellon.plugins."):
        return EXCHANGE_PLUGINS
    return EXCHANGE_EVENTS


def exchange_for_pattern(glob: str) -> str:
    """Same rule as :func:`exchange_for_subject`, applied to a glob."""
    if glob.startswith("magellon.plugins."):
        return EXCHANGE_PLUGINS
    return EXCHANGE_EVENTS


def glob_to_rmq_routing_key(glob: str) -> str:
    """Translate NATS-style ``>`` to AMQP ``#``.

    NATS ``>`` matches one-or-more tail segments; AMQP ``#`` matches
    zero-or-more. For our routes the tail is never empty in practice,
    so the looser AMQP semantic is safe — no false positives.

    Single-segment ``*`` is identical in both.
    """
    return glob.replace(">", "#")


def declare_event_exchanges(channel: "pika.channel.Channel") -> None:
    """Declare the two topic exchanges the binder publishes events on.

    Idempotent per AMQP semantics — redeclaring with identical args
    is a no-op. Called once on binder ``start()``.
    """
    channel.exchange_declare(
        exchange=EXCHANGE_PLUGINS,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare(
        exchange=EXCHANGE_EVENTS,
        exchange_type="topic",
        durable=True,
    )
    logger.info(
        "RmqBinder: declared event exchanges %s, %s",
        EXCHANGE_PLUGINS,
        EXCHANGE_EVENTS,
    )


__all__ = [
    "EXCHANGE_EVENTS",
    "EXCHANGE_PLUGINS",
    "declare_event_exchanges",
    "exchange_for_pattern",
    "exchange_for_subject",
    "glob_to_rmq_routing_key",
]
