"""Regression tests for the broker-dispatch task_id zip contract.

2026-05-04 reviewer-flagged Blocker #1. Pre-fix, ``JobManager.create_job``
ignored the supplied ``task_ids`` whenever ``image_ids`` was also
present and minted random ``ImageJobTask.oid`` values. Plugin step
events arrived carrying the original ``task_id`` from the
``TaskMessage`` envelope — that id had no row in the DB, so
``_advance_task_state`` skipped silently and tasks stayed at
``status_id=QUEUED`` forever.

The fix at ``services/job_manager.py:create_job`` zips the two lists
1:1 when both are supplied, so the TaskMessage's ``id`` lands as the
real ``ImageJobTask.oid``. These tests pin the contract.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from services import job_manager
from services.job_manager import JobManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_session_local(monkeypatch):
    """Stub session_local() used by JobManager.create_job so we can
    inspect the ImageJobTask rows it adds without hitting MySQL."""
    db = MagicMock()
    added = []
    db.add.side_effect = lambda obj: added.append(obj)
    db.refresh = MagicMock()
    db.commit = MagicMock()

    class _Ctx:
        def __enter__(self):
            return db

        def __exit__(self, exc_type, exc, tb):
            db.close()
            return False

    monkeypatch.setattr(job_manager, "session_local", lambda: _Ctx())
    return db, added


# ---------------------------------------------------------------------------
# Blocker #1 zip mode
# ---------------------------------------------------------------------------


def test_blocker1_create_job_zips_task_ids_and_image_ids(monkeypatch):
    """When both lists are supplied (broker dispatch from
    plugins/controller.py::_submit_broker_job), the new ImageJobTask
    rows get the SUPPLIED task_id as oid + the supplied image_id as
    image_id. Pre-fix this branch silently dropped task_ids and
    minted random oids."""
    from models.sqlalchemy_models import ImageJobTask

    db, added = _capture_session_local(monkeypatch)

    pre_minted_task_id = uuid.uuid4()
    pre_minted_image_id = uuid.uuid4()

    JobManager().create_job(
        plugin_id="ctf/CTF Plugin",
        name="ctf job",
        task_ids=[pre_minted_task_id],
        image_ids=[str(pre_minted_image_id)],
    )

    # Should have added the parent ImageJob + one ImageJobTask.
    job_task_rows = [o for o in added if isinstance(o, ImageJobTask)]
    assert len(job_task_rows) == 1
    row = job_task_rows[0]
    # The bug: pre-fix this was uuid.uuid4(), not pre_minted_task_id.
    assert row.oid == pre_minted_task_id, (
        "ImageJobTask.oid must equal the supplied task_id so the "
        "TaskMessage.id round-trips back to a real DB row"
    )
    assert row.image_id == pre_minted_image_id


def test_blocker1_create_job_zip_mode_handles_multiple_pairs(monkeypatch):
    """Batch dispatch — N task_ids zip to N image_ids in order."""
    from models.sqlalchemy_models import ImageJobTask

    db, added = _capture_session_local(monkeypatch)

    task_ids = [uuid.uuid4() for _ in range(3)]
    image_ids = [str(uuid.uuid4()) for _ in range(3)]

    JobManager().create_job(
        plugin_id="ctf/CTF Plugin",
        name="batch",
        task_ids=task_ids,
        image_ids=image_ids,
    )

    rows = [o for o in added if isinstance(o, ImageJobTask)]
    assert len(rows) == 3
    for i, row in enumerate(rows):
        assert row.oid == task_ids[i]
        assert row.image_id == uuid.UUID(image_ids[i])


def test_blocker1_create_job_rejects_length_mismatch(monkeypatch):
    """Eager fail on length mismatch — silently dropping work was the
    exact bug we're closing."""
    db, _added = _capture_session_local(monkeypatch)

    with pytest.raises(ValueError, match="must zip 1:1"):
        JobManager().create_job(
            plugin_id="ctf/CTF Plugin",
            name="bad batch",
            task_ids=[uuid.uuid4(), uuid.uuid4()],
            image_ids=[str(uuid.uuid4())],
        )


# ---------------------------------------------------------------------------
# Phase 3 / High #4 / Phase 8b parameter pass-through
# ---------------------------------------------------------------------------


def test_create_job_persists_subject_kind_and_subject_id(monkeypatch):
    """Reviewer-flagged High #4: dispatch must seed subject_kind +
    subject_id at create_job so the ImageJobTask row carries them.
    Pre-fix the runner's contract-default fallback was the only
    path; subject_id was never persisted at dispatch."""
    from models.sqlalchemy_models import ImageJobTask

    db, added = _capture_session_local(monkeypatch)

    stack_id = uuid.uuid4()
    JobManager().create_job(
        plugin_id="2d-class/CAN Classifier",
        name="classify stack",
        task_ids=[uuid.uuid4()],
        subject_kind="particle_stack",
        subject_id=stack_id,
    )

    rows = [o for o in added if isinstance(o, ImageJobTask)]
    assert rows, "expected one ImageJobTask"
    assert rows[0].subject_kind == "particle_stack"
    assert rows[0].subject_id == stack_id


def test_create_job_persists_parent_run_id(monkeypatch):
    """Reviewer-flagged Medium #6: dispatched jobs must be able to
    join a PipelineRun. parent_run_id pass-through verified."""
    from models.sqlalchemy_models import ImageJob

    db, added = _capture_session_local(monkeypatch)

    run_id = uuid.uuid4()
    JobManager().create_job(
        plugin_id="ctf/CTF Plugin",
        name="ctf as part of pipeline",
        task_ids=[uuid.uuid4()],
        parent_run_id=run_id,
    )

    job_rows = [o for o in added if isinstance(o, ImageJob)]
    assert job_rows, "expected one ImageJob"
    assert job_rows[0].parent_run_id == run_id


def test_create_job_image_only_path_seeds_subject_id_from_image(monkeypatch):
    """Pre-Phase-3 image-keyed dispatch path (image_ids alone): the
    row's subject_kind defaults to 'image' and subject_id mirrors
    image_id when caller doesn't supply an explicit subject_id."""
    from models.sqlalchemy_models import ImageJobTask

    db, added = _capture_session_local(monkeypatch)

    image_id = uuid.uuid4()
    JobManager().create_job(
        plugin_id="motioncor",
        name="image task",
        image_ids=[str(image_id)],
    )

    rows = [o for o in added if isinstance(o, ImageJobTask)]
    assert rows
    assert rows[0].subject_kind == "image"
    assert rows[0].subject_id == image_id
