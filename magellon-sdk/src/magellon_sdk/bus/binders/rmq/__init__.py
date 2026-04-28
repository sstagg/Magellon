"""RabbitMQ binder — the L4 implementation behind the bus.

See ``Documentation/MESSAGE_BUS_SPEC.md`` §3 (architecture) and §5
(binder SPI).
"""
from magellon_sdk.bus.binders.rmq.binder import RmqBinder
from magellon_sdk.bus.binders.rmq.topology import (
    EXCHANGE_EVENTS,
    EXCHANGE_PLUGINS,
    exchange_for_pattern,
    exchange_for_subject,
    glob_to_rmq_routing_key,
)

__all__ = [
    "EXCHANGE_EVENTS",
    "EXCHANGE_PLUGINS",
    "RmqBinder",
    "exchange_for_pattern",
    "exchange_for_subject",
    "glob_to_rmq_routing_key",
]
