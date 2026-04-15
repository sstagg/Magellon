"""Step-event payload schemas + subject helpers for plugin → UI progress.

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

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from magellon_sdk.envelope import Envelope


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


__all__ = [
    "STEP_COMPLETED",
    "STEP_EVENT_TYPES",
    "STEP_FAILED",
    "STEP_PROGRESS",
    "STEP_STARTED",
    "StepCompleted",
    "StepEventPublisher",
    "StepFailed",
    "StepProgress",
    "StepStarted",
    "step_subject",
]
