"""Seam-level E2E smoke test for the CoreService↔plugin pipeline.

Drives the *shape* of the production path without GPU/MotionCor: a
``TaskMessage`` is dispatched via :class:`RabbitmqTaskDispatcher`, a stub
worker thread consumes it off the real broker, builds a matching
``TaskResultMessage``, publishes it to the result queue, and the test
thread reads it back. We then run the result through the
``_advance_task_state`` logic (imported from the result-processor
plugin) with a mocked DB to prove the wire format survives and the
state transition reaches COMPLETED + correct stage.

This is the cheapest test that would have caught every Phase 1–6 bug
end-to-end:

- dispatcher routing (Phase 6)
- RMQ publish error-surface (Phase 3)
- TaskMessage/TaskResultMessage wire compatibility (Phase 2/3)
- ImageJobTask state advancement (Phase 4)

Budget: 30s wall clock per test. Skips cleanly if RMQ is down.

For the full docker-compose + GPU MotionCor E2E, see
``CoreService/scripts/e2e_smoke.sh`` and
``test_e2e_full_stack_smoke`` below (marked ``requires_full_stack``,
skipped by default).
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import uuid
from unittest.mock import MagicMock

import pytest

pika = pytest.importorskip("pika")
from pika.exceptions import AMQPConnectionError

from magellon_sdk import messaging
from magellon_sdk.dispatcher import RabbitmqTaskDispatcher, TaskDispatcherRegistry
from magellon_sdk.models import CTF_TASK, MOTIONCOR, TaskMessage, TaskResultMessage, TaskStatus


RMQ_HOST = os.environ.get("RABBITMQ_HOST", "127.0.0.1")
RMQ_PORT = int(os.environ.get("RABBITMQ_PORT", "5672"))
RMQ_USER = os.environ.get("RABBITMQ_USER", "rabbit")
RMQ_PASS = os.environ.get("RABBITMQ_PASS", "behd1d2")

TEST_BUDGET = 30  # seconds per test — guard against consumer hangs


class _Settings:
    HOST_NAME = RMQ_HOST
    PORT = RMQ_PORT
    USER_NAME = RMQ_USER
    PASSWORD = RMQ_PASS
    QUEUE_NAME = "e2e-seam-default"


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


@pytest.fixture(scope="module", autouse=True)
def _require_broker():
    if not _broker_reachable():
        pytest.skip(f"RabbitMQ not reachable at {RMQ_HOST}:{RMQ_PORT}")
    # MB6.2: messaging.publish_message_to_queue (used by
    # RabbitmqTaskDispatcher) now delegates to bus.tasks.send. Install
    # the RMQ bus for the duration of this module so the dispatcher
    # has a binder to publish through.
    from magellon_sdk.bus._facade import get_bus
    from magellon_sdk.bus.bootstrap import install_rmq_bus
    bus = install_rmq_bus(_Settings())
    try:
        yield
    finally:
        try:
            bus.close()
        finally:
            get_bus.override(None)


def _params() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=RMQ_HOST,
        credentials=pika.PlainCredentials(RMQ_USER, RMQ_PASS),
        socket_timeout=5,
        connection_attempts=1,
    )


def _delete_queue(q: str) -> None:
    try:
        conn = pika.BlockingConnection(_params())
        try:
            conn.channel().queue_delete(queue=q)
        finally:
            conn.close()
    except Exception:
        pass


def _unique(tag: str) -> str:
    return f"e2e-seam-{tag}-{uuid.uuid4().hex[:8]}"


def _start_stub_worker(in_queue: str, out_queue: str, *, output_data: dict, deadline: float) -> threading.Thread:
    """Spin up a background thread that behaves like an external plugin:
    consume one ``TaskMessage`` off ``in_queue``, publish one
    ``TaskResultMessage`` onto ``out_queue``, then exit."""

    def _run() -> None:
        try:
            conn = pika.BlockingConnection(_params())
            try:
                ch = conn.channel()
                ch.queue_declare(queue=in_queue, durable=True)
                ch.queue_declare(queue=out_queue, durable=True)

                # Poll basic_get until a message lands or we hit the deadline.
                body = None
                while time.time() < deadline:
                    method, _, b = ch.basic_get(queue=in_queue, auto_ack=True)
                    if method is not None:
                        body = b
                        break
                    time.sleep(0.1)

                if body is None:
                    return

                task = messaging.parse_message_to_task_object(body.decode())
                result = TaskResultMessage(
                    task_id=task.id,
                    job_id=task.job_id,
                    image_id=uuid.uuid4(),
                    image_path="/tmp/fake.mrc",
                    session_name="seam-session",
                    status=TaskStatus(code=2, name="completed", description="ok"),
                    type=task.type,
                    output_data=output_data,
                )
                ch.basic_publish(
                    exchange="",
                    routing_key=out_queue,
                    body=result.model_dump_json().encode(),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
            finally:
                conn.close()
        except Exception:
            # Test thread will fail on timeout instead; don't raise on daemon thread.
            return

    t = threading.Thread(target=_run, daemon=True, name=f"stub-worker-{in_queue}")
    t.start()
    return t


def _read_one_result(out_queue: str, *, deadline: float) -> TaskResultMessage:
    conn = pika.BlockingConnection(_params())
    try:
        ch = conn.channel()
        ch.queue_declare(queue=out_queue, durable=True)
        while time.time() < deadline:
            method, _, body = ch.basic_get(queue=out_queue, auto_ack=True)
            if method is not None:
                return messaging.parse_message_to_task_result_object(body.decode())
            time.sleep(0.1)
        raise AssertionError(f"No result on {out_queue} within budget")
    finally:
        conn.close()


def _import_advance_task_state():
    """Load ``_advance_task_state`` + STATUS_* out of the result-processor
    plugin via ``importlib`` so we don't clash with CoreService's own
    ``services/`` package (which is already on sys.path). The plugin
    module imports ``core.*`` at module top so we prepend the plugin
    root first, then load the file by path under a non-colliding
    module name."""
    import importlib.util

    plugin_root = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "plugins", "magellon_result_processor",
        )
    )
    if plugin_root not in sys.path:
        sys.path.insert(0, plugin_root)

    module_path = os.path.join(plugin_root, "services", "task_output_processor.py")
    spec = importlib.util.spec_from_file_location(
        "_rp_task_output_processor", module_path,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.TaskOutputProcessor, mod.STATUS_COMPLETED, mod.STATUS_FAILED


def test_seam_round_trip_ctf_completed():
    """Dispatch a CTF task → stub worker → result → state advance.
    Verifies the whole seam: dispatcher, wire format, state write."""
    in_q = _unique("ctf-in")
    out_q = _unique("ctf-out")
    deadline = time.time() + TEST_BUDGET

    try:
        registry = TaskDispatcherRegistry()
        registry.register(CTF_TASK, RabbitmqTaskDispatcher(queue_name=in_q, rabbitmq_settings=_Settings()))

        task = TaskMessage(
            id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            data={"inputFile": "/tmp/in.mrc", "outputFile": "/tmp/out.mrc"},
            type=CTF_TASK,
        )

        worker = _start_stub_worker(
            in_q, out_q, output_data={"defocus": 1.23}, deadline=deadline,
        )

        assert registry.dispatch(task) is True, "dispatcher.dispatch returned False"

        result = _read_one_result(out_q, deadline=deadline)
        worker.join(timeout=5)

        # Wire contract preserved end-to-end.
        assert result.task_id == task.id
        assert result.job_id == task.job_id
        assert result.type.code == CTF_TASK.code
        assert result.output_data == {"defocus": 1.23}

        # State advance: run the plugin's helper with a mocked DB.
        TaskOutputProcessor, STATUS_COMPLETED, _ = _import_advance_task_state()
        db_task = MagicMock(status_id=0, stage=0)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = db_task

        proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
        proc.db = db
        proc._queue_type_output_config = {}
        proc._advance_task_state(result, status_id=STATUS_COMPLETED)

        assert db_task.status_id == STATUS_COMPLETED
        assert db_task.stage == 2  # CTF = stage 2
    finally:
        _delete_queue(in_q)
        _delete_queue(out_q)


def test_seam_round_trip_motioncor_failed():
    """Same seam, different task type + terminal status."""
    in_q = _unique("mc-in")
    out_q = _unique("mc-out")
    deadline = time.time() + TEST_BUDGET

    try:
        disp = RabbitmqTaskDispatcher(queue_name=in_q, rabbitmq_settings=_Settings())
        task = TaskMessage(id=uuid.uuid4(), job_id=uuid.uuid4(), data={"InMrc": "/tmp/f.mrc"}, type=MOTIONCOR)

        worker = _start_stub_worker(in_q, out_q, output_data={}, deadline=deadline)

        assert disp.dispatch(task) is True

        result = _read_one_result(out_q, deadline=deadline)
        worker.join(timeout=5)

        assert result.type.code == MOTIONCOR.code
        assert result.task_id == task.id

        TaskOutputProcessor, _, STATUS_FAILED = _import_advance_task_state()
        db_task = MagicMock(status_id=0, stage=0)
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = db_task

        proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
        proc.db = db
        proc._queue_type_output_config = {}
        # The stub worker reports success; simulate the processor
        # overriding to FAILED (mirrors the exception path).
        proc._advance_task_state(result, status_id=STATUS_FAILED)

        assert db_task.status_id == STATUS_FAILED
        assert db_task.stage == 1  # MotionCor = stage 1
    finally:
        _delete_queue(in_q)
        _delete_queue(out_q)


# --- Full-stack smoke, skipped by default ---

@pytest.mark.skipif(
    os.environ.get("MAGELLON_E2E_FULL_STACK") != "1",
    reason="full-stack E2E: set MAGELLON_E2E_FULL_STACK=1 and run scripts/e2e_smoke.sh",
)
def test_e2e_full_stack_smoke():
    """Placeholder for the full docker-compose + GPU MotionCor E2E.

    The real assertion logic lives in ``scripts/e2e_smoke.sh`` today
    because it needs to drive ``docker compose up``, wait on service
    health, upload a test .mrc, and poll the job API. When CI gets a
    GPU runner we'll port those steps here with proper pytest
    fixtures; until then this test just documents the gate.
    """
    pytest.skip("full-stack E2E is run via scripts/e2e_smoke.sh, not pytest directly")
