"""Transport adapters for Magellon plugins.

Two transports live here today: the blocking pika-based ``RabbitmqClient``
used for plugin task dispatch, and the async JetStream
``NatsPublisher`` / ``NatsConsumer`` pair used for CloudEvents-wrapped
inter-service events. Consumers should import from the submodule they
need — the NATS import pulls in ``nats-py`` which is an optional dep.
"""
from __future__ import annotations

from magellon_sdk.transport.nats import NatsConsumer, NatsPublisher
from magellon_sdk.transport.rabbitmq import RabbitmqClient

__all__ = ["NatsConsumer", "NatsPublisher", "RabbitmqClient"]
