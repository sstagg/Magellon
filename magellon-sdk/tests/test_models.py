"""Regression tests for the task-model shapes.

Guards against the family of bugs that prior versions shipped:
- ``UUID`` fields typed non-Optional but defaulted to ``None``.
- Mutable ``datetime.now()`` / ``uuid4()`` call expressions as class-level
  defaults (evaluated once at import, shared across every instance).
- ``JobMessage.create`` passing ``uuid=...`` to a field named ``id``.
- ``PixSize: Optional[float] = False`` — default incompatible with type.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from magellon_sdk.models import (
    CTF_TASK,
    PENDING,
    MotionCorInput,
    JobMessage,
    TaskMessage,
    TaskResultMessage,
)


# --- TaskResultMessage: optional UUID fields + round-trip ---

def test_task_result_dto_defaults_are_none():
    r = TaskResultMessage()
    assert r.task_id is None
    assert r.image_id is None
    assert r.job_id is None


def test_task_result_dto_round_trip_all_optional():
    """Previously failed: task_id/image_id were typed UUID (not Optional)
    so `None` defaults round-tripped through JSON failed validation."""
    r = TaskResultMessage(code=200, message="ok")
    restored = TaskResultMessage.model_validate_json(r.model_dump_json())
    assert restored.code == 200
    assert restored.message == "ok"


# --- default_factory behaviour: no shared state across instances ---

def test_task_dto_job_id_defaults_per_instance():
    """Previously `job_id = uuid4()` was called once at import, so every
    TaskMessage() with a defaulted job_id shared the *same* UUID."""
    a = TaskMessage(data={})
    b = TaskMessage(data={})
    assert a.job_id != b.job_id


def test_task_dto_created_date_defaults_per_instance():
    a = TaskMessage(data={})
    time.sleep(0.001)
    b = TaskMessage(data={})
    assert a.created_date != b.created_date


def test_task_dto_created_date_is_utc():
    t = TaskMessage(data={})
    assert t.created_date is not None
    assert t.created_date.tzinfo is not None
    assert t.created_date.utcoffset() == timezone.utc.utcoffset(datetime.now())


def test_task_result_dto_created_date_is_utc_and_per_instance():
    a = TaskResultMessage()
    time.sleep(0.001)
    b = TaskResultMessage()
    assert a.created_date is not None
    assert a.created_date.tzinfo is not None
    assert a.created_date != b.created_date


# --- JobMessage.create: uuid → id fix ---

def test_job_dto_create_sets_id_not_silently_drops_it():
    """Previously passed ``uuid=uuid4()`` which Pydantic v2's default
    ``extra=ignore`` silently dropped, leaving ``id`` as None."""
    job = JobMessage.create({"k": "v"}, CTF_TASK)
    assert job.id is not None
    assert job.type == CTF_TASK
    assert job.data == {"k": "v"}
    assert job.status is not None and job.status.code == 0


# --- MotionCorInput.PixSize: False → None ---

def test_motioncor_pixsize_default_is_none():
    """Previously defaulted to False — utils.py had to defend with
    ``isinstance(..., (float, int))``. With None, downstream ``if
    params.PixSize`` still skips it cleanly."""
    d = MotionCorInput(inputFile="x.tif", Gain="g.mrc")
    assert d.PixSize is None


def test_motioncor_pixsize_accepts_float():
    d = MotionCorInput(inputFile="x.tif", Gain="g.mrc", PixSize=0.705)
    assert d.PixSize == 0.705
