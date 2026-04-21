"""Transport adapters for Magellon plugins.

Post-MB6.2 the only transport module that lives here is the async
JetStream ``NatsPublisher`` / ``NatsConsumer`` pair. The blocking
pika client moved to :mod:`magellon_sdk.bus.binders.rmq._client` as a
binder-private implementation detail — callers that need to publish
on RMQ should use ``bus.tasks.send`` / ``bus.events.publish`` via
the MessageBus, not the raw client.
"""
from __future__ import annotations

from magellon_sdk.transport.nats import NatsConsumer, NatsPublisher

__all__ = ["NatsConsumer", "NatsPublisher"]
