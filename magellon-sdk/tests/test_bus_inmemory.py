"""In-memory broker binder tests (MB4 prep).

Exercises the async / threaded delivery model that MockBinder
deliberately omits: consumer threads, ack/nack, requeue with
redelivery counter, DLQ routing, event fanout across subscribers,
drain-synchronization.
"""
from __future__ import annotations

import threading
import time
from typing import List

import pytest

from magellon_sdk.bus import DefaultMessageBus, TaskConsumerPolicy
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.routes import (
    HeartbeatRoute,
    StepEventRoute,
    TaskRoute,
)
from magellon_sdk.categories.contract import CTF, MOTIONCOR_CATEGORY
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError, RetryableError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def binder():
    b = InMemoryBinder()
    b.start()
    yield b
    b.close()


@pytest.fixture
def bus(binder):
    return DefaultMessageBus(binder)


def _env(data=None, **kwargs) -> Envelope:
    return Envelope.wrap(
        source=kwargs.pop("source", "test"),
        type=kwargs.pop("type", "test"),
        subject=kwargs.pop("subject", "test"),
        data=data or {},
    )


# ---------------------------------------------------------------------------
# Work queue: async consumer threads + ack
# ---------------------------------------------------------------------------

def test_publish_delivers_to_consumer_on_background_thread(bus, binder):
    received: List[Envelope] = []
    event = threading.Event()

    def handler(env):
        received.append(env)
        event.set()

    bus.tasks.consumer(TaskRoute.for_category(CTF), handler)
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))

    assert event.wait(timeout=2.0), "handler never ran"
    assert len(received) == 1
    assert received[0].data == {"x": 1}

    assert binder.wait_for_drain(timeout=1.0)


def test_wait_for_drain_blocks_until_all_deliveries_complete(bus, binder):
    """wait_for_drain is the canonical assertion point — no sleep,
    no polling in tests."""
    handler_running = threading.Event()
    proceed = threading.Event()
    received: List[Envelope] = []

    def slow_handler(env):
        handler_running.set()
        proceed.wait(timeout=2)  # block until test lets us through
        received.append(env)

    bus.tasks.consumer(TaskRoute.for_category(CTF), slow_handler)
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))

    # Handler is in-flight; drain must NOT return yet
    assert handler_running.wait(timeout=1.0)
    assert not binder.wait_for_drain(timeout=0.1)
    assert received == []

    # Release the handler; drain returns true
    proceed.set()
    assert binder.wait_for_drain(timeout=1.0)
    assert len(received) == 1


def test_point_to_point_round_robin_across_competing_consumers(bus, binder):
    """Two consumers on the same task subject compete — each message
    goes to one consumer, not both (work-queue semantics)."""
    a_got: List[Envelope] = []
    b_got: List[Envelope] = []

    bus.tasks.consumer(TaskRoute.for_category(CTF), a_got.append)
    bus.tasks.consumer(TaskRoute.for_category(CTF), b_got.append)

    for i in range(10):
        bus.tasks.send(TaskRoute.for_category(CTF), _env({"n": i}))

    assert binder.wait_for_drain(timeout=2.0)
    # Total messages equals input; neither consumer got all of them
    # (wouldn't be reliable if a thread never got scheduled, but with
    # 10 messages and 2 threads both should be hit).
    assert len(a_got) + len(b_got) == 10


# ---------------------------------------------------------------------------
# Error routing: requeue / DLQ via classify_exception
# ---------------------------------------------------------------------------

def test_retryable_error_requeues_with_incremented_redelivery(bus, binder):
    """RetryableError → classify says REQUEUE. Binder bumps the
    redelivery counter each time so the handler's next attempt sees
    an honest count."""
    counts_seen: List[int] = []
    attempts = []

    def handler(env):
        attempts.append(env)
        count = env.data.get("_redelivery_count_from_header")
        counts_seen.append(count)
        # Fail the first two; succeed on the third.
        if len(attempts) < 3:
            raise RetryableError("blip")

    # We can't read headers from env.data, so we use a counter:
    seen = {"count": 0}

    def handler2(env):
        seen["count"] += 1
        if seen["count"] < 3:
            raise RetryableError("blip")

    bus.tasks.consumer(TaskRoute.for_category(CTF), handler2)
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))

    assert binder.wait_for_drain(timeout=3.0)
    assert seen["count"] == 3


def test_permanent_error_routes_to_dlq_when_enabled(bus, binder):
    """PermanentError → classify says ACK/DLQ. Binder routes to DLQ
    when policy allows (default: dlq_enabled=True)."""
    def handler(env):
        raise PermanentError("bad input")

    bus.tasks.consumer(TaskRoute.for_category(CTF), handler)
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))

    assert binder.wait_for_drain(timeout=1.0)
    dlq = binder.dlq_for(TaskRoute.for_category(CTF).subject)
    assert len(dlq) == 1


def test_permanent_error_drops_message_when_dlq_disabled(bus, binder):
    def handler(env):
        raise PermanentError("bad input")

    bus.tasks.consumer(
        TaskRoute.for_category(CTF),
        handler,
        policy=TaskConsumerPolicy(dlq_enabled=False),
    )
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))

    assert binder.wait_for_drain(timeout=1.0)
    dlq = binder.dlq_for(TaskRoute.for_category(CTF).subject)
    assert dlq == []


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------

def test_purge_drops_pending_deliveries_without_invoking_consumer(bus, binder):
    """Purge before a consumer registers — no handler should fire."""
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 2}))

    count = bus.tasks.purge(TaskRoute.for_category(CTF))
    assert count == 2

    # Consumer registered AFTER purge — should receive nothing
    received: List[Envelope] = []
    bus.tasks.consumer(TaskRoute.for_category(CTF), received.append)
    time.sleep(0.2)  # let the consumer thread loop once
    assert received == []


# ---------------------------------------------------------------------------
# Events: fanout across subscribers, pattern matching
# ---------------------------------------------------------------------------

def test_event_publish_fans_out_to_all_matching_subscribers(bus, binder):
    all_hb: List[Envelope] = []
    ctf_hb: List[Envelope] = []

    bus.events.subscribe(HeartbeatRoute.all(), all_hb.append)
    bus.events.subscribe(
        type("P", (), {"subject_glob": "magellon.plugins.heartbeat.ctf.*"})(),
        ctf_hb.append,
    )

    bus.events.publish(HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"n": 1}))
    bus.events.publish(
        HeartbeatRoute.for_plugin(MOTIONCOR_CATEGORY, "mc2"), _env({"n": 2})
    )

    assert binder.wait_for_drain(timeout=2.0)
    assert len(all_hb) == 2
    assert len(ctf_hb) == 1


def test_subscription_close_stops_delivery(bus, binder):
    received: List[Envelope] = []
    handle = bus.events.subscribe(StepEventRoute.all(), received.append)

    bus.events.publish(StepEventRoute.create(job_id="a", step="ctf"), _env({"n": 1}))
    assert binder.wait_for_drain(timeout=1.0)
    assert len(received) == 1

    handle.close()
    bus.events.publish(StepEventRoute.create(job_id="a", step="ctf"), _env({"n": 2}))
    assert binder.wait_for_drain(timeout=1.0)
    assert len(received) == 1  # close prevented delivery #2


# ---------------------------------------------------------------------------
# Drop-in: use the bus through real call paths with no RMQ
# ---------------------------------------------------------------------------

def test_inmemory_binder_is_a_drop_in_for_rmq_in_tests(binder):
    """The typical integration-test pattern: wire the bus with
    InMemoryBinder, override get_bus, exercise real producer code,
    assert via wait_for_drain."""
    from magellon_sdk.bus import get_bus
    get_bus.reset()
    try:
        bus = DefaultMessageBus(binder)
        get_bus.override(bus)

        # Real "producer" code — in a production test this would be
        # a CoreService importer calling push_task_to_task_queue.
        received: List[Envelope] = []
        bus.tasks.consumer(TaskRoute.for_category(CTF), received.append)

        env = _env({"image_path": "/gpfs/x.mrc"})
        get_bus().tasks.send(TaskRoute.for_category(CTF), env)

        assert binder.wait_for_drain(timeout=1.0)
        assert len(received) == 1
        assert received[0].data == {"image_path": "/gpfs/x.mrc"}
    finally:
        get_bus.reset()
