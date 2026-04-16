"""Magellon MessageBus — caller-facing API.

See ``Documentation/MESSAGE_BUS_SPEC_AND_PLAN.md`` for the design and
``Documentation/MESSAGE_BUS_EXECUTION_PLAN.md`` for the phased
migration.

MB1.1 lands Protocols + policy dataclasses. Concrete entry points
(``get_bus``, route value objects, mock binder) land in MB1.2 / MB1.3.
No production caller imports this package yet.
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
