"""Compatibility shim — applies motioncor's pika heartbeat defaults on top of the SDK client.

The motioncor consumer historically hardcoded ``heartbeat=600`` and
``blocked_connection_timeout=300`` in its connection parameters to keep
long-running frame-transfer connections alive. Those values stay here as
a thin subclass so we don't need to touch motioncor's call sites.
"""
from magellon_sdk.transport.rabbitmq import RabbitmqClient as _BaseRabbitmqClient


class RabbitmqClient(_BaseRabbitmqClient):
    def __init__(self, settings):
        super().__init__(
            settings,
            heartbeat=600,
            blocked_connection_timeout=300,
        )


__all__ = ["RabbitmqClient"]
