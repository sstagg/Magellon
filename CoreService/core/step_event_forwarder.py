"""NATS → ``job_event`` table bridge.

Subscribes to the ``magellon.job.*.step.*`` JetStream subject pattern
and hands each envelope to :class:`services.job_event_writer.JobEventWriter`.
Lifecycle events are persisted; progress events are filtered at the
writer (live-only). Idempotency is enforced at the DB layer (UNIQUE
index on ``event_id``) so re-delivery is safe.

This forwarder is the read-side of the event bus. The write-side lives
in plugins via :class:`magellon_sdk.events.StepEventPublisher`.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable

from sqlalchemy.orm import Session

from magellon_sdk.envelope import Envelope
from magellon_sdk.transport.nats import NatsConsumer

from services.job_event_writer import JobEventWriter

logger = logging.getLogger(__name__)


DEFAULT_SUBJECT_PATTERN = "magellon.job.*.step.*"
DEFAULT_STREAM = "MAGELLON_STEP_EVENTS"
DEFAULT_DURABLE = "core-job-event-writer"


class StepEventForwarder:
    """Glue between :class:`NatsConsumer` and :class:`JobEventWriter`.

    Construct with a consumer and a session factory — typically
    CoreService's ``database.session_local``. Call :meth:`start` from
    the FastAPI startup hook and :meth:`stop` from shutdown.
    """

    def __init__(
        self,
        consumer: NatsConsumer,
        session_factory: Callable[[], Session],
    ) -> None:
        self.consumer = consumer
        self.session_factory = session_factory

    async def handle(self, envelope: Envelope[Any]) -> None:
        """Per-event callback. Creates a scoped session per envelope so
        one bad event never poisons a long-lived session, and so
        :meth:`JobEventWriter.write`'s ``commit`` doesn't cross events."""
        db = self.session_factory()
        try:
            JobEventWriter(db).write(envelope)
        except Exception:
            logger.exception(
                "StepEventForwarder: writer failed for event %s", envelope.id
            )
            raise
        finally:
            db.close()

    async def start(self) -> bool:
        """Connect + subscribe. Returns False if the stream is absent
        (publisher hasn't started yet) — caller may retry later."""
        connected = await self.consumer.connect()
        if not connected:
            return False
        await self.consumer.subscribe(self.handle)
        logger.info(
            "StepEventForwarder started: subject=%s durable=%s",
            self.consumer.subject,
            self.consumer.durable_name,
        )
        return True

    async def stop(self) -> None:
        await self.consumer.close()
        logger.info("StepEventForwarder stopped")


def build_default_forwarder(session_factory: Callable[[], Session]) -> StepEventForwarder:
    """Factory using env-driven config.

    Env vars (all optional):
      NATS_URL                    default: nats://localhost:4222
      NATS_STEP_EVENTS_STREAM     default: MAGELLON_STEP_EVENTS
      NATS_STEP_EVENTS_SUBJECT    default: magellon.job.*.step.*
      NATS_STEP_EVENTS_DURABLE    default: core-job-event-writer
    """
    consumer = NatsConsumer(
        broker_url=os.environ.get("NATS_URL", "nats://localhost:4222"),
        stream=os.environ.get("NATS_STEP_EVENTS_STREAM", DEFAULT_STREAM),
        subject=os.environ.get("NATS_STEP_EVENTS_SUBJECT", DEFAULT_SUBJECT_PATTERN),
        durable_name=os.environ.get("NATS_STEP_EVENTS_DURABLE", DEFAULT_DURABLE),
    )
    return StepEventForwarder(consumer, session_factory)


__all__ = ["StepEventForwarder", "build_default_forwarder"]
