"""Tests for JobManager._rollup_parent_run — A.1, PipelineRun status rollup.

When a child ImageJob transitions, the parent PipelineRun.status_id is
recomputed from the aggregate of its children. PipelineRun uses a
different status enum (1=pending, 2=running, 4=completed, 5=failed,
6=cancelled) than ImageJob/JobManager (0-4); the rollup maps the child
ImageJob statuses onto the run enum.

Pre-A.1 the parent run row never moved off its create-time `pending`
status no matter what its child jobs did.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from models.sqlalchemy_models import ImageJob, PipelineRun
from services.job_manager import (
    JobManager,
    RUN_STATUS_CANCELLED,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_PENDING,
    RUN_STATUS_RUNNING,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
)


# ---------------------------------------------------------------------------
# Helpers — fake Session that scripts the two queries the rollup makes
# ---------------------------------------------------------------------------


def _db_with(run, child_statuses):
    """Fake Session.

    ``query(PipelineRun).filter(...).first()`` -> ``run``.
    ``query(ImageJob.status_id).filter(...).all()`` -> one (status,) tuple
    per child.
    """
    db = MagicMock()

    def _query(arg):
        q = MagicMock()
        q.filter.return_value = q
        if arg is PipelineRun:
            q.first.return_value = run
        else:  # the ImageJob.status_id column expression
            q.all.return_value = [(s,) for s in child_statuses]
        return q

    db.query.side_effect = _query
    return db


def _run():
    return PipelineRun(
        oid=uuid.uuid4(), status_id=RUN_STATUS_PENDING, msession_id="s1"
    )


def _child(run_id):
    return ImageJob(oid=uuid.uuid4(), name="child", parent_run_id=run_id)


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


def test_rollup_noop_when_job_has_no_parent_run():
    """Standalone job (the pre-Phase-8 common case) — rollup must not
    touch any run and must not query."""
    db = MagicMock()
    job = ImageJob(oid=uuid.uuid4(), name="standalone", parent_run_id=None)

    JobManager._rollup_parent_run(db, job)

    db.query.assert_not_called()


def test_rollup_noop_when_parent_run_missing():
    """parent_run_id points at a row that doesn't exist — don't crash."""
    run_id = uuid.uuid4()
    db = _db_with(run=None, child_statuses=[STATUS_COMPLETED])
    JobManager._rollup_parent_run(db, _child(run_id))
    # No run to mutate; absence of an exception is the assertion.


# ---------------------------------------------------------------------------
# Aggregate rule
# ---------------------------------------------------------------------------


def test_rollup_all_queued_keeps_run_pending():
    run = _run()
    db = _db_with(run, [STATUS_QUEUED, STATUS_QUEUED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_PENDING
    assert run.started_date is None
    assert run.ended_date is None


def test_rollup_any_running_moves_run_to_running():
    run = _run()
    db = _db_with(run, [STATUS_RUNNING, STATUS_QUEUED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_RUNNING
    assert run.started_date is not None
    assert run.ended_date is None


def test_rollup_partial_completion_is_running_not_completed():
    """Some children done, some still queued — the run is RUNNING, not
    COMPLETED. The completed-children-only test below covers the
    terminal case."""
    run = _run()
    db = _db_with(run, [STATUS_COMPLETED, STATUS_QUEUED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_RUNNING
    assert run.ended_date is None


def test_rollup_all_completed_moves_run_to_completed():
    run = _run()
    db = _db_with(run, [STATUS_COMPLETED, STATUS_COMPLETED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_COMPLETED
    assert run.started_date is not None
    assert run.ended_date is not None


def test_rollup_any_failed_moves_run_to_failed():
    run = _run()
    db = _db_with(run, [STATUS_COMPLETED, STATUS_FAILED, STATUS_RUNNING])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_FAILED
    assert run.ended_date is not None


def test_rollup_any_cancelled_moves_run_to_cancelled():
    run = _run()
    db = _db_with(run, [STATUS_COMPLETED, STATUS_CANCELLED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_CANCELLED
    assert run.ended_date is not None


def test_rollup_failed_takes_priority_over_cancelled():
    """A failed child outranks a cancelled one — a partially-failed
    pipeline reads as failed so it surfaces in error dashboards."""
    run = _run()
    db = _db_with(run, [STATUS_FAILED, STATUS_CANCELLED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert run.status_id == RUN_STATUS_FAILED


def test_rollup_is_idempotent():
    """Recomputes the full picture each call — re-running it on the
    same children converges to the same answer."""
    run = _run()
    db = _db_with(run, [STATUS_COMPLETED, STATUS_COMPLETED])
    JobManager._rollup_parent_run(db, _child(run.oid))
    first = (run.status_id, run.ended_date)
    JobManager._rollup_parent_run(db, _child(run.oid))
    assert (run.status_id, run.ended_date) == first
