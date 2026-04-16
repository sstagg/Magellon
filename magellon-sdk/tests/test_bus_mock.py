"""Mock binder + facade round-trip tests (MB1.3).

Pins the behavior that MB2 (RMQ binder) and MB4 (consumer migration)
will rely on:

  - ``bus.tasks.send(route, env)`` + ``bus.tasks.consumer(route, fn)``
    round-trips synchronously through the mock binder.
  - ``bus.events.publish`` fans out to matching subscribers.
  - Wildcard matching follows the NATS-style convention documented
    on ``EventPattern``.
  - ``get_bus.override(mock)`` swaps the bus for tests without any
    module-import-time race.
"""
from __future__ import annotations

from typing import List

import pytest

from magellon_sdk.bus import (
    DefaultMessageBus,
    PublishReceipt,
    TaskConsumerPolicy,
    get_bus,
)
from magellon_sdk.bus.binders.mock import MockBinder, _matches
from magellon_sdk.bus.routes import (
    AnnounceRoute,
    ConfigRoute,
    HeartbeatRoute,
    StepEventRoute,
    TaskRoute,
)
from magellon_sdk.categories.contract import CTF, MOTIONCOR_CATEGORY
from magellon_sdk.envelope import Envelope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def binder() -> MockBinder:
    return MockBinder()


@pytest.fixture
def bus(binder: MockBinder) -> DefaultMessageBus:
    b = DefaultMessageBus(binder)
    b.start()
    yield b
    b.close()


def _env(data: dict) -> Envelope:
    return Envelope.wrap(
        source="magellon/tests",
        type="magellon.test.event",
        subject="test",
        data=data,
    )


# ---------------------------------------------------------------------------
# Glob matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "glob, subject, expected",
    [
        # exact match
        ("magellon.tasks.ctf", "magellon.tasks.ctf", True),
        ("magellon.tasks.ctf", "magellon.tasks.motioncor", False),
        # single-segment wildcard
        ("magellon.tasks.*", "magellon.tasks.ctf", True),
        ("magellon.tasks.*", "magellon.tasks.ctf.result", False),
        # tail wildcard
        ("magellon.plugins.heartbeat.>", "magellon.plugins.heartbeat.ctf.ctffind4", True),
        ("magellon.plugins.heartbeat.>", "magellon.plugins.announce.ctf.ctffind4", False),
        # step event pattern preserves today's shape
        ("job.*.step.*", "job.42.step.ctf", True),
        ("job.*.step.*", "job.42.step.ctf.detail", False),
        # mixed
        ("magellon.plugins.config.>", "magellon.plugins.config.broadcast", True),
        ("magellon.plugins.config.>", "magellon.plugins.config.ctf", True),
    ],
)
def test_glob_matches(glob, subject, expected):
    assert _matches(glob, subject) is expected


# ---------------------------------------------------------------------------
# Work-queue round-trip
# ---------------------------------------------------------------------------

def test_task_send_dispatches_to_registered_consumer(bus, binder):
    route = TaskRoute.for_category(CTF)
    received: List[Envelope] = []

    def handler(env: Envelope) -> None:
        received.append(env)

    bus.tasks.consumer(route, handler)
    receipt = bus.tasks.send(route, _env({"image": "x.mrc"}))

    assert isinstance(receipt, PublishReceipt) and receipt.ok
    assert len(received) == 1
    assert received[0].data == {"image": "x.mrc"}
    assert binder.published_tasks == [(route.subject, received[0])]


def test_task_send_with_no_consumer_still_succeeds(bus, binder):
    """A send without a consumer is a valid state — the binder just
    enqueues. Tests that assert handler invocation must register first."""
    route = TaskRoute.for_category(CTF)
    receipt = bus.tasks.send(route, _env({"image": "x.mrc"}))
    assert receipt.ok
    assert len(binder.published_tasks) == 1


def test_task_handler_return_is_captured(bus, binder):
    """Handlers that return an Envelope represent the result route
    publication. MB2's RMQ binder will auto-publish; the mock just
    captures for inspection."""
    route = TaskRoute.for_category(CTF)

    def handler(env: Envelope) -> Envelope:
        return _env({"answer": 42})

    bus.tasks.consumer(route, handler)
    bus.tasks.send(route, _env({"image": "x.mrc"}))

    assert len(binder.handler_returns) == 1
    assert binder.handler_returns[0].data == {"answer": 42}


def test_task_purge_returns_count_and_clears(bus, binder):
    route = TaskRoute.for_category(CTF)
    bus.tasks.send(route, _env({"n": 1}))
    bus.tasks.send(route, _env({"n": 2}))

    count = bus.tasks.purge(route)

    assert count == 2
    assert binder.published_tasks == []
    assert binder.purge_counts == [(route.subject, 2)]


# ---------------------------------------------------------------------------
# Pub-sub round-trip
# ---------------------------------------------------------------------------

def test_event_publish_fans_out_to_matching_subscribers(bus, binder):
    ctf_heartbeats: List[Envelope] = []
    all_heartbeats: List[Envelope] = []

    bus.events.subscribe(HeartbeatRoute.all(), all_heartbeats.append)
    bus.events.subscribe(
        # Pattern for just CTF heartbeats
        type("P", (), {"subject_glob": "magellon.plugins.heartbeat.ctf.*"})(),
        ctf_heartbeats.append,
    )

    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"),
        _env({"status": "ready"}),
    )
    bus.events.publish(
        HeartbeatRoute.for_plugin(MOTIONCOR_CATEGORY, "motioncor2"),
        _env({"status": "ready"}),
    )

    assert len(all_heartbeats) == 2
    assert len(ctf_heartbeats) == 1
    assert ctf_heartbeats[0].data == {"status": "ready"}


def test_subscription_close_stops_delivery(bus):
    received: List[Envelope] = []
    handle = bus.events.subscribe(HeartbeatRoute.all(), received.append)

    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"n": 1})
    )
    handle.close()
    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"n": 2})
    )

    assert len(received) == 1
    assert received[0].data == {"n": 1}


def test_step_events_match_today_forwarder_binding(bus, binder):
    """The step-event forwarder binds ``job.*.step.*`` today.
    Confirm the mock binder's pattern matching routes envelopes
    accordingly — this is the invariant MB5's forwarder migration
    will rely on."""
    step_events: List[Envelope] = []
    bus.events.subscribe(StepEventRoute.all(), step_events.append)

    bus.events.publish(
        StepEventRoute.create(job_id="abc", step="ctf"), _env({"pct": 50})
    )
    # An announce on a different shape must NOT hit the step handler
    bus.events.publish(
        AnnounceRoute.for_plugin(CTF, "ctffind4"),
        _env({"version": "4.1"}),
    )

    assert len(step_events) == 1
    assert step_events[0].data == {"pct": 50}


# ---------------------------------------------------------------------------
# Config route — broadcast + per-category on one pattern
# ---------------------------------------------------------------------------

def test_config_route_all_catches_broadcast_and_per_category(bus):
    """The ConfigSubscriber will use ``ConfigRoute.all()`` (MB5). It
    must receive both per-category pushes and global broadcasts."""
    received: List[Envelope] = []
    bus.events.subscribe(ConfigRoute.all(), received.append)

    bus.events.publish(ConfigRoute.for_category(CTF), _env({"k": 1}))
    bus.events.publish(ConfigRoute.broadcast(), _env({"k": 2}))

    assert [e.data for e in received] == [{"k": 1}, {"k": 2}]


# ---------------------------------------------------------------------------
# get_bus registry
# ---------------------------------------------------------------------------

class TestGetBusRegistry:
    """get_bus() semantics — override, factory, reset."""

    def setup_method(self) -> None:
        get_bus.reset()
        get_bus._factory = None  # type: ignore[attr-defined]

    def teardown_method(self) -> None:
        get_bus.reset()
        get_bus._factory = None  # type: ignore[attr-defined]

    def test_get_bus_without_factory_or_override_raises(self):
        with pytest.raises(RuntimeError, match="No MessageBus configured"):
            get_bus()

    def test_override_swaps_in_a_specific_bus(self):
        mock_bus = DefaultMessageBus(MockBinder())
        get_bus.override(mock_bus)
        assert get_bus() is mock_bus

    def test_factory_is_called_lazily_once(self):
        call_count = {"n": 0}

        def _factory() -> DefaultMessageBus:
            call_count["n"] += 1
            return DefaultMessageBus(MockBinder())

        get_bus.set_factory(_factory)
        first = get_bus()
        second = get_bus()

        assert first is second
        assert call_count["n"] == 1

    def test_reset_clears_override_and_next_call_rebuilds(self):
        get_bus.set_factory(lambda: DefaultMessageBus(MockBinder()))
        first = get_bus()
        get_bus.reset()
        second = get_bus()
        assert first is not second

    def test_override_then_reset_without_factory_raises(self):
        get_bus.override(DefaultMessageBus(MockBinder()))
        get_bus.reset()
        with pytest.raises(RuntimeError, match="No MessageBus configured"):
            get_bus()


# ---------------------------------------------------------------------------
# Lifecycle — start / close
# ---------------------------------------------------------------------------

def test_bus_start_invokes_binder_start():
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    assert not binder.started
    bus.start()
    assert binder.started
    bus.close()
    assert binder.closed


def test_bus_context_manager_handles_lifecycle():
    binder = MockBinder()
    with DefaultMessageBus(binder) as bus:
        assert binder.started
        route = TaskRoute.for_category(CTF)
        bus.tasks.send(route, _env({"x": 1}))
    assert binder.closed
