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

import logging
from typing import Callable

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


class RmqStepEventForwarder:
    """Per-message: scoped DB session → JobEventWriter → ack/nack.

    Idempotency is delegated to the writer's UNIQUE event_id index;
    a re-delivery from RMQ that the NATS path already persisted is
    silently a no-op.
    """

    def __init__(
        self,
        consumer: RabbitmqEventConsumer,
        session_factory: Callable[[], Session],
    ) -> None:
        self.consumer = consumer
        self.session_factory = session_factory

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
) -> RmqStepEventForwarder:
    """Factory: construct the consumer from CoreService's
    :class:`RabbitMQSettings` and wrap it in the forwarder."""
    consumer = RabbitmqEventConsumer(
        rabbitmq_settings,
        exchange=exchange,
        queue_name=queue_name,
        binding_key=binding_key,
    )
    return RmqStepEventForwarder(consumer, session_factory)


__all__ = [
    "DEFAULT_BINDING_KEY",
    "DEFAULT_QUEUE_NAME",
    "RmqStepEventForwarder",
    "build_default_rmq_forwarder",
]
