"""Bus services — transport-neutral subscribers that compose over the
caller-supplied MessageBus.

This package holds small, reusable subscribers that every deployment
of the Magellon bus will typically want. They do not import ``pika``
or any other transport SDK — they take a :class:`MessageBus` by
argument and delegate to ``bus.tasks.consumer`` / ``bus.events.subscribe``.
"""
from magellon_sdk.bus.services.liveness_registry import (
    LivenessListener,
    PluginLivenessEntry,
    PluginLivenessRegistry,
    get_registry,
    start_liveness_listener,
)
from magellon_sdk.bus.services.result_consumer import (
    ResultHandler,
    result_consumer_engine,
    start_result_consumers,
)
from magellon_sdk.bus.services.step_event_forwarder import (
    BusStepEventConsumer,
    DownstreamHandler,
    StepEventForwarder,
)

__all__ = [
    "BusStepEventConsumer",
    "DownstreamHandler",
    "LivenessListener",
    "PluginLivenessEntry",
    "PluginLivenessRegistry",
    "ResultHandler",
    "StepEventForwarder",
    "get_registry",
    "result_consumer_engine",
    "start_liveness_listener",
    "start_result_consumers",
]
