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
    BoundStepReporter,
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


# ---- BoundStepReporter ----


@pytest.mark.asyncio
async def test_bound_reporter_emits_full_lifecycle_with_bound_ids():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="fft")
    job, task = uuid4(), uuid4()
    reporter = BoundStepReporter(pub, job_id=job, task_id=task, step="fft")

    await reporter.started()
    await reporter.progress(50.0, "halfway")
    await reporter.completed(output_files=["/tmp/out.png"])

    types = [env.type for _, env in rec.calls]
    assert types == [STEP_STARTED, STEP_PROGRESS, STEP_COMPLETED]

    for _, env in rec.calls:
        assert env.data["job_id"] == str(job)
        assert env.data["task_id"] == str(task)
        assert env.data["step"] == "fft"

    progress_env = rec.calls[1][1]
    assert progress_env.data["percent"] == 50.0
    assert progress_env.data["message"] == "halfway"

    completed_env = rec.calls[2][1]
    assert completed_env.data["output_files"] == ["/tmp/out.png"]


@pytest.mark.asyncio
async def test_bound_reporter_failed_carries_error():
    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="fft")
    reporter = BoundStepReporter(pub, job_id=uuid4(), step="fft")

    await reporter.failed(error="bad input")

    _, env = rec.calls[0]
    assert env.type == STEP_FAILED
    assert env.data["error"] == "bad input"
    # task_id is optional and stays None when not bound
    assert env.data["task_id"] is None


@pytest.mark.asyncio
async def test_bound_reporter_with_none_publisher_is_a_noop():
    """Passing publisher=None mirrors MAGELLON_STEP_EVENTS_ENABLED unset.
    Plugins should be able to call every method without their own guard."""
    reporter = BoundStepReporter(None, job_id=uuid4(), step="fft")

    # None of these should raise.
    await reporter.started()
    await reporter.progress(10.0, "x")
    await reporter.completed(output_files=["/tmp/x"])
    await reporter.failed(error="x")


# ---- BoundStepReporter cancel hook (G.1) ----


@pytest.mark.asyncio
async def test_bound_reporter_progress_raises_when_job_cancelled():
    """G.1: when an operator cancels the job, the very next
    ``reporter.progress(...)`` must raise :class:`JobCancelledError`.
    That's the seam plugins unwind through — no separate cancel-
    polling code in the plugin."""
    from magellon_sdk.bus.services.cancel_registry import get_cancel_registry
    from magellon_sdk.progress import JobCancelledError

    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="ctf")
    job_id = uuid4()
    reporter = BoundStepReporter(pub, job_id=job_id, step="ctf")

    # One emit OK before cancel.
    await reporter.progress(10.0, "running")
    assert len(rec.calls) == 1

    # Operator flips the cancel bit.
    reg = get_cancel_registry()
    try:
        reg.mark_cancelled(job_id)

        with pytest.raises(JobCancelledError, match=str(job_id)):
            await reporter.progress(50.0, "more work")

        # The cancelled emit must NOT have reached the publisher —
        # the check gate is before the publish call.
        assert len(rec.calls) == 1
    finally:
        reg.reset()


@pytest.mark.asyncio
async def test_bound_reporter_started_also_checks_cancel():
    """Started() is a checkpoint too — if the operator cancels
    between dispatch and the plugin's first emit, we want to unwind
    without doing any work."""
    from magellon_sdk.bus.services.cancel_registry import get_cancel_registry
    from magellon_sdk.progress import JobCancelledError

    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="ctf")
    job_id = uuid4()
    reporter = BoundStepReporter(pub, job_id=job_id, step="ctf")

    reg = get_cancel_registry()
    try:
        reg.mark_cancelled(job_id)
        with pytest.raises(JobCancelledError):
            await reporter.started()
        assert rec.calls == []
    finally:
        reg.reset()


@pytest.mark.asyncio
async def test_bound_reporter_terminal_emits_do_not_check_cancel():
    """completed() / failed() deliberately don't check the registry.
    If the plugin's own logic has reached a terminal state, aborting
    mid-emit is pointless — let the event land so the UI can show
    the final transition."""
    from magellon_sdk.bus.services.cancel_registry import get_cancel_registry

    rec = _Recorder()
    pub = StepEventPublisher(rec, plugin_name="ctf")
    job_id = uuid4()
    reporter = BoundStepReporter(pub, job_id=job_id, step="ctf")

    reg = get_cancel_registry()
    try:
        reg.mark_cancelled(job_id)
        # Both should succeed even though the job is marked cancelled.
        await reporter.completed(output_files=["/tmp/out.mrc"])
        await reporter.failed(error="late failure")
    finally:
        reg.reset()

    types = [env.type for _, env in rec.calls]
    assert STEP_COMPLETED in types
    assert STEP_FAILED in types
