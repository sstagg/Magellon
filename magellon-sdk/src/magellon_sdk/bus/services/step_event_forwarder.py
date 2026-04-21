"""Step-event forwarder: bus.events deliveries → DB row + optional UI emit.

Relocated from ``CoreService/core/rmq_step_event_forwarder.py`` (MB5.4b).
Now transport-neutral — the forwarder owns the per-message work
(scoped DB session → writer → optional async downstream) and takes a
consumer-shaped seam that a caller wires to whichever transport the
deployment uses.

:class:`BusStepEventConsumer` adapts ``bus.events.subscribe`` to the
consumer shape (``start(callback)`` / ``stop()``) the forwarder
expects. Callers that want unit tests pass in a stub with the same
shape; production uses the bus adapter.

Idempotency is delegated to the writer's UNIQUE event_id index —
cross-channel re-delivery (RMQ mirror + NATS primary) is a no-op
at the DB.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, Protocol

from magellon_sdk.bus.interfaces import MessageBus, SubscriptionHandle
from magellon_sdk.bus.routes.event_route import StepEventRoute
from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)


DEFAULT_QUEUE_NAME = "core_step_events_queue"
DEFAULT_BINDING_KEY = "job.*.step.*"
DEFAULT_EXCHANGE = "magellon.events"

DownstreamHandler = Callable[[Envelope[Any]], Awaitable[None]]


class _ConsumerProtocol(Protocol):
    """Shape the forwarder needs from its consumer seam.

    Matches the pre-MB5.4b ``RabbitmqEventConsumer`` surface that the
    forwarder used to depend on, so test stubs + the new
    :class:`BusStepEventConsumer` are interchangeable.
    """

    queue_name: str
    binding_key: str
    exchange: str

    def start(self, callback: Callable[[Envelope], None]) -> None: ...
    def stop(self) -> None: ...


class BusStepEventConsumer:
    """Adapter: ``bus.events.subscribe`` → the forwarder's consumer shape.

    ``start(callback)`` registers the callback as a bus subscription
    handler on :data:`StepEventRoute.all` (matches today's wire
    pattern ``job.*.step.*``). ``stop()`` closes the subscription.

    The ``queue_name`` / ``binding_key`` / ``exchange`` attributes are
    cosmetic — they let the forwarder log a useful identity line at
    startup. Pre-MB5.4b they came from ``RabbitmqEventConsumer``;
    here they're constants that match the binder's topology.
    """

    queue_name = DEFAULT_QUEUE_NAME
    binding_key = DEFAULT_BINDING_KEY
    exchange = DEFAULT_EXCHANGE

    def __init__(self, bus: MessageBus) -> None:
        self._bus = bus
        self._handle: Optional[SubscriptionHandle] = None

    def start(self, callback: Callable[[Envelope], None]) -> None:
        if self._handle is not None:
            return
        self._handle = self._bus.events.subscribe(StepEventRoute.all(), callback)

    def stop(self) -> None:
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                logger.exception("BusStepEventConsumer: handle close failed")
            self._handle = None


class StepEventForwarder:
    """Per-message: scoped DB session → :class:`JobEventWriter` →
    optional async downstream → ack/nack.

    Idempotency is delegated to the writer's UNIQUE event_id index;
    a re-delivery from RMQ that the NATS path already persisted is
    silently a no-op at the DB.

    The ``downstream`` callback is async (e.g. a Socket.IO emit) but
    the consumer runs on a daemon thread — we cross the boundary via
    ``asyncio.run_coroutine_threadsafe`` against the asgi event loop
    captured at startup. Without ``loop``, downstream is skipped so
    the forwarder still works as a pure persistence sink.

    ``writer_factory`` is callable(session)→writer. Caller supplies
    this because the writer is CoreService-specific
    (``services.job_event_writer.JobEventWriter``). Tests can inject
    a stub writer.
    """

    def __init__(
        self,
        consumer: _ConsumerProtocol,
        session_factory: Callable[[], Any],
        *,
        writer_factory: Callable[[Any], Any],
        downstream: Optional[DownstreamHandler] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.consumer = consumer
        self.session_factory = session_factory
        self._writer_factory = writer_factory
        self.downstream = downstream
        self.loop = loop

    def handle(self, envelope: Envelope) -> None:
        db = self.session_factory()
        try:
            self._writer_factory(db).write(envelope)
        except Exception:
            logger.exception(
                "StepEventForwarder: writer failed for event %s", envelope.id
            )
            raise
        finally:
            db.close()

        # Cross thread → asgi loop boundary for the async downstream.
        # Fire-and-forget: a slow Socket.IO emit must not stall the
        # consumer thread, and downstream failure is non-fatal.
        if self.downstream is not None and self.loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.downstream(envelope), self.loop
                )
            except Exception:
                logger.exception(
                    "StepEventForwarder: failed to schedule downstream "
                    "for event %s — non-fatal, persistence unaffected",
                    envelope.id,
                )

    def start(self) -> None:
        self.consumer.start(self.handle)
        logger.info(
            "StepEventForwarder started: queue=%s binding=%s exchange=%s",
            self.consumer.queue_name,
            self.consumer.binding_key,
            self.consumer.exchange,
        )

    def stop(self) -> None:
        self.consumer.stop()
        logger.info("StepEventForwarder stopped")


__all__ = [
    "DEFAULT_BINDING_KEY",
    "DEFAULT_EXCHANGE",
    "DEFAULT_QUEUE_NAME",
    "BusStepEventConsumer",
    "DownstreamHandler",
    "StepEventForwarder",
]
