"""RabbitMQ → ``job_event`` table bridge.

Sibling of :class:`core.step_event_forwarder.StepEventForwarder`.
NATS is the exploration channel; RMQ is the operational fabric. Both
land the *same* CloudEvents-id envelope into the same ``job_event``
row — the UNIQUE constraint on ``event_id`` makes cross-channel
re-delivery a no-op.

Runs on a daemon thread (matches the existing motioncor consumer
pattern). The Socket.IO live-emit path is currently driven from the
NATS forwarder only; if you need RMQ→UI as well, lift the optional
loop-aware downstream from :mod:`core.step_event_forwarder` and pass
``asyncio.run_coroutine_threadsafe(emit_step_event(env), loop)`` here.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.orm import Session

from magellon_sdk.envelope import Envelope
from magellon_sdk.transport.rabbitmq_events import (
    DEFAULT_EXCHANGE,
    RabbitmqEventConsumer,
)

from services.job_event_writer import JobEventWriter

logger = logging.getLogger(__name__)


DEFAULT_QUEUE_NAME = "core_step_events_queue"
DEFAULT_BINDING_KEY = "job.*.step.*"

DownstreamHandler = Callable[[Envelope[Any]], Awaitable[None]]


class RmqStepEventForwarder:
    """Per-message: scoped DB session → JobEventWriter → optional
    async downstream → ack/nack.

    Idempotency is delegated to the writer's UNIQUE event_id index;
    a re-delivery from RMQ that the NATS path already persisted is
    silently a no-op.

    The ``downstream`` callback is async (e.g.
    :func:`core.socketio_server.emit_step_event`) but the consumer
    runs on a daemon thread — we cross the boundary via
    ``asyncio.run_coroutine_threadsafe`` against the asgi event
    loop captured at startup. Without ``loop``, downstream is
    skipped (no-op) so the forwarder still works as a pure
    persistence sink.
    """

    def __init__(
        self,
        consumer: RabbitmqEventConsumer,
        session_factory: Callable[[], Session],
        downstream: Optional[DownstreamHandler] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.consumer = consumer
        self.session_factory = session_factory
        self.downstream = downstream
        self.loop = loop

    def handle(self, envelope: Envelope) -> None:
        db = self.session_factory()
        try:
            JobEventWriter(db).write(envelope)
        except Exception:
            logger.exception(
                "RmqStepEventForwarder: writer failed for event %s", envelope.id
            )
            raise
        finally:
            db.close()

        # Cross thread → asgi loop boundary for the async downstream.
        # Fire-and-forget: a slow Socket.IO emit must not stall the
        # RMQ consumer thread, and downstream failure is non-fatal.
        if self.downstream is not None and self.loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.downstream(envelope), self.loop
                )
            except Exception:
                logger.exception(
                    "RmqStepEventForwarder: failed to schedule downstream "
                    "for event %s — non-fatal, persistence unaffected",
                    envelope.id,
                )

    def start(self) -> None:
        self.consumer.start(self.handle)
        logger.info(
            "RmqStepEventForwarder started: queue=%s binding=%s exchange=%s",
            self.consumer.queue_name,
            self.consumer.binding_key,
            self.consumer.exchange,
        )

    def stop(self) -> None:
        self.consumer.stop()
        logger.info("RmqStepEventForwarder stopped")


def build_default_rmq_forwarder(
    rabbitmq_settings,
    session_factory: Callable[[], Session],
    *,
    queue_name: str = DEFAULT_QUEUE_NAME,
    binding_key: str = DEFAULT_BINDING_KEY,
    exchange: str = DEFAULT_EXCHANGE,
    downstream: Optional[DownstreamHandler] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> RmqStepEventForwarder:
    """Factory: construct the consumer from CoreService's
    :class:`RabbitMQSettings` and wrap it in the forwarder.

    Pass ``downstream`` + ``loop`` together to enable live
    UI emission from the RMQ path. Without both, the forwarder
    is a pure persistence sink.
    """
    consumer = RabbitmqEventConsumer(
        rabbitmq_settings,
        exchange=exchange,
        queue_name=queue_name,
        binding_key=binding_key,
    )
    return RmqStepEventForwarder(
        consumer,
        session_factory,
        downstream=downstream,
        loop=loop,
    )


__all__ = [
    "DEFAULT_BINDING_KEY",
    "DEFAULT_QUEUE_NAME",
    "RmqStepEventForwarder",
    "build_default_rmq_forwarder",
]
