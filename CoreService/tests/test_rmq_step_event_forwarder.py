"""Unit tests for :mod:`core.rmq_step_event_forwarder`.

We don't drive a real RMQ broker — that's covered by the SDK
integration suite. Here we stub :class:`RabbitmqEventConsumer` and
verify the forwarder honors the same persistence + session-lifecycle
contract as the NATS forwarder. The two share a JobEventWriter and
the DB UNIQUE event_id constraint, so re-delivery across channels
is provably a no-op.
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


def _envelope(event_type, *, job_id=None, event_id=None):
    job_id = job_id or uuid4()
    env = Envelope.wrap(
        source="magellon/plugins/ctf",
        type=event_type,
        subject=f"magellon.job.{job_id}.step.ctf",
        data={"job_id": str(job_id), "step": "ctf"},
    )
    if event_id:
        env.id = event_id
    return env


class StubConsumer:
    queue_name = "core_step_events_queue"
    binding_key = "job.*.step.*"
    exchange = "magellon.events"

    def __init__(self):
        self.callback = None
        self.started = False
        self.stopped = False

    def start(self, callback):
        self.callback = callback
        self.started = True

    def stop(self):
        self.stopped = True


def test_handle_persists_lifecycle_event(session_factory):
    from core.rmq_step_event_forwarder import RmqStepEventForwarder

    forwarder = RmqStepEventForwarder(consumer=StubConsumer(), session_factory=session_factory)
    env = _envelope(STEP_COMPLETED)

    forwarder.handle(env)

    db = session_factory()
    try:
        rows = db.query(JobEventRow).all()
        assert len(rows) == 1
        assert rows[0].event_id == env.id
    finally:
        db.close()


def test_handle_skips_progress_event(session_factory):
    from core.rmq_step_event_forwarder import RmqStepEventForwarder

    forwarder = RmqStepEventForwarder(consumer=StubConsumer(), session_factory=session_factory)
    forwarder.handle(_envelope(STEP_PROGRESS))

    db = session_factory()
    try:
        assert db.query(JobEventRow).count() == 0
    finally:
        db.close()


def test_redelivery_with_same_event_id_is_noop(session_factory):
    """Same event_id arriving twice (e.g., NATS already wrote it,
    then RMQ delivers) must dedupe at the DB."""
    from core.rmq_step_event_forwarder import RmqStepEventForwarder

    forwarder = RmqStepEventForwarder(consumer=StubConsumer(), session_factory=session_factory)
    env = _envelope(STEP_COMPLETED)

    forwarder.handle(env)
    forwarder.handle(env)  # second delivery

    db = session_factory()
    try:
        assert db.query(JobEventRow).count() == 1
    finally:
        db.close()


def test_start_wires_handle_into_consumer(session_factory):
    from core.rmq_step_event_forwarder import RmqStepEventForwarder

    consumer = StubConsumer()
    forwarder = RmqStepEventForwarder(consumer=consumer, session_factory=session_factory)
    forwarder.start()

    assert consumer.started is True
    assert consumer.callback == forwarder.handle


def test_stop_calls_consumer_stop(session_factory):
    from core.rmq_step_event_forwarder import RmqStepEventForwarder

    consumer = StubConsumer()
    forwarder = RmqStepEventForwarder(consumer=consumer, session_factory=session_factory)
    forwarder.stop()

    assert consumer.stopped is True
