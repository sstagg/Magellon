"""Transport adapters for Magellon plugins.

Today this package provides the shared pika-based RabbitMQ client. Other
transports (NATS, HTTP) may land alongside it; consumers should import
from the submodule they need.
"""
from __future__ import annotations

from magellon_sdk.transport.rabbitmq import RabbitmqClient

__all__ = ["RabbitmqClient"]
