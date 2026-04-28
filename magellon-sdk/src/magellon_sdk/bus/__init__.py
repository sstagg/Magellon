"""Magellon MessageBus — caller-facing API.

See ``Documentation/MESSAGE_BUS_SPEC.md`` for the design.
"""
from magellon_sdk.bus._facade import DefaultMessageBus, get_bus
from magellon_sdk.bus.interfaces import (
    Binder,
    ConsumerHandle,
    EventHandler,
    EventsBus,
    MessageBus,
    PatternRef,
    RouteRef,
    SubscriptionHandle,
    TaskHandler,
    TasksBus,
)
from magellon_sdk.bus.policy import (
    AuditLogConfig,
    PublishReceipt,
    TaskConsumerPolicy,
)

__all__ = [
    # policy
    "AuditLogConfig",
    "PublishReceipt",
    "TaskConsumerPolicy",
    # protocols (L2 + L3)
    "Binder",
    "ConsumerHandle",
    "EventHandler",
    "EventsBus",
    "MessageBus",
    "PatternRef",
    "RouteRef",
    "SubscriptionHandle",
    "TaskHandler",
    "TasksBus",
    # facade + registry
    "DefaultMessageBus",
    "get_bus",
]
