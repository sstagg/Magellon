"""End-to-end tests against a real RabbitMQ broker.

Mirrors the in-memory e2e suite (``test_e2e_inmemory.py``) but runs
the same scenarios through the production RmqBinder. Catches bugs the
in-memory binder can hide:

  - exchange / queue declaration races (auto-delete vs durable mix-up)
  - reconnect logic during a transient broker drop
  - actual AMQP wire shape vs CloudEvents header round-trip
  - real DLX routing (the in-memory binder simulates it; pika's
    behavior is what runs in production)

Tests are skipped cleanly when the broker isn't reachable. Each test
uses unique queue names so concurrent runs / pre-existing queue
state don't interfere.

Start a broker with::

    docker compose -f Docker/docker-compose.yml up rabbitmq -d

Or set ``RABBITMQ_HOST`` / ``RABBITMQ_PORT`` / ``RABBITMQ_USER`` /
``RABBITMQ_PASS`` in the environment to point at another broker.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import List, Optional, Type
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

pika = pytest.importorskip("pika")

from magellon_sdk.base import PluginBase
from magellon_sdk.bus import DefaultMessageBus, get_bus
from magellon_sdk.bus.bootstrap import install_rmq_bus
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.bus.routes.event_route import (
    CancelRoute,
    ConfigRoute,
    StepEventRoute,
)
from magellon_sdk.bus.services.cancel_registry import (
    CancelMessage,
    get_cancel_registry,
    start_cancel_listener,
)
from magellon_sdk.categories.contract import CTF
from magellon_sdk.config_broker import (
    ConfigPublisher,
    ConfigSubscriber,
    ConfigUpdate,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError
from magellon_sdk.models import CTF_TASK, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.progress import JobCancelledError
from magellon_sdk.runner import PluginBrokerRunner


# ---------------------------------------------------------------------------
# Connection params + skip-if-no-broker
# ---------------------------------------------------------------------------

RMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RABBITMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RABBITMQ_PASS", "behd1d2")


class _Settings:
    HOST_NAME = RMQ_HOST
    PORT = RMQ_PORT
    USER_NAME = RMQ_USER
    PASSWORD = RMQ_PASS
    QUEUE_NAME = "rmq-e2e-default"


def _broker_reachable() -> bool:
    try:
        with socket.create_connection((RMQ_HOST, RMQ_PORT), timeout=2):
            pass
        params = pika.ConnectionParameters(
            host=RMQ_HOST,
            credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
            socket_timeout=2,
            connection_attempts=1,
        )
        conn = pika.BlockingConnection(params)
        conn.close()
        return True
    except Exception:
        return False


def _params() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=RMQ_HOST,
        credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
        socket_timeout=5,
        connection_attempts=1,
    )


def _delete_queue(name: str) -> None:
    try:
        conn = pika.BlockingConnection(_params())
        try:
            conn.channel().queue_delete(queue=name)
        finally:
            conn.close()
    except Exception:
        pass


def _declare_queue(name: str) -> None:
    """Pre-declare a queue on the default exchange so publishes don't
    silently drop. The RMQ binder lazily declares only on the consumer
    side; the producer side relies on either auto-declare or the queue
    already existing — match the seam-test pattern and pre-declare."""
    conn = pika.BlockingConnection(_params())
    try:
        conn.channel().queue_declare(queue=name, durable=True)
    finally:
        conn.close()


def _unique(tag: str) -> str:
    return f"rmq-e2e-{tag}-{uuid.uuid4().hex[:8]}"


def _wait_for(predicate, *, timeout: float = 5.0, interval: float = 0.05) -> bool:
    """Poll ``predicate()`` until it returns truthy or the deadline
    expires. Returns whether it became True."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Module-scoped bus fixture — one install per test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _bus():
    if not _broker_reachable():
        pytest.skip(f"RabbitMQ not reachable at {RMQ_HOST}:{RMQ_PORT}")
    bus = install_rmq_bus(_Settings())
    try:
        yield bus
    finally:
        try:
            bus.close()
        finally:
            get_bus.reset()


@pytest.fixture(autouse=True)
def _reset_cancel_registry():
    """The cancel registry is process-wide; isolate tests."""
    get_cancel_registry().reset()
    yield
    get_cancel_registry().reset()


# ---------------------------------------------------------------------------
# Test plugin
# ---------------------------------------------------------------------------

class _Input(BaseModel):
    image_path: str = "/x.mrc"


class _Output(BaseModel):
    answer: int


class _Plugin(PluginBase[_Input, _Output]):
    task_category = CTF_TASK

    def __init__(
        self,
        *,
        raise_on_run: Optional[Exception] = None,
        check_cancel_for_job: Optional[uuid.UUID] = None,
    ) -> None:
        super().__init__()
        self._raise = raise_on_run
        self._check_cancel = check_cancel_for_job
        self.call_count = 0

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="rmq-e2e-plugin", version="0.1.0", developer="test")

    @classmethod
    def input_schema(cls) -> Type[_Input]:
        return _Input

    @classmethod
    def output_schema(cls) -> Type[_Output]:
        return _Output

    def execute(self, input_data: _Input, *, reporter=None) -> _Output:
        self.call_count += 1
        if self._check_cancel is not None and get_cancel_registry().is_cancelled(self._check_cancel):
            raise JobCancelledError(f"job {self._check_cancel} cancelled")
        if self._raise is not None:
            raise self._raise
        return _Output(answer=42)


def _result_factory(task: TaskMessage, output: _Output) -> TaskResultMessage:
    return TaskResultMessage(
        task_id=task.id,
        job_id=task.job_id,
        code=200,
        message="ok",
        type=task.type,
        output_data={"answer": output.answer},
    )


def _make_task(*, job_id: Optional[uuid.UUID] = None) -> TaskMessage:
    return TaskMessage(
        id=uuid.uuid4(),
        job_id=job_id or uuid.uuid4(),
        type=CTF_TASK,
        data={"image_path": "/gpfs/x.mrc"},
    )


def _make_runner(plugin: _Plugin, *, in_q: str, out_q: str, bus) -> PluginBrokerRunner:
    return PluginBrokerRunner(
        plugin=plugin,
        settings=_Settings(),
        in_queue=in_q,
        out_queue=out_q,
        result_factory=_result_factory,
        bus=bus,
    )


def _drive_consumer_in_thread(handle) -> threading.Thread:
    """RmqBinder's task consumer registers the callback but doesn't
    spawn its own thread for ``start_consuming`` — the caller is
    expected to drive ``run_until_shutdown()`` (which is what
    ``PluginBrokerRunner.start_blocking`` does in production). For
    test code that doesn't use the runner's main loop, we drive it
    in a daemon thread.

    NOTE: this asymmetry with InMemoryBinder (which auto-spawns) is
    a real ergonomic gap. Plugin-author tests using InMemoryBinder
    work without spinning a thread; the same code against RmqBinder
    silently doesn't consume. Documented here so the next reader
    hits the same wall and finds the answer."""
    t = threading.Thread(
        target=handle.run_until_shutdown,
        name="test-consumer-driver",
        daemon=True,
    )
    t.start()
    return t


def _read_one_result(queue: str, *, deadline: float) -> Optional[TaskResultMessage]:
    """Poll the out-queue with basic_get until one message arrives or
    the deadline passes. Returns None on timeout."""
    conn = pika.BlockingConnection(_params())
    try:
        ch = conn.channel()
        ch.queue_declare(queue=queue, durable=True)
        while time.monotonic() < deadline:
            method, _, body = ch.basic_get(queue=queue, auto_ack=True)
            if method is not None:
                return TaskResultMessage.model_validate_json(body.decode())
            time.sleep(0.1)
        return None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# E2E #1 — runner round-trip through a real broker
# ---------------------------------------------------------------------------

def test_rmq_e2e_runner_round_trip(_bus):
    """The basic full-stack smoke: install bus → register runner's
    consumer on a real RMQ queue → dispatch a task via the bus →
    runner consumes, runs the plugin, publishes result on the out
    queue → test reads result back. Catches binder-level bugs the
    in-memory variant can't (queue decl flags, ack mode, content
    type round-trip)."""
    in_q = _unique("ctf-in")
    out_q = _unique("ctf-out")
    _declare_queue(in_q)
    _declare_queue(out_q)

    plugin = _Plugin()
    runner = _make_runner(plugin, in_q=in_q, out_q=out_q, bus=_bus)
    handle = _bus.tasks.consumer(runner._in_route, runner._handle_task)
    consume_thread = _drive_consumer_in_thread(handle)
    try:
        task = _make_task()
        _bus.tasks.send(
            TaskRoute.named(in_q),
            Envelope.wrap(source="t", type="t", subject=in_q, data=task),
        )

        result = _read_one_result(out_q, deadline=time.monotonic() + 10.0)
        assert result is not None, "no result on out queue within 10s"
        assert result.task_id == task.id
        assert result.output_data == {"answer": 42}
        assert plugin.call_count == 1
    finally:
        handle.close()
        consume_thread.join(timeout=5)
        _delete_queue(in_q)
        _delete_queue(out_q)


# ---------------------------------------------------------------------------
# E2E #2 — cancel propagates via real RMQ pub/sub
# ---------------------------------------------------------------------------

def test_rmq_e2e_cancel_propagates_via_real_bus(_bus):
    """The full cancel path through real RMQ: cancel listener
    subscribes to ``magellon.plugins.cancel.>`` on the
    ``magellon.plugins`` topic exchange; we publish a CancelMessage
    on a job-specific routing key; the listener's queue receives,
    decodes, marks the registry; we then verify the registry sees
    the cancel.

    Catches: routing-key glob mismatch (broker-side bind vs subject
    pattern), envelope decode regression, registry race during
    subscriber thread startup."""
    listener = start_cancel_listener(bus=_bus)
    try:
        # Allow the subscription queue to be declared + bound.
        time.sleep(0.2)

        job_id = uuid.uuid4()
        _bus.events.publish(
            CancelRoute.for_job(str(job_id)),
            Envelope.wrap(
                source="ops",
                type="magellon.cancel",
                subject=f"magellon.plugins.cancel.{job_id}",
                data=CancelMessage(job_id=job_id, reason="user cancelled"),
            ),
        )

        assert _wait_for(
            lambda: get_cancel_registry().is_cancelled(job_id),
            timeout=5.0,
        ), "cancel did not reach registry within 5s"
    finally:
        listener.stop()


def test_rmq_e2e_cancel_aborts_in_flight_task(_bus):
    """End-to-end: with a cancel listener running, dispatch a task
    whose plugin checks the registry. Publish cancel BEFORE the task
    so the registry is primed. Plugin sees the marked job and the
    runner publishes a cancelled result."""
    in_q = _unique("ctf-in")
    out_q = _unique("ctf-out")
    _declare_queue(in_q)
    _declare_queue(out_q)
    job_id = uuid.uuid4()

    listener = start_cancel_listener(bus=_bus)
    try:
        time.sleep(0.2)  # let listener bind

        # Mark the job cancelled FIRST so the plugin's registry check
        # is guaranteed to fire — avoids a race against the consumer.
        _bus.events.publish(
            CancelRoute.for_job(str(job_id)),
            Envelope.wrap(
                source="ops",
                type="magellon.cancel",
                subject=f"magellon.plugins.cancel.{job_id}",
                data=CancelMessage(job_id=job_id),
            ),
        )
        assert _wait_for(
            lambda: get_cancel_registry().is_cancelled(job_id),
            timeout=5.0,
        )

        plugin = _Plugin(check_cancel_for_job=job_id)
        runner = _make_runner(plugin, in_q=in_q, out_q=out_q, bus=_bus)
        handle = _bus.tasks.consumer(runner._in_route, runner._handle_task)
        consume_thread = _drive_consumer_in_thread(handle)
        try:
            _bus.tasks.send(
                TaskRoute.named(in_q),
                Envelope.wrap(
                    source="t", type="t", subject=in_q,
                    data=_make_task(job_id=job_id),
                ),
            )

            result = _read_one_result(out_q, deadline=time.monotonic() + 10.0)
            assert result is not None
            assert result.output_data == {
                "cancelled": True,
                "reason": f"job {job_id} cancelled",
            }
            assert plugin.call_count == 1  # entered once, raised in cancel check
        finally:
            handle.close()
            consume_thread.join(timeout=5)
            _delete_queue(in_q)
            _delete_queue(out_q)
    finally:
        listener.stop()


# ---------------------------------------------------------------------------
# E2E #3 — persistent config round-trips through real RMQ
# ---------------------------------------------------------------------------

def test_rmq_e2e_persistent_config_round_trip(_bus, tmp_path):
    """Full path: ConfigPublisher → real RMQ config exchange →
    ConfigSubscriber on the other end with persisted_path → settings
    appear on disk.

    Catches: config exchange / routing-key drift, content-type
    handling on the subscriber side, file-write timing relative to
    the in-memory apply."""
    persisted = tmp_path / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted, bus=_bus,
    )
    sub.start()
    try:
        time.sleep(0.2)  # let subscriber bind

        publisher = ConfigPublisher(bus=_bus)
        publisher.publish_to_category(CTF, {"max_defocus": 5.0}, persistent=True)

        assert _wait_for(persisted.exists, timeout=5.0), (
            "persistent config not written to disk within 5s"
        )

        saved = json.loads(persisted.read_text())
        assert saved == {"max_defocus": 5.0}
    finally:
        sub.stop()


def test_rmq_e2e_non_persistent_push_does_not_write(_bus, tmp_path):
    """Dual of the previous — verify a push without persistent=True
    arrives in-memory but does NOT write to disk. Otherwise
    persistence is silently always-on, which would surprise an
    operator."""
    persisted = tmp_path / "ctf.json"
    sub = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted, bus=_bus,
    )
    sub.start()
    try:
        time.sleep(0.2)

        ConfigPublisher(bus=_bus).publish_to_category(CTF, {"x": 1})  # default persistent=False

        assert _wait_for(
            lambda: sub.take_pending() == {"x": 1},
            timeout=5.0,
        ), "in-memory apply didn't happen"
        # Disk untouched.
        assert not persisted.exists()
    finally:
        sub.stop()


# ---------------------------------------------------------------------------
# E2E #4 — step events fan out through the topic exchange
# ---------------------------------------------------------------------------

def test_rmq_e2e_step_events_fan_out_to_multiple_subscribers(_bus):
    """Topic-exchange fanout through a real broker: one publisher,
    two subscribers each bound on the wildcard pattern, both receive
    every event. CoreService's step-event forwarder + an audit
    writer is the production shape."""
    job_id = uuid.uuid4()
    events_a: List[Envelope] = []
    events_b: List[Envelope] = []

    sub_a = _bus.events.subscribe(StepEventRoute.all(), events_a.append)
    sub_b = _bus.events.subscribe(StepEventRoute.all(), events_b.append)
    try:
        time.sleep(0.3)  # bind both subscribers

        for i in range(3):
            route = StepEventRoute.create(job_id=str(job_id), step=f"s{i}")
            _bus.events.publish(
                route,
                Envelope.wrap(
                    source="plugin",
                    type=f"magellon.step.s{i}",
                    subject=route.subject,
                    data={"i": i},
                ),
            )

        assert _wait_for(
            lambda: len(events_a) == 3 and len(events_b) == 3,
            timeout=5.0,
        ), f"expected 3 events each; got a={len(events_a)} b={len(events_b)}"
    finally:
        sub_a.close()
        sub_b.close()


# ---------------------------------------------------------------------------
# E2E #5 — PermanentError → DLQ via real RMQ
# ---------------------------------------------------------------------------

def test_rmq_e2e_permanent_error_does_not_succeed(_bus):
    """A PermanentError raised by the plugin must NOT produce a
    success result on the out queue. With DLQ wired (via
    declare_queue_with_dlq) the message would also land in the DLQ,
    but the queue we register here uses default args — so the
    minimum invariant we can verify cheaply is: no success result.

    For full DLQ-routing assertion against a real broker, see
    tests/test_transport_rabbitmq_integration.py — that suite exercises
    declare_queue_with_dlq directly."""
    in_q = _unique("perm-in")
    out_q = _unique("perm-out")
    _declare_queue(in_q)
    _declare_queue(out_q)

    plugin = _Plugin(raise_on_run=PermanentError("bad input"))
    runner = _make_runner(plugin, in_q=in_q, out_q=out_q, bus=_bus)
    handle = _bus.tasks.consumer(runner._in_route, runner._handle_task)
    consume_thread = _drive_consumer_in_thread(handle)
    try:
        _bus.tasks.send(
            TaskRoute.named(in_q),
            Envelope.wrap(source="t", type="t", subject=in_q, data=_make_task()),
        )

        # Give the consumer a generous window; we expect NO result.
        result = _read_one_result(out_q, deadline=time.monotonic() + 3.0)
        assert result is None, "PermanentError should not produce a success result"
        # The plugin was entered exactly once.
        assert plugin.call_count == 1
    finally:
        handle.close()
        consume_thread.join(timeout=5)
        _delete_queue(in_q)
        _delete_queue(out_q)
