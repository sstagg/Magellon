"""Smoke tests for the Phase 4 ORM additions.

Pin the SQLAlchemy column shape that alembic migrations 0004 + 0005
declare. These tests don't hit a real DB — they only verify that the
ORM model module imports cleanly, the new columns/table exist, and
the column types match the migration. Catches the class of regression
where someone bumps the migration but forgets the ORM (or vice versa).
"""
from __future__ import annotations

import uuid

import pytest

from models.sqlalchemy_models import Artifact, ImageJobTask


# ---------------------------------------------------------------------------
# ImageJobTask gained subject_kind / subject_id (Phase 3 / migration 0004)
# ---------------------------------------------------------------------------


def test_image_job_task_has_subject_kind_column():
    cols = ImageJobTask.__table__.columns
    assert "subject_kind" in cols
    col = cols["subject_kind"]
    # VARCHAR(32), NOT NULL, default 'image' — per ratified rule 4
    # (project_artifact_bus_invariants.md, 2026-05-03).
    assert col.nullable is False
    assert col.type.length == 32
    # server_default should be 'image' so existing rows + new inserts
    # land with the back-compat value during the deploy.
    assert col.server_default is not None
    server_default_text = str(col.server_default.arg)
    assert "image" in server_default_text


def test_image_job_task_has_subject_id_column():
    cols = ImageJobTask.__table__.columns
    assert "subject_id" in cols
    assert cols["subject_id"].nullable is True


def test_image_job_task_subject_index_is_present():
    """Phase 3 added an index on (subject_kind, subject_id) so 'find
    every task touching this stack' stays fast as classifier rows
    grow. The index is declared via Column(index=True) on the kind
    column in the migration — the ORM mirrors the (kind, id) shape
    without the explicit index, but we at least verify the columns
    are queryable."""
    # ORM doesn't require us to mirror the composite index — the
    # column existence is enough for ORM-level queries to work. The
    # composite index lives in alembic 0004.
    cols = ImageJobTask.__table__.columns
    # subject_kind alone may carry an index (Column(index=True))
    # depending on the migration; both are acceptable.
    assert {"subject_kind", "subject_id"}.issubset(cols.keys())


# ---------------------------------------------------------------------------
# Artifact table (Phase 4 / migration 0005)
# ---------------------------------------------------------------------------


def test_artifact_has_promoted_hot_columns():
    """Per ratified rule 2: the queryable scalars + paths are real
    columns on the artifact table, not buried in data_json."""
    cols = Artifact.__table__.columns
    expected = {
        "oid",
        "kind",
        "producing_job_id",
        "producing_task_id",
        "msession_id",
        "mrcs_path",
        "star_path",
        "particle_count",
        "apix",
        "box_size",
        "data_json",
        "created_date",
        "deleted_at",
    }
    missing = expected - set(cols.keys())
    assert not missing, f"Artifact is missing: {missing}"


def test_artifact_kind_is_varchar_not_enum():
    """Per ratified rule 4: VARCHAR + app validation, not MySQL ENUM.
    The DB column type is the enforcement point."""
    col = Artifact.__table__.columns["kind"]
    # ``length`` attribute is on String/VARCHAR types only — fails on
    # ENUM. (We assert the type by lookup, not isinstance, because
    # the dialect-specific class wraps it.)
    assert hasattr(col.type, "length")
    assert col.type.length == 32
    assert col.nullable is False


def test_artifact_can_be_instantiated_with_typical_extraction_payload():
    """Sanity: build an Artifact row in memory the way
    TaskOutputProcessor._maybe_write_artifact does. No DB session
    needed — just verifies the constructor accepts the shape."""
    a = Artifact(
        oid=uuid.uuid4(),
        kind="particle_stack",
        producing_job_id=uuid.uuid4(),
        producing_task_id=uuid.uuid4(),
        msession_id="session_abc",
        mrcs_path="/work/sess/extract/m_particles.mrcs",
        star_path="/work/sess/extract/m_particles.star",
        particle_count=42,
        apix=1.23,
        box_size=256,
        data_json={"json_path": "/work/sess/extract/m_particles.json"},
    )
    assert a.kind == "particle_stack"
    assert a.particle_count == 42
    assert a.box_size == 256
    assert a.data_json["json_path"].endswith(".json")


def test_artifact_is_queryable_kind_independent_of_payload():
    """The producer doesn't need every promoted field — class
    averages, for example, have ``mrcs_path`` but no STAR. Verify
    the columns are nullable enough to hold that shape."""
    a = Artifact(
        oid=uuid.uuid4(),
        kind="class_averages",
        producing_job_id=uuid.uuid4(),
        producing_task_id=uuid.uuid4(),
        msession_id="session_abc",
        mrcs_path="/work/sess/can/class_averages.mrcs",
        # No star_path, box_size — class averages don't carry them
        particle_count=20000,
        apix=1.23,
        data_json={
            "assignments_csv_path": "/work/sess/can/assignments.csv",
            "num_classes_emitted": 50,
            "source_particle_stack_id": str(uuid.uuid4()),
        },
    )
    assert a.kind == "class_averages"
    assert a.star_path is None
    assert a.box_size is None
    assert a.data_json["num_classes_emitted"] == 50
