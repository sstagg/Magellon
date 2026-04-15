"""Unit tests for StepEventJobStateProjector.

Pure logic test — JobManager is replaced with a fake recorder so we
verify exactly which calls each envelope shape produces. No DB
involvement; the projector's job is mapping envelopes onto manager
methods, and that's all we assert here.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from magellon_sdk.envelope import Envelope
from magellon_sdk.events import (
    STEP_COMPLETED,
    STEP_FAILED,
    STEP_PROGRESS,
    STEP_STARTED,
)

from services.job_state_projector import StepEventJobStateProjector


class _FakeManager:
    """Records every call in-order so tests can spell out the expected
    sequence per envelope. Default behavior: 'expected_tasks' == 2 so
    the second completion finalizes the job — overridable per test."""

    def __init__(self, expected_tasks: int = 2) -> None:
        self.calls: List[tuple] = []
        self._completed: Dict[str, set] = {}
        self._expected = expected_tasks

    def mark_task_running(self, task_id: str) -> bool:
        self.calls.append(("mark_task_running", task_id))
        return True

    def mark_task_completed(self, task_id: str, *, result: Any = None) -> bool:
        self.calls.append(("mark_task_completed", task_id, result))
        return True

    def mark_task_failed(self, task_id: str, *, error: str) -> bool:
        self.calls.append(("mark_task_failed", task_id, error))
        return True

    def mark_running(self, job_id: str, *, progress: int = 0):
        self.calls.append(("mark_running", job_id))
        return {}

    def record_task_completion(self, job_id: str, task_id: str) -> Dict[str, int]:
        self.calls.append(("record_task_completion", job_id, task_id))
        bucket = self._completed.setdefault(job_id, set())
        bucket.add(task_id)
        return {
            "completed": len(bucket),
            "expected": self._expected,
            "progress_pct": int(round(100 * len(bucket) / self._expected))
            if self._expected else 0,
        }

    def complete_job(self, job_id: str, *, result: Any, num_items: int = 0):
        self.calls.append(("complete_job", job_id, result, num_items))
        return {}

    def fail_job(self, job_id: str, *, error: str):
        self.calls.append(("fail_job", job_id, error))
        return {}


def _env(event_type: str, *, job_id: str, task_id: str | None = None,
         data_extra: Dict[str, Any] | None = None) -> Envelope:
    data: Dict[str, Any] = {"job_id": job_id, "step": "fft"}
    if task_id:
        data["task_id"] = task_id
    if data_extra:
        data.update(data_extra)
    return Envelope(
        id=str(uuid.uuid4()),
        type=event_type,
        source="test",
        subject=f"job.{job_id}",
        time=datetime.now(timezone.utc),
        data=data,
    )


def _project(projector, env):
    asyncio.run(projector(env))


def test_started_marks_task_and_job_running():
    fake = _FakeManager()
    p = StepEventJobStateProjector(manager=fake)
    job = str(uuid.uuid4())
    task = str(uuid.uuid4())

    _project(p, _env(STEP_STARTED, job_id=job, task_id=task))

    names = [c[0] for c in fake.calls]
    assert names == ["mark_task_running", "mark_running"]


def test_progress_is_a_no_op():
    fake = _FakeManager()
    p = StepEventJobStateProjector(manager=fake)
    _project(p, _env(STEP_PROGRESS, job_id=str(uuid.uuid4()),
                     task_id=str(uuid.uuid4()),
                     data_extra={"progress": 42}))
    assert fake.calls == []


def test_completed_records_and_finalizes_when_all_done():
    fake = _FakeManager(expected_tasks=2)
    p = StepEventJobStateProjector(manager=fake)
    job = str(uuid.uuid4())
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())

    _project(p, _env(STEP_COMPLETED, job_id=job, task_id=t1,
                     data_extra={"output_files": ["/out/a.png"]}))
    _project(p, _env(STEP_COMPLETED, job_id=job, task_id=t2,
                     data_extra={"output_files": ["/out/b.png"]}))

    names = [c[0] for c in fake.calls]
    # First completion: task done + record (no finalize yet, 1/2)
    # Second completion: task done + record + complete_job (2/2)
    assert names == [
        "mark_task_completed",
        "record_task_completion",
        "mark_task_completed",
        "record_task_completion",
        "complete_job",
    ]
    final = fake.calls[-1]
    assert final[2] == {"task_count": 2, "completed_tasks": 2}
    assert final[3] == 2  # num_items


def test_completed_does_not_finalize_until_all_tasks_done():
    fake = _FakeManager(expected_tasks=3)
    p = StepEventJobStateProjector(manager=fake)
    job = str(uuid.uuid4())
    t1 = str(uuid.uuid4())

    _project(p, _env(STEP_COMPLETED, job_id=job, task_id=t1))

    names = [c[0] for c in fake.calls]
    assert "complete_job" not in names


def test_failed_marks_task_and_fails_job():
    fake = _FakeManager()
    p = StepEventJobStateProjector(manager=fake)
    job = str(uuid.uuid4())
    task = str(uuid.uuid4())

    _project(p, _env(STEP_FAILED, job_id=job, task_id=task,
                     data_extra={"error": {"message": "boom"}}))

    names = [c[0] for c in fake.calls]
    assert names == ["mark_task_failed", "fail_job"]
    assert fake.calls[0][2] == "boom"
    assert fake.calls[1][2] == "boom"


def test_envelope_without_job_id_is_ignored():
    fake = _FakeManager()
    p = StepEventJobStateProjector(manager=fake)
    env = Envelope(
        id="e1", type=STEP_STARTED, source="t", subject="x",
        time=datetime.now(timezone.utc), data={"task_id": "tid"},
    )
    _project(p, env)
    assert fake.calls == []


def test_projector_swallows_manager_exceptions():
    """A bad envelope can't crash the downstream chain — the writer
    has already persisted it and Socket.IO emit needs to run too."""

    class _Boom:
        def mark_task_running(self, *a, **kw):
            raise RuntimeError("simulated")

        def mark_running(self, *a, **kw):
            raise RuntimeError("simulated")

    p = StepEventJobStateProjector(manager=_Boom())
    # Should NOT raise.
    _project(p, _env(STEP_STARTED, job_id=str(uuid.uuid4()),
                     task_id=str(uuid.uuid4())))
