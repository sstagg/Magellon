"""Step-event payload schemas, publisher helpers, and a lazy factory.

Background
----------

Today, progress from an *in-process* plugin reaches the browser via
``JobReporter`` → ``JobManager`` → ``emit_job_update``. Progress from
an *external* (RabbitMQ-dispatched) plugin is invisible until the
final ``TaskResultDto`` lands, which makes the UI look frozen for
minutes at a time during long MotionCor runs.

The plan (see ``Documentation/MESSAGES_AND_EVENTS.md`` §2.3 and §4):
plugins publish ``magellon.step.*`` CloudEvents on NATS JetStream,
CoreService runs a consumer that forwards them to Socket.IO room
``job:<job_id>``. This module ships the publisher half — the
CloudEvents data-payload schemas and a thin ``StepEventPublisher``
helper that every plugin can share.

The CoreService-side consumer (Socket.IO forwarder) is the follow-up.

Subject convention
------------------

``magellon.job.<job_id>.step.<step>``

- Per-job wildcard: ``magellon.job.<job_id>.step.*`` — all events for one job
- Per-step wildcard: ``magellon.job.*.step.ctf`` — all CTF events across jobs

This is the pattern Phase 4 planned; plugins shouldn't hand-roll their
own subject layout.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)


# ---- Event type constants (CloudEvents ``type`` field) ----

STEP_STARTED = "magellon.step.started"
STEP_PROGRESS = "magellon.step.progress"
STEP_COMPLETED = "magellon.step.completed"
STEP_FAILED = "magellon.step.failed"

STEP_EVENT_TYPES = frozenset({STEP_STARTED, STEP_PROGRESS, STEP_COMPLETED, STEP_FAILED})


# ---- Event data payloads (the ``data`` field on the CloudEvents envelope) ----


class _StepBase(BaseModel):
    """Common fields across every step event.

    ``step`` is the plugin's short name — ``"ctf"``, ``"motioncor"`` —
    not the display name. It doubles as the NATS subject suffix, so
    keep it lowercase and alnum/underscore only.
    """

    model_config = ConfigDict(extra="allow")

    job_id: UUID
    task_id: Optional[UUID] = None
    step: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StepStarted(_StepBase):
    pass


class StepProgress(_StepBase):
    percent: float = Field(ge=0.0, le=100.0)
    message: Optional[str] = None


class StepCompleted(_StepBase):
    output_files: Optional[List[str]] = None


class StepFailed(_StepBase):
    error: str


# ---- Subject helper ----


def step_subject(job_id: UUID | str, step: str) -> str:
    """Build the NATS subject for a step event.

    Normalizes ``job_id`` to string form so UUIDs and already-stringified
    IDs behave the same.
    """
    return f"magellon.job.{job_id}.step.{step}"


# ---- Publisher helper ----


class StepEventPublisher:
    """Thin wrapper that turns a plugin's ``publish(step, data)`` calls
    into CloudEvents envelopes on the right NATS subject.

    Decouples plugin code from envelope wiring — plugins call
    ``await pub.started(job_id, task_id, step="ctf")`` and get a
    correctly-formed ``magellon.step.started`` CloudEvent with the
    canonical subject.

    ``nats_publisher`` is any object exposing ``async publish(subject,
    envelope)`` — in production it's a :class:`NatsPublisher`, in unit
    tests a ``MagicMock`` or simple recorder works.

    ``plugin_name`` becomes the CloudEvents ``source`` —
    ``magellon/plugins/<name>``. Keep it stable across releases so
    consumers can filter by source.
    """

    def __init__(self, nats_publisher: Any, *, plugin_name: str) -> None:
        self._pub = nats_publisher
        self._source = f"magellon/plugins/{plugin_name}"

    async def started(self, *, job_id: UUID, step: str, task_id: Optional[UUID] = None) -> None:
        await self._emit(STEP_STARTED, StepStarted(job_id=job_id, task_id=task_id, step=step))

    async def progress(
        self,
        *,
        job_id: UUID,
        step: str,
        percent: float,
        message: Optional[str] = None,
        task_id: Optional[UUID] = None,
    ) -> None:
        await self._emit(
            STEP_PROGRESS,
            StepProgress(job_id=job_id, task_id=task_id, step=step, percent=percent, message=message),
        )

    async def completed(
        self,
        *,
        job_id: UUID,
        step: str,
        task_id: Optional[UUID] = None,
        output_files: Optional[List[str]] = None,
    ) -> None:
        await self._emit(
            STEP_COMPLETED,
            StepCompleted(job_id=job_id, task_id=task_id, step=step, output_files=output_files),
        )

    async def failed(
        self,
        *,
        job_id: UUID,
        step: str,
        error: str,
        task_id: Optional[UUID] = None,
    ) -> None:
        await self._emit(
            STEP_FAILED,
            StepFailed(job_id=job_id, task_id=task_id, step=step, error=error),
        )

    async def _emit(self, event_type: str, data: _StepBase) -> None:
        subject = step_subject(data.job_id, data.step)
        envelope = Envelope.wrap(
            source=self._source,
            type=event_type,
            subject=subject,
            data=data.model_dump(mode="json"),
        )
        await self._pub.publish(subject, envelope)


class BoundStepReporter:
    """One-task view over a :class:`StepEventPublisher`.

    Plugins typically run a single ``do_execute`` against one (job_id,
    task_id, step) triple — repeating those args on every emit is noise.
    This wrapper binds them once so the call site reads as the actual
    progress story:

        reporter = BoundStepReporter(publisher, job_id=..., task_id=..., step="fft")
        await reporter.started()
        await reporter.progress(50, "computing FFT")
        await reporter.completed(output_files=[out_path])

    ``publisher`` may be ``None`` — that's the disabled-step-events case
    (``MAGELLON_STEP_EVENTS_ENABLED`` unset). Every method becomes a
    no-op so plugins don't need their own None guards.
    """

    def __init__(
        self,
        publisher: Optional[StepEventPublisher],
        *,
        job_id: UUID,
        step: str,
        task_id: Optional[UUID] = None,
    ) -> None:
        self._pub = publisher
        self._job_id = job_id
        self._task_id = task_id
        self._step = step

    async def started(self) -> None:
        if self._pub is None:
            return
        await self._pub.started(job_id=self._job_id, step=self._step, task_id=self._task_id)

    async def progress(self, percent: float, message: Optional[str] = None) -> None:
        if self._pub is None:
            return
        await self._pub.progress(
            job_id=self._job_id,
            step=self._step,
            percent=percent,
            message=message,
            task_id=self._task_id,
        )

    async def completed(self, output_files: Optional[List[str]] = None) -> None:
        if self._pub is None:
            return
        await self._pub.completed(
            job_id=self._job_id,
            step=self._step,
            task_id=self._task_id,
            output_files=output_files,
        )

    async def failed(self, error: str) -> None:
        if self._pub is None:
            return
        await self._pub.failed(
            job_id=self._job_id, step=self._step, error=error, task_id=self._task_id
        )


# ---------------------------------------------------------------------------
# Lazy publisher factory — was triplicated across CTF/FFT/MotionCor plugins
# ---------------------------------------------------------------------------


class _RmqAsyncAdapter:
    """Adapt the sync :class:`RabbitmqEventPublisher` to the async
    ``publish(subject, envelope)`` shape :class:`StepEventPublisher` calls.

    pika's basic_publish is fast enough that wrapping in ``asyncio.to_thread``
    would be overhead — emits are best-effort observability anyway.
    """

    def __init__(self, rmq: Any) -> None:
        self._rmq = rmq

    async def publish(self, subject: str, envelope: Envelope) -> None:
        self._rmq.publish(subject, envelope)


class _FanoutPublisher:
    """Emit each envelope to every wrapped transport. One publisher
    raising is logged but does not block the others — partial delivery
    beats full silence."""

    def __init__(self, publishers: List[Any]) -> None:
        self._publishers = publishers

    async def publish(self, subject: str, envelope: Envelope) -> None:
        for pub in self._publishers:
            try:
                await pub.publish(subject, envelope)
            except Exception:
                logger.exception(
                    "fanout publisher: one transport failed for event %s — continuing",
                    envelope.id,
                )


_PUBLISHERS: Dict[str, StepEventPublisher] = {}
_PUBLISHER_LOCK = asyncio.Lock()


async def make_step_publisher(
    plugin_name: str,
    *,
    rmq_settings: Any = None,
) -> Optional[StepEventPublisher]:
    """Lazy, idempotent step-event publisher per ``plugin_name``.

    Returns ``None`` when ``MAGELLON_STEP_EVENTS_ENABLED`` is unset or
    when broker init fails — in that case the env var is also flipped
    to ``"0"`` so subsequent calls short-circuit instead of hammering
    the broker.

    When ``MAGELLON_STEP_EVENTS_RMQ=1`` and ``rmq_settings`` is provided,
    the publisher fans out to both NATS and RMQ. RMQ init failure
    degrades to NATS-only rather than disabling everything — same shape
    the per-plugin factories used to have.

    Env knobs:
      MAGELLON_STEP_EVENTS_ENABLED=1   master toggle
      MAGELLON_STEP_EVENTS_RMQ=1       enable RMQ mirror (needs rmq_settings)
      NATS_URL                         default nats://localhost:4222
      NATS_STEP_EVENTS_STREAM          default MAGELLON_STEP_EVENTS
      NATS_STEP_EVENTS_SUBJECTS        default magellon.job.*.step.*
    """
    if os.environ.get("MAGELLON_STEP_EVENTS_ENABLED") != "1":
        return None
    cached = _PUBLISHERS.get(plugin_name)
    if cached is not None:
        return cached

    async with _PUBLISHER_LOCK:
        cached = _PUBLISHERS.get(plugin_name)
        if cached is not None:
            return cached

        try:
            from magellon_sdk.transport.nats import NatsPublisher

            nats = NatsPublisher(
                broker_url=os.environ.get("NATS_URL", "nats://localhost:4222"),
                stream=os.environ.get(
                    "NATS_STEP_EVENTS_STREAM", "MAGELLON_STEP_EVENTS"
                ),
                subjects=[
                    os.environ.get(
                        "NATS_STEP_EVENTS_SUBJECTS", "magellon.job.*.step.*"
                    )
                ],
            )
            await nats.connect()

            transports: List[Any] = [nats]
            if (
                os.environ.get("MAGELLON_STEP_EVENTS_RMQ") == "1"
                and rmq_settings is not None
            ):
                try:
                    from magellon_sdk.transport.rabbitmq_events import (
                        DEFAULT_EXCHANGE,
                        RabbitmqEventPublisher,
                    )

                    rmq = RabbitmqEventPublisher(
                        rmq_settings, exchange=DEFAULT_EXCHANGE
                    )
                    rmq.connect()
                    transports.append(_RmqAsyncAdapter(rmq))
                    logger.info(
                        "[%s] step-event publisher: RMQ mirror enabled", plugin_name
                    )
                except Exception:
                    logger.exception(
                        "[%s] step-event publisher: RMQ init failed — NATS only",
                        plugin_name,
                    )

            inner: Any = (
                transports[0] if len(transports) == 1 else _FanoutPublisher(transports)
            )
            publisher = StepEventPublisher(inner, plugin_name=plugin_name)
            _PUBLISHERS[plugin_name] = publisher
            logger.info(
                "[%s] step-event publisher ready (transports=%d)",
                plugin_name,
                len(transports),
            )
            return publisher
        except Exception:
            logger.exception(
                "[%s] step-event publisher init failed — disabling for this run",
                plugin_name,
            )
            os.environ["MAGELLON_STEP_EVENTS_ENABLED"] = "0"
            return None


def reset_publishers_for_tests() -> None:
    """Clear the module-level publisher cache. Test-only."""
    _PUBLISHERS.clear()


__all__ = [
    "STEP_COMPLETED",
    "STEP_EVENT_TYPES",
    "STEP_FAILED",
    "STEP_PROGRESS",
    "STEP_STARTED",
    "BoundStepReporter",
    "StepCompleted",
    "StepEventPublisher",
    "StepFailed",
    "StepProgress",
    "StepStarted",
    "make_step_publisher",
    "reset_publishers_for_tests",
    "step_subject",
]
