"""Smoke tests for the Phase 8 PipelineRun ORM additions.

Pin the SQLAlchemy column shape that alembic migration 0006 declares
+ verify the relationship between ImageJob and PipelineRun is
queryable. No DB session needed — these test the model module's
in-memory shape, catching the "alembic landed but ORM didn't" or
vice versa class of regression.
"""
from __future__ import annotations

import uuid

from models.sqlalchemy_models import ImageJob, PipelineRun


# ---------------------------------------------------------------------------
# PipelineRun table shape
# ---------------------------------------------------------------------------


def test_pipeline_run_has_expected_columns():
    cols = PipelineRun.__table__.columns
    expected = {
        "oid",
        "name",
        "description",
        "msession_id",
        "status_id",
        "created_date",
        "started_date",
        "ended_date",
        "settings",
        "user_id",
        "deleted_at",
        "OptimisticLockField",
        "GCRecord",
    }
    missing = expected - set(cols.keys())
    assert not missing, f"PipelineRun is missing: {missing}"


def test_pipeline_run_status_id_is_required_with_default_pending():
    """status_id NOT NULL DEFAULT 1 (pending). Mirrors ImageJob.
    Pinned so a future migration can't silently drop the default."""
    col = PipelineRun.__table__.columns["status_id"]
    assert col.nullable is False
    assert col.server_default is not None
    assert "1" in str(col.server_default.arg)


def test_pipeline_run_msession_id_is_indexed_for_session_listing():
    """The ``GET /sessions/{sid}/pipelines`` query path filters on
    msession_id; the index keeps that fast as runs accumulate."""
    cols = PipelineRun.__table__.columns
    assert cols["msession_id"].index is True


def test_pipeline_run_created_date_is_required():
    col = PipelineRun.__table__.columns["created_date"]
    assert col.nullable is False


# ---------------------------------------------------------------------------
# ImageJob.parent_run_id FK + relationship
# ---------------------------------------------------------------------------


def test_image_job_has_parent_run_id_column():
    cols = ImageJob.__table__.columns
    assert "parent_run_id" in cols
    # Nullable so pre-Phase-8 jobs remain valid as standalone runs.
    assert cols["parent_run_id"].nullable is True


def test_image_job_parent_run_id_is_indexed():
    """Listing all jobs under a PipelineRun is a hot path — index
    keeps it fast."""
    cols = ImageJob.__table__.columns
    assert cols["parent_run_id"].index is True


def test_pipeline_run_jobs_relationship_walks_back():
    """Verify the ORM relationship resolves at class load — catches
    the "back_populates names diverged" footgun where one side says
    'jobs' and the other says 'job'."""
    # Touching the attribute resolves the relationship descriptor;
    # if the back_populates pair is wrong, this raises.
    rel = PipelineRun.__mapper__.relationships["jobs"]
    assert rel.mapper.class_ is ImageJob
    assert rel.back_populates == "parent_run"


def test_image_job_parent_run_relationship_resolves():
    rel = ImageJob.__mapper__.relationships["parent_run"]
    assert rel.mapper.class_ is PipelineRun
    assert rel.back_populates == "jobs"


# ---------------------------------------------------------------------------
# Constructor smoke — typical create-time payload
# ---------------------------------------------------------------------------


def test_pipeline_run_can_be_instantiated_with_typical_payload():
    """Sanity: build a PipelineRun the way a future ``POST /pipelines/runs``
    handler would. No DB session needed — verify the constructor
    accepts the shape."""
    run = PipelineRun(
        oid=uuid.uuid4(),
        name="Process session 25mar23b",
        description="picker → extractor → classifier",
        msession_id="25mar23b_session_oid_str",
        status_id=1,  # pending
        settings={
            "picker": {"backend": "topaz", "threshold": -3.0},
            "extractor": {"box_size": 256, "edge_width": 2},
            "classifier": {"num_classes": 50, "align_iters": 3},
        },
        user_id="bkhoshbin",
    )
    assert run.name.startswith("Process session")
    assert run.status_id == 1
    assert run.settings["extractor"]["box_size"] == 256


def test_image_job_links_to_pipeline_run_via_parent_run_id():
    """ImageJob's parent_run_id can be set to a PipelineRun.oid; the
    ORM relationship (``parent_run``) then resolves the row."""
    run_oid = uuid.uuid4()
    run = PipelineRun(oid=run_oid, status_id=1, msession_id="s1")
    job = ImageJob(
        oid=uuid.uuid4(),
        name="extraction job",
        msession_id="s1",
        parent_run_id=run_oid,
        status_id=1,
    )
    # Without a Session, we can only verify the FK column is set;
    # back-populate happens on flush.
    assert job.parent_run_id == run_oid
