"""Unit tests for services.job_event_writer.

Uses an in-memory SQLite DB with a minimal mirror of the ``job_event``
table so the writer's idempotency contract can be exercised without a
live MySQL. ON DUPLICATE KEY UPDATE doesn't exist in SQLite, so the
writer's MySQL-specific insert is monkeypatched to ``INSERT OR IGNORE``
— the business behaviour (dup → no-op) is identical across both.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, Column, DateTime, String, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.sqlite.dml import Insert as SqliteInsert

from lib.sqlalchemy_uuid_type import SqlalchemyUuidType

from magellon_sdk.envelope import Envelope
from magellon_sdk.events import STEP_COMPLETED, STEP_FAILED, STEP_PROGRESS, STEP_STARTED

# Build a minimal Base + JobEvent replica for SQLite.
TestBase = declarative_base()


class JobEventRow(TestBase):
    __tablename__ = "job_event"
    oid = Column(SqlalchemyUuidType, primary_key=True)
    event_id = Column(String(64), unique=True, nullable=False)
    job_id = Column(SqlalchemyUuidType, nullable=False)
    task_id = Column(SqlalchemyUuidType)
    event_type = Column(String(64), nullable=False)
    step = Column(String(64), nullable=False)
    source = Column(String(200))
    ts = Column(DateTime, nullable=False)
    data_json = Column(JSON)
    created_date = Column(DateTime, nullable=False)


@pytest.fixture()
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Point the writer at our test row + at SQLite's insert flavour.
    import services.job_event_writer as mod

    monkeypatch.setattr(mod, "JobEvent", JobEventRow)
    monkeypatch.setattr(mod, "mysql_insert", sqlite_insert)

    # SQLite's Insert has no on_duplicate_key_update; attach a shim at
    # the class level so it survives the .values() chain (which returns
    # a fresh Insert). INSERT OR IGNORE gives rowcount=0 on conflict,
    # matching the MySQL ON DUPLICATE KEY UPDATE oid=oid no-op semantics.
    def _on_duplicate_key_update(self, **kw):
        return self.prefix_with("OR IGNORE")

    monkeypatch.setattr(
        SqliteInsert, "on_duplicate_key_update", _on_duplicate_key_update, raising=False
    )

    yield session
    session.close()


def _make_envelope(event_type, *, job_id=None, task_id=None, event_id=None, step="ctf"):
    job_id = job_id or uuid4()
    data = {"job_id": str(job_id), "step": step}
    if task_id is not None:
        data["task_id"] = str(task_id)
    return Envelope.wrap(
        source="magellon/plugins/ctf",
        type=event_type,
        subject=f"magellon.job.{job_id}.step.{step}",
        data=data,
    ), job_id


def test_writer_persists_lifecycle_event(db_session):
    from services.job_event_writer import JobEventWriter

    env, job_id = _make_envelope(STEP_COMPLETED, task_id=uuid4())
    writer = JobEventWriter(db_session)

    assert writer.write(env) is True

    rows = db_session.query(JobEventRow).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_id == env.id
    assert row.event_type == STEP_COMPLETED
    assert row.step == "ctf"
    assert row.job_id == job_id
    assert isinstance(row.ts, datetime)


def test_writer_skips_progress_event(db_session):
    from services.job_event_writer import JobEventWriter

    env, _ = _make_envelope(STEP_PROGRESS)
    writer = JobEventWriter(db_session)

    assert writer.write(env) is False
    assert db_session.query(JobEventRow).count() == 0


def test_writer_dedupes_same_event_id(db_session):
    from services.job_event_writer import JobEventWriter

    env, _ = _make_envelope(STEP_STARTED)
    writer = JobEventWriter(db_session)

    assert writer.write(env) is True
    # Same envelope (same CloudEvents id) — arriving on a second
    # channel, say. Must no-op.
    assert writer.write(env) is False
    assert db_session.query(JobEventRow).count() == 1


def test_writer_rejects_envelope_without_job_id(db_session):
    from services.job_event_writer import JobEventWriter

    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type=STEP_FAILED,
        subject="magellon.job.x.step.ctf",
        data={"step": "ctf", "error": "boom"},  # no job_id
    )
    writer = JobEventWriter(db_session)

    assert writer.write(env) is False
    assert db_session.query(JobEventRow).count() == 0


def test_writer_ignores_unknown_event_type(db_session):
    from services.job_event_writer import JobEventWriter

    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type="not.a.step.event",
        data={"job_id": str(uuid4()), "step": "ctf"},
    )
    writer = JobEventWriter(db_session)

    assert writer.write(env) is False
    assert db_session.query(JobEventRow).count() == 0


def test_writer_persists_all_three_lifecycle_types(db_session):
    from services.job_event_writer import JobEventWriter

    writer = JobEventWriter(db_session)
    job_id = uuid4()
    for t in (STEP_STARTED, STEP_COMPLETED, STEP_FAILED):
        env, _ = _make_envelope(t, job_id=job_id)
        assert writer.write(env) is True

    assert db_session.query(JobEventRow).count() == 3
