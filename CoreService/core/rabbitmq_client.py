"""Compatibility shim — re-exports the shared pika client from magellon-sdk.

Historic copies lived in each plugin and here. They now share one
implementation at ``magellon_sdk.transport.rabbitmq``.
"""
from magellon_sdk.transport.rabbitmq import RabbitmqClient  # noqa: F401

__all__ = ["RabbitmqClient"]
