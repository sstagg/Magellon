"""Unit tests for :mod:`core.step_event_forwarder`.

NATS is stubbed out — these tests drive ``StepEventForwarder.handle``
directly with an in-memory SQLite session, mirroring the setup used
by ``test_job_event_writer``. The forwarder's responsibilities are:

1. per-envelope scoped session (close even on writer failure)
2. delegate filtering/idempotency to JobEventWriter (don't re-check here)
3. ``start()`` honours ``NatsConsumer.connect()`` returning False so
   the caller can retry when the publisher isn't up yet.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, Column, DateTime, String, JSON
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.sqlite.dml import Insert as SqliteInsert

from lib.sqlalchemy_uuid_type import SqlalchemyUuidType
from magellon_sdk.envelope import Envelope
from magellon_sdk.events import STEP_COMPLETED, STEP_PROGRESS


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
def session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    import services.job_event_writer as mod

    monkeypatch.setattr(mod, "JobEvent", JobEventRow)
    monkeypatch.setattr(mod, "mysql_insert", sqlite_insert)

    def _on_duplicate_key_update(self, **kw):
        return self.prefix_with("OR IGNORE")

    monkeypatch.setattr(
        SqliteInsert, "on_duplicate_key_update", _on_duplicate_key_update, raising=False
    )

    return Session


def _envelope(event_type, *, job_id=None):
    job_id = job_id or uuid4()
    return Envelope.wrap(
        source="magellon/plugins/ctf",
        type=event_type,
        subject=f"magellon.job.{job_id}.step.ctf",
        data={"job_id": str(job_id), "step": "ctf"},
    )


@pytest.mark.asyncio
async def test_handle_persists_lifecycle_event(session_factory):
    from core.step_event_forwarder import StepEventForwarder

    forwarder = StepEventForwarder(consumer=None, session_factory=session_factory)
    env = _envelope(STEP_COMPLETED)

    await forwarder.handle(env)

    db = session_factory()
    try:
        rows = db.query(JobEventRow).all()
        assert len(rows) == 1
        assert rows[0].event_id == env.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_handle_skips_progress_event(session_factory):
    from core.step_event_forwarder import StepEventForwarder

    forwarder = StepEventForwarder(consumer=None, session_factory=session_factory)
    await forwarder.handle(_envelope(STEP_PROGRESS))

    db = session_factory()
    try:
        assert db.query(JobEventRow).count() == 0
    finally:
        db.close()


@pytest.mark.asyncio
async def test_handle_closes_session_on_writer_failure(session_factory, monkeypatch):
    """Even if the writer raises, the scoped session must close so we
    don't leak connections from a long-running consumer loop."""
    from core import step_event_forwarder as fwd_mod

    closed = {"count": 0}

    class TrackingSession:
        def __init__(self, real):
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        def close(self):
            closed["count"] += 1
            self._real.close()

    def tracking_factory():
        return TrackingSession(session_factory())

    class BoomWriter:
        def __init__(self, db):
            pass

        def write(self, envelope):
            raise RuntimeError("boom")

    monkeypatch.setattr(fwd_mod, "JobEventWriter", BoomWriter)

    forwarder = fwd_mod.StepEventForwarder(consumer=None, session_factory=tracking_factory)

    with pytest.raises(RuntimeError, match="boom"):
        await forwarder.handle(_envelope(STEP_COMPLETED))

    assert closed["count"] == 1


@pytest.mark.asyncio
async def test_start_returns_false_when_stream_missing(session_factory):
    """If the JetStream stream isn't present yet (publisher not up),
    ``NatsConsumer.connect()`` returns False — forwarder must surface
    that so the startup hook can skip or schedule a retry."""
    from core.step_event_forwarder import StepEventForwarder

    class StubConsumer:
        subject = "magellon.job.*.step.*"
        durable_name = "core-job-event-writer"

        async def connect(self):
            return False

        async def subscribe(self, callback):
            raise AssertionError("subscribe must not run when connect is False")

        async def close(self):
            pass

    forwarder = StepEventForwarder(consumer=StubConsumer(), session_factory=session_factory)
    assert await forwarder.start() is False


@pytest.mark.asyncio
async def test_start_subscribes_when_connected(session_factory):
    from core.step_event_forwarder import StepEventForwarder

    subscribed = {"cb": None}

    class StubConsumer:
        subject = "magellon.job.*.step.*"
        durable_name = "core-job-event-writer"

        async def connect(self):
            return True

        async def subscribe(self, callback):
            subscribed["cb"] = callback

        async def close(self):
            pass

    forwarder = StepEventForwarder(consumer=StubConsumer(), session_factory=session_factory)
    assert await forwarder.start() is True
    assert subscribed["cb"] == forwarder.handle
