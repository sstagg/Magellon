"""CoreService wrapper over :mod:`magellon_sdk.bus.services.step_event_forwarder`.

MB5.4b moved the forwarder logic (per-message DB write + optional
async downstream) into the SDK so any bus-based consumer can use it.
The CoreService-specific bits stay here:

- :class:`JobEventWriter` as the writer factory.
- :func:`build_default_rmq_forwarder` factory over the bus-backed
  consumer adapter.
- :class:`RmqStepEventForwarder` kept as a subclass of the SDK
  :class:`StepEventForwarder` so CoreService's existing callers
  (``main.py``, ``tests/test_rmq_step_event_forwarder.py``) keep
  their two-argument construction shape.

Pre-MB5.4b this module opened its own pika consumer via
``RabbitmqEventConsumer`` from ``magellon_sdk.transport.rabbitmq_events``.
Post-MB5.4b it wraps ``bus.events.subscribe`` on
:class:`StepEventRoute.all` via :class:`BusStepEventConsumer` —
binder owns the connection / ack / reconnect.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from magellon_sdk.bus import get_bus
from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.bus.services.step_event_forwarder import (
    DEFAULT_BINDING_KEY,
    DEFAULT_EXCHANGE,
    DEFAULT_QUEUE_NAME,
    BusStepEventConsumer,
    DownstreamHandler,
    StepEventForwarder,
)
from magellon_sdk.envelope import Envelope

from services.job_event_writer import JobEventWriter

logger = logging.getLogger(__name__)


class RmqStepEventForwarder(StepEventForwarder):
    """CoreService-flavoured forwarder: injects :class:`JobEventWriter`
    so the two-argument pre-MB5.4b constructor still works.

    ``RmqStepEventForwarder(consumer, session_factory, downstream=None, loop=None)``
    is preserved verbatim — existing tests and the ``main.py`` wiring
    need no edit.
    """

    def __init__(
        self,
        consumer: Any,
        session_factory: Callable[[], Session],
        downstream: Optional[DownstreamHandler] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        super().__init__(
            consumer,
            session_factory,
            writer_factory=JobEventWriter,
            downstream=downstream,
            loop=loop,
        )


def build_default_rmq_forwarder(
    rabbitmq_settings: Any = None,
    session_factory: Optional[Callable[[], Session]] = None,
    *,
    queue_name: str = DEFAULT_QUEUE_NAME,
    binding_key: str = DEFAULT_BINDING_KEY,
    exchange: str = DEFAULT_EXCHANGE,
    downstream: Optional[DownstreamHandler] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
    bus: Optional[MessageBus] = None,
) -> RmqStepEventForwarder:
    """Factory: construct a bus-backed consumer and wrap it in the
    CoreService forwarder.

    ``rabbitmq_settings``, ``queue_name``, ``binding_key``, ``exchange``
    are retained for backcompat with the pre-MB5.4b signature but no
    longer drive pika connection setup — the binder (installed via
    ``install_rmq_bus`` at CoreService startup) owns that. ``queue_name``
    and ``binding_key`` remain visible on the consumer for log/status
    output; they match the binder's default topology.

    ``session_factory`` is still required — the forwarder needs a
    session per delivery to hand the :class:`JobEventWriter`.
    """
    if session_factory is None:
        raise ValueError("build_default_rmq_forwarder requires session_factory")

    resolved_bus = bus if bus is not None else get_bus()
    consumer = BusStepEventConsumer(resolved_bus)
    # The consumer's default cosmetic attributes (queue_name / binding_key
    # / exchange) already match the pre-MB5.4b defaults — override only
    # if the caller explicitly passed a different value so custom
    # deployments that ran on non-default queue names still log honest.
    if queue_name != DEFAULT_QUEUE_NAME:
        consumer.queue_name = queue_name
    if binding_key != DEFAULT_BINDING_KEY:
        consumer.binding_key = binding_key
    if exchange != DEFAULT_EXCHANGE:
        consumer.exchange = exchange

    return RmqStepEventForwarder(
        consumer,
        session_factory,
        downstream=downstream,
        loop=loop,
    )


__all__ = [
    "DEFAULT_BINDING_KEY",
    "DEFAULT_EXCHANGE",
    "DEFAULT_QUEUE_NAME",
    "RmqStepEventForwarder",
    "build_default_rmq_forwarder",
]
