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
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.orm import Session

from magellon_sdk.envelope import Envelope
from magellon_sdk.transport.nats import NatsConsumer

from services.job_event_writer import JobEventWriter

DownstreamHandler = Callable[[Envelope[Any]], Awaitable[None]]


async def log_step_event(envelope: Envelope[Any]) -> None:
    """Emit a one-line INFO log per step event.

    Sits in the downstream chain so the operator can watch events flow
    through CoreService logs without tailing RMQ/NATS separately.
    Lifecycle events also get a row in ``job_event`` (via
    :class:`JobEventWriter`); progress events are live-only and would
    otherwise be invisible from the backend log.
    """
    data: Any = envelope.data if isinstance(envelope.data, dict) else {}
    job_id = data.get("job_id", "?")
    task_id = data.get("task_id", "?")
    step = data.get("step", "?")
    short_type = envelope.type.replace("magellon.step.", "")
    extras = ""
    if short_type == "progress" and "percent" in data:
        extras = f" {data['percent']}%"
        if data.get("message"):
            extras += f" — {data['message']}"
    elif short_type == "failed":
        extras = f" — {data.get('error', '')}"
    elif short_type == "completed" and data.get("output_files"):
        extras = f" — {len(data['output_files'])} file(s)"
    logging.getLogger("magellon.step_events").info(
        "step_event: %s job=%s task=%s step=%s%s",
        short_type, job_id, task_id, step, extras,
    )


def chain_downstream(*handlers: DownstreamHandler) -> DownstreamHandler:
    """Run multiple downstream handlers in order for one envelope.

    Each handler is awaited; an exception in one is logged and swallowed
    so the next still runs (the writer already persisted the event, and
    we'd rather have a partial fan-out than drop everything).
    """
    async def _run(envelope: Envelope[Any]) -> None:
        for h in handlers:
            try:
                await h(envelope)
            except Exception:
                logger.exception(
                    "downstream handler %r failed for event %s",
                    getattr(h, "__qualname__", repr(h)), envelope.id,
                )
    return _run

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
        downstream: Optional[DownstreamHandler] = None,
    ) -> None:
        self.consumer = consumer
        self.session_factory = session_factory
        self.downstream = downstream

    async def handle(self, envelope: Envelope[Any]) -> None:
        """Per-event callback. Creates a scoped session per envelope so
        one bad event never poisons a long-lived session, and so
        :meth:`JobEventWriter.write`'s ``commit`` doesn't cross events.

        After persistence, if a ``downstream`` handler is configured
        (e.g. Socket.IO emit) it runs for *every* envelope — lifecycle
        and progress alike — so live progress still reaches the UI even
        though it isn't persisted."""
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

        if self.downstream is not None:
            try:
                await self.downstream(envelope)
            except Exception:
                logger.exception(
                    "StepEventForwarder: downstream handler failed for event %s — "
                    "non-fatal, event is already persisted",
                    envelope.id,
                )

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


def build_default_forwarder(
    session_factory: Callable[[], Session],
    downstream: Optional[DownstreamHandler] = None,
) -> StepEventForwarder:
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
    return StepEventForwarder(consumer, session_factory, downstream=downstream)


__all__ = ["StepEventForwarder", "build_default_forwarder", "chain_downstream"]
