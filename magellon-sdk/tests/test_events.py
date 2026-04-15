"""Unit tests for magellon_sdk.events.

No broker needed — the publisher is exercised against an in-memory
recorder that captures subject + envelope per call.
"""
from __future__ import annotations

from typing import List, Tuple
from uuid import uuid4

import pytest

from magellon_sdk.envelope import Envelope
from magellon_sdk.events import (
    STEP_COMPLETED,
    STEP_FAILED,
    STEP_PROGRESS,
    STEP_STARTED,
    StepCompleted,
    StepEventPublisher,
    StepProgress,
    step_subject,
)


class _Recorder:
    """Stands in for NatsPublisher — records each publish() call."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Envelope]] = []

    async def publish(self, subject: str, envelope: Envelope) -> None:
        self.calls.append((subject, envelope))


# ---- subject helper ----


def test_step_subject_includes_job_id_and_step():
    job = uuid4()
    assert step_subject(job, "ctf") == f"magellon.job.{job}.step.ctf"


def test_step_subject_accepts_string_id():
    assert step_subject("abc123", "motioncor") == "magellon.job.abc123.step.motioncor"


# ---- payload validation ----


def test_step_progress_percent_range_enforced():
    with pytest.raises(ValueError):
        StepProgress(job_id=uuid4(), step="ctf", percent=101.0)
    with pytest.raises(ValueError):
        StepProgress(job_id=uuid4(), step="ctf", percent=-1.0)


def test_step_completed_output_files_optional():
    # None is fine (step produced no files)
    ev = StepCompleted(job_id=uuid4(), step="ctf")
    assert ev.output_files is None
    ev2 = StepCompleted(job_id=uuid4(), step="ctf", output_files=["/tmp/a.png"])
    assert ev2.output_files == ["/tmp/a.png"]


# ---- publisher dispatch ----


@pytest.mark.asyncio
async def test_publisher_started_emits_started_envelope():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="ctf")
    job = uuid4()
    task = uuid4()

    await pub.started(job_id=job, step="ctf", task_id=task)

    assert len(rec.calls) == 1
    subject, env = rec.calls[0]
    assert subject == f"magellon.job.{job}.step.ctf"
    assert env.type == STEP_STARTED
    assert env.source == "magellon/plugins/ctf"
    assert env.subject == subject
    assert env.data["job_id"] == str(job)
    assert env.data["task_id"] == str(task)
    assert env.data["step"] == "ctf"


@pytest.mark.asyncio
async def test_publisher_progress_envelope_carries_percent_and_message():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="motioncor")
    job = uuid4()

    await pub.progress(job_id=job, step="motioncor", percent=42.5, message="frame 3/10")

    subject, env = rec.calls[0]
    assert env.type == STEP_PROGRESS
    assert env.data["percent"] == 42.5
    assert env.data["message"] == "frame 3/10"


@pytest.mark.asyncio
async def test_publisher_completed_includes_output_files():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="ctf")
    job = uuid4()

    await pub.completed(job_id=job, step="ctf", output_files=["/tmp/ctf.png"])

    subject, env = rec.calls[0]
    assert env.type == STEP_COMPLETED
    assert env.data["output_files"] == ["/tmp/ctf.png"]


@pytest.mark.asyncio
async def test_publisher_failed_includes_error():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="ctf")
    job = uuid4()

    await pub.failed(job_id=job, step="ctf", error="CTFFIND exited 1")

    subject, env = rec.calls[0]
    assert env.type == STEP_FAILED
    assert env.data["error"] == "CTFFIND exited 1"


@pytest.mark.asyncio
async def test_publisher_source_reflects_plugin_name():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="motioncor")
    await pub.started(job_id=uuid4(), step="motioncor")

    _, env = rec.calls[0]
    assert env.source == "magellon/plugins/motioncor"
