"""Unit tests for the PipelineRun controller (Phase 8b, 2026-05-03).

The controller talks SQLAlchemy directly — no repository layer — so
these tests stub the Session and verify the per-handler behavior:
validation, status defaults, soft-delete shape, and the list-with-
job-counts query.

End-to-end via the FastAPI TestClient + a real SQLite session is a
fuller integration test; deferred until the test fixture for
auth + permissions lands centrally (the same pattern other
CoreService controllers wait on).
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from controllers import pipelines_controller as pc
from models.pydantic_pipelines_models import PipelineRunCreate
from models.sqlalchemy_models import ImageJob, PipelineRun


# ---------------------------------------------------------------------------
# Helpers — fake DB session that records adds + lets us script query results
# ---------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *_a, **_kw):
        return self

    def order_by(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def first(self):
        if isinstance(self._result, list):
            return self._result[0] if self._result else None
        return self._result

    def all(self):
        if isinstance(self._result, list):
            return self._result
        return [self._result] if self._result is not None else []


def _make_db(*, find=None, list_result=None, jobs=None, job_count_rows=None):
    """Compose a MagicMock Session whose query() returns scripted rows.

    ``find`` — what ``.first()`` returns for PipelineRun lookups.
    ``list_result`` — what ``.all()`` returns for the list query.
    ``jobs`` — what ``.all()`` returns for the per-run jobs query.
    ``job_count_rows`` — list of (parent_run_id, job_oid) tuples for the
        bulk count query.
    """
    db = MagicMock()
    queries = {
        PipelineRun: _FakeQuery(find if list_result is None else list_result),
        ImageJob: _FakeQuery(jobs if jobs is not None else (job_count_rows or [])),
    }
    # Scope each query() call by its first positional argument.
    def _query(*models):
        primary = models[0]
        # Map ORM column accesses (ImageJob.parent_run_id) back to the
        # ImageJob entity for our scripted lookup.
        if hasattr(primary, "class_"):
            primary = primary.class_
        return queries.get(primary, _FakeQuery(None))

    db.query.side_effect = _query
    return db


# ---------------------------------------------------------------------------
# POST — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_rejects_blank_name():
    db = _make_db()
    with pytest.raises(HTTPException) as exc:
        await pc.create_pipeline_run(
            payload=PipelineRunCreate(name=" "),
            db=db,
            _=None,
            user_id=uuid4(),
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_create_persists_run_with_pending_status():
    """status_id=1 (pending) is the operator-visible signal that the
    run was registered but no child jobs have started. Pin it."""
    db = _make_db()
    user = uuid4()
    payload = PipelineRunCreate(
        name="session-25mar23b end-to-end",
        description="picker → extractor → classifier",
        msession_id="25mar23b",
        settings={"box_size": 256},
    )

    out = await pc.create_pipeline_run(
        payload=payload, db=db, _=None, user_id=user
    )

    # db.add called once with a PipelineRun instance.
    assert db.add.call_count == 1
    written = db.add.call_args[0][0]
    assert isinstance(written, PipelineRun)
    assert written.name == "session-25mar23b end-to-end"
    assert written.msession_id == "25mar23b"
    assert written.status_id == pc._STATUS_PENDING
    assert written.settings == {"box_size": 256}
    assert written.user_id == str(user)
    assert isinstance(written.created_date, datetime)
    db.commit.assert_called_once()
    # Detail response carries the new oid.
    assert out.oid == written.oid
    assert out.status_id == pc._STATUS_PENDING
    assert out.jobs == []


@pytest.mark.asyncio
async def test_create_rolls_back_on_db_error():
    db = _make_db()
    db.commit.side_effect = RuntimeError("db down")
    with pytest.raises(HTTPException) as exc:
        await pc.create_pipeline_run(
            payload=PipelineRunCreate(name="x"),
            db=db,
            _=None,
            user_id=uuid4(),
        )
    assert exc.value.status_code == 500
    db.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# GET — detail
# ---------------------------------------------------------------------------


def _stub_run(oid=None, *, deleted=False):
    return PipelineRun(
        oid=oid or uuid4(),
        name="run",
        description="d",
        msession_id="s",
        status_id=1,
        created_date=datetime(2026, 5, 3, 12, 0, 0),
        settings={"k": "v"},
        user_id="u",
        deleted_at=datetime.utcnow() if deleted else None,
    )


def _stub_job(parent_run_id):
    return ImageJob(
        oid=uuid4(),
        name="ctf job",
        msession_id="s",
        status_id=2,
        type_id=2,
        plugin_id="ctf-ctffind",
        created_date=datetime(2026, 5, 3, 12, 5, 0),
        parent_run_id=parent_run_id,
    )


def test_detail_returns_404_for_missing_run():
    db = _make_db(find=None)
    with pytest.raises(HTTPException) as exc:
        pc.get_pipeline_run(oid=uuid4(), db=db, user_id=uuid4())
    assert exc.value.status_code == 404


def test_detail_returns_404_for_soft_deleted_run():
    """Soft-deleted runs are 'gone' from the user's perspective. Pass
    include_deleted to the list endpoint for audit trails."""
    db = _make_db(find=_stub_run(deleted=True))
    with pytest.raises(HTTPException) as exc:
        pc.get_pipeline_run(oid=uuid4(), db=db, user_id=uuid4())
    assert exc.value.status_code == 404


def test_detail_returns_run_with_child_jobs():
    run = _stub_run()
    j1 = _stub_job(run.oid)
    j2 = _stub_job(run.oid)
    db = MagicMock()
    db.query.side_effect = [
        _FakeQuery(run),    # PipelineRun lookup
        _FakeQuery([j1, j2]),  # ImageJob lookup
    ]

    out = pc.get_pipeline_run(oid=run.oid, db=db, user_id=uuid4())

    assert out.oid == run.oid
    assert out.name == "run"
    assert len(out.jobs) == 2
    assert out.jobs[0].plugin_id == "ctf-ctffind"


# ---------------------------------------------------------------------------
# GET — list (counts join)
# ---------------------------------------------------------------------------


def test_list_returns_empty_when_no_runs():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    out = pc.list_pipeline_runs(db=db, user_id=uuid4())
    assert out == []


def test_list_summarises_with_per_run_job_counts():
    """The per-run job-count query must be a single bulk lookup, not
    N+1. Verify by counting db.query calls (one for runs, one for
    jobs)."""
    r1 = _stub_run()
    r2 = _stub_run()

    runs_query = MagicMock()
    runs_query.filter.return_value = runs_query
    runs_query.order_by.return_value = runs_query
    runs_query.limit.return_value = runs_query
    runs_query.all.return_value = [r1, r2]

    jobs_query = MagicMock()
    jobs_query.filter.return_value = jobs_query
    jobs_query.all.return_value = [
        (r1.oid, uuid4()), (r1.oid, uuid4()), (r1.oid, uuid4()),
        (r2.oid, uuid4()),
    ]

    db = MagicMock()
    db.query.side_effect = [runs_query, jobs_query]

    out = pc.list_pipeline_runs(db=db, user_id=uuid4())

    assert len(out) == 2
    counts_by_oid = {row.oid: row.job_count for row in out}
    assert counts_by_oid[r1.oid] == 3
    assert counts_by_oid[r2.oid] == 1


# ---------------------------------------------------------------------------
# DELETE — soft-delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_returns_404_for_missing_run():
    db = _make_db(find=None)
    with pytest.raises(HTTPException) as exc:
        await pc.delete_pipeline_run(oid=uuid4(), db=db, _=None, user_id=uuid4())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_idempotent_for_already_deleted_run():
    """Calling delete on an already-deleted row is a no-op success.
    Don't bump deleted_at — the original timestamp is the audit
    record."""
    run = _stub_run(deleted=True)
    pre_deleted_at = run.deleted_at
    db = _make_db(find=run)

    out = await pc.delete_pipeline_run(oid=run.oid, db=db, _=None, user_id=uuid4())

    assert "already deleted" in out["message"].lower()
    assert run.deleted_at == pre_deleted_at  # untouched
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_sets_deleted_at_and_commits():
    run = _stub_run()
    db = _make_db(find=run)

    out = await pc.delete_pipeline_run(oid=run.oid, db=db, _=None, user_id=uuid4())

    assert "soft-deleted" in out["message"].lower()
    assert run.deleted_at is not None
    assert isinstance(run.deleted_at, datetime)
    db.commit.assert_called_once()
