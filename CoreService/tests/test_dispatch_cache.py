"""Tests for the PE2 dispatch cache (``services/dispatch_cache.py``).

In-memory SQLite covers the lookup + invalidate behaviour without
needing MySQL or the full ORM startup. The Artifact model is the
schema source of truth (alembic 0010); SQLite's CREATE TABLE picks
up the same columns + composite index.

What we pin:

  - Cache hit: identical (plugin_id, version, params, inputs) returns
    the prior artifact.
  - Cache miss on plugin_id mismatch, version bump, params change,
    or input-set change.
  - Soft-deleted rows never hit.
  - Soft-deleted ANCESTOR causes the descendant to miss too
    (PE2 invalidation rule #2).
  - Invalidate refuses the no-filter case.
  - Invalidate by plugin_id / by version / by artifact_oid all work.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from magellon_sdk.cache import compute_input_set_hash, compute_params_hash
from models.sqlalchemy_models import Artifact, Base
from services.dispatch_cache import invalidate_cache, lookup_cached_output


# ---------------------------------------------------------------------------
# In-memory SQLite fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db() -> Iterator[Session]:
    """Throwaway SQLite session with the artifact table.

    Only the Artifact-related portion of the schema is created — the
    rest of the ORM is heavy and not needed for cache-lookup tests.
    """
    engine = create_engine("sqlite:///:memory:")
    # Create only the artifact + dependency tables. Base.metadata
    # would try to create everything; we restrict to what we need.
    Artifact.__table__.create(engine, checkfirst=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_artifact(
    *,
    plugin_id: str = "stack-maker",
    plugin_version: str = "1.0.0",
    params: dict | None = None,
    input_oids: list | None = None,
    kind: str = "particle_stack",
    source_artifact_id: uuid.UUID | None = None,
    deleted_at: datetime | None = None,
) -> Artifact:
    return Artifact(
        oid=uuid.uuid4(),
        kind=kind,
        producing_job_id=uuid.uuid4(),
        producing_task_id=uuid.uuid4(),
        msession_id="test-session",
        producer_plugin_id=plugin_id,
        producer_plugin_version=plugin_version,
        params_hash=compute_params_hash(params or {}),
        input_set_hash=compute_input_set_hash(input_oids or []),
        source_artifact_id=source_artifact_id,
        deleted_at=deleted_at,
        created_date=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Hit
# ---------------------------------------------------------------------------


class TestCacheHit:
    def test_identical_run_hits(self, db):
        oid = uuid.uuid4()
        params = {"box_size": 256, "apix": 1.0}
        existing = _make_artifact(input_oids=[oid], params=params)
        db.add(existing)
        db.commit()

        hit = lookup_cached_output(
            db,
            plugin_id="stack-maker", plugin_version="1.0.0",
            params=params, input_oids=[oid],
        )
        assert hit is not None
        assert hit.oid == existing.oid

    def test_param_order_does_not_affect_hit(self, db):
        oid = uuid.uuid4()
        db.add(_make_artifact(
            input_oids=[oid],
            params={"a": 1, "b": 2, "c": 3},
        ))
        db.commit()
        hit = lookup_cached_output(
            db,
            plugin_id="stack-maker", plugin_version="1.0.0",
            params={"c": 3, "a": 1, "b": 2},
            input_oids=[oid],
        )
        assert hit is not None

    def test_input_order_does_not_affect_hit(self, db):
        a, b = uuid.uuid4(), uuid.uuid4()
        db.add(_make_artifact(input_oids=[a, b]))
        db.commit()
        hit = lookup_cached_output(
            db,
            plugin_id="stack-maker", plugin_version="1.0.0",
            params={}, input_oids=[b, a],
        )
        assert hit is not None

    def test_multiple_rows_returns_most_recent(self, db):
        """When the same key has been hit multiple times (rare but
        possible — pre-fix race), return the newest artifact."""
        oid = uuid.uuid4()
        old = _make_artifact(input_oids=[oid])
        old.created_date = datetime(2024, 1, 1)
        new = _make_artifact(input_oids=[oid])
        new.created_date = datetime(2026, 1, 1)
        db.add_all([old, new])
        db.commit()
        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.0.0",
            params={}, input_oids=[oid],
        )
        assert hit is not None
        assert hit.oid == new.oid


# ---------------------------------------------------------------------------
# Miss
# ---------------------------------------------------------------------------


class TestCacheMiss:
    def test_plugin_id_mismatch_misses(self, db):
        oid = uuid.uuid4()
        db.add(_make_artifact(plugin_id="stack-maker", input_oids=[oid]))
        db.commit()
        hit = lookup_cached_output(
            db, plugin_id="different-plugin", plugin_version="1.0.0",
            params={}, input_oids=[oid],
        )
        assert hit is None

    def test_version_bump_misses(self, db):
        oid = uuid.uuid4()
        db.add(_make_artifact(plugin_version="1.0.0", input_oids=[oid]))
        db.commit()
        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.1.0",
            params={}, input_oids=[oid],
        )
        assert hit is None

    def test_param_change_misses(self, db):
        oid = uuid.uuid4()
        db.add(_make_artifact(input_oids=[oid], params={"box_size": 256}))
        db.commit()
        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.0.0",
            params={"box_size": 320},
            input_oids=[oid],
        )
        assert hit is None

    def test_input_set_change_misses(self, db):
        a, b = uuid.uuid4(), uuid.uuid4()
        db.add(_make_artifact(input_oids=[a]))
        db.commit()
        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.0.0",
            params={}, input_oids=[a, b],
        )
        assert hit is None

    def test_missing_plugin_id_returns_none(self, db):
        """Without a plugin_id we can't compute the key — refuse the
        lookup rather than match every row."""
        hit = lookup_cached_output(
            db, plugin_id="", plugin_version="1.0.0",
            params={}, input_oids=[],
        )
        assert hit is None


# ---------------------------------------------------------------------------
# Soft-delete invalidation (rules #2 and #3 from the plan)
# ---------------------------------------------------------------------------


class TestSoftDeleteFiltering:
    def test_directly_deleted_row_does_not_hit(self, db):
        oid = uuid.uuid4()
        deleted = _make_artifact(
            input_oids=[oid], deleted_at=datetime.utcnow(),
        )
        db.add(deleted)
        db.commit()
        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.0.0",
            params={}, input_oids=[oid],
        )
        assert hit is None

    def test_superseded_ancestor_invalidates_descendant(self, db):
        """A descendant whose parent has been soft-deleted should not
        be cache-eligible — that's the plan's rule #2 ("input artifact
        superseded")."""
        # Parent artifact: a particle_stack that's been superseded.
        parent = _make_artifact(
            kind="particle_stack", deleted_at=datetime.utcnow(),
        )
        db.add(parent)
        db.flush()  # so the FK target exists
        # Child: 2D classification run that consumed the parent.
        child_input = uuid.uuid4()
        child = _make_artifact(
            kind="class_averages",
            input_oids=[child_input],
            source_artifact_id=parent.oid,
        )
        db.add(child)
        db.commit()

        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.0.0",
            params={}, input_oids=[child_input],
        )
        assert hit is None

    def test_live_descendant_with_live_parent_does_hit(self, db):
        """Sanity check the other side of the superseded-ancestor
        filter — same shape but with the parent still live should hit."""
        parent = _make_artifact(kind="particle_stack")
        db.add(parent)
        db.flush()
        child_input = uuid.uuid4()
        child = _make_artifact(
            kind="class_averages",
            input_oids=[child_input],
            source_artifact_id=parent.oid,
        )
        db.add(child)
        db.commit()

        hit = lookup_cached_output(
            db, plugin_id="stack-maker", plugin_version="1.0.0",
            params={}, input_oids=[child_input],
        )
        assert hit is not None
        assert hit.oid == child.oid


# ---------------------------------------------------------------------------
# Admin invalidate
# ---------------------------------------------------------------------------


class TestInvalidateCache:
    def test_refuses_no_filter(self, db):
        """An unfiltered call would soft-delete every artifact in the
        system. Refuse with count=0."""
        db.add(_make_artifact())
        db.commit()
        n = invalidate_cache(db)
        assert n == 0

    def test_invalidate_by_plugin_id(self, db):
        a = _make_artifact(plugin_id="stack-maker")
        b = _make_artifact(plugin_id="other-plugin")
        db.add_all([a, b])
        db.commit()
        n = invalidate_cache(db, plugin_id="stack-maker")
        assert n == 1
        db.refresh(a)
        db.refresh(b)
        assert a.deleted_at is not None
        assert b.deleted_at is None

    def test_invalidate_by_version(self, db):
        a = _make_artifact(plugin_version="1.0.0")
        b = _make_artifact(plugin_version="1.1.0")
        db.add_all([a, b])
        db.commit()
        n = invalidate_cache(db, plugin_version="1.0.0")
        assert n == 1
        db.refresh(a)
        db.refresh(b)
        assert a.deleted_at is not None
        assert b.deleted_at is None

    def test_invalidate_by_oid(self, db):
        a = _make_artifact()
        b = _make_artifact()
        db.add_all([a, b])
        db.commit()
        n = invalidate_cache(db, artifact_oid=a.oid)
        assert n == 1
        db.refresh(a)
        db.refresh(b)
        assert a.deleted_at is not None
        assert b.deleted_at is None

    def test_already_deleted_rows_not_counted(self, db):
        """invalidate_cache filters on ``deleted_at IS NULL`` so
        already-deleted rows aren't double-counted."""
        a = _make_artifact(deleted_at=datetime.utcnow())
        b = _make_artifact()
        db.add_all([a, b])
        db.commit()
        n = invalidate_cache(db, plugin_id="stack-maker")
        # Only the live row gets a fresh deleted_at — the pre-existing
        # one was already excluded.
        assert n == 1
