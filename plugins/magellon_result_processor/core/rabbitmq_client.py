"""Compatibility shim — re-exports the shared pika client from magellon-sdk."""
from magellon_sdk.transport.rabbitmq import RabbitmqClient  # noqa: F401

__all__ = ["RabbitmqClient"]
