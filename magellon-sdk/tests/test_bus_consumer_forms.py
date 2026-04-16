"""Dual-form consumer / subscribe API tests (MB1.3).

Pins the invariant from spec §4.2: ``bus.tasks.consumer`` and
``bus.events.subscribe`` accept either:

  - a handler as the second positional argument (imperative form —
    required for bound methods, lambdas, dynamically-bound handlers),
  - or no handler at all, returning a decorator (for module-level
    plain functions).

Both forms register the same underlying handler; the decorator is
sugar over the imperative call. This test lives or dies at the
facade layer — the binder never sees the difference.
"""
from __future__ import annotations

from typing import List

import pytest

from magellon_sdk.bus import (
    ConsumerHandle,
    DefaultMessageBus,
    SubscriptionHandle,
    TaskConsumerPolicy,
)
from magellon_sdk.bus.binders.mock import MockBinder
from magellon_sdk.bus.routes import HeartbeatRoute, TaskRoute
from magellon_sdk.categories.contract import CTF
from magellon_sdk.envelope import Envelope


@pytest.fixture
def bus():
    b = DefaultMessageBus(MockBinder())
    b.start()
    yield b
    b.close()


def _env(data=None) -> Envelope:
    return Envelope.wrap(
        source="test", type="test", subject="test", data=data or {}
    )


# ---------------------------------------------------------------------------
# Imperative form — the canonical shape for class-based services
# ---------------------------------------------------------------------------

class _StepEventForwarder:
    """Representative class-based service. MB5's step-event
    forwarder looks like this. Bound method handler is why the
    imperative form has to exist."""

    def __init__(self, bus):
        self.received: List[Envelope] = []
        self._handle = bus.events.subscribe(HeartbeatRoute.all(), self._on_heartbeat)

    def _on_heartbeat(self, env: Envelope) -> None:
        self.received.append(env)

    def close(self):
        self._handle.close()


def test_imperative_task_consumer_returns_consumer_handle(bus):
    received: List[Envelope] = []

    def handler(env):
        received.append(env)

    handle = bus.tasks.consumer(TaskRoute.for_category(CTF), handler)

    assert isinstance(handle, ConsumerHandle)
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))
    assert len(received) == 1


def test_imperative_event_subscribe_returns_subscription_handle(bus):
    received: List[Envelope] = []
    handle = bus.events.subscribe(HeartbeatRoute.all(), received.append)

    assert isinstance(handle, SubscriptionHandle)
    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"status": "ok"})
    )
    assert len(received) == 1


def test_imperative_form_binds_methods_correctly(bus):
    """The whole reason the imperative form exists — a bound method
    registered directly, no decorator gymnastics."""
    forwarder = _StepEventForwarder(bus)

    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"pulse": 1})
    )
    assert len(forwarder.received) == 1
    assert forwarder.received[0].data == {"pulse": 1}

    forwarder.close()
    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"pulse": 2})
    )
    assert len(forwarder.received) == 1  # close() unsubscribed


# ---------------------------------------------------------------------------
# Decorator form — sugar for module-level functions
# ---------------------------------------------------------------------------

def test_decorator_task_consumer_registers_and_returns_handle(bus):
    received: List[Envelope] = []

    @bus.tasks.consumer(TaskRoute.for_category(CTF))
    def handle(env):
        received.append(env)

    # The decorator returns the ConsumerHandle, not the function.
    assert isinstance(handle, ConsumerHandle)
    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))
    assert len(received) == 1


def test_decorator_event_subscribe_registers_and_returns_handle(bus):
    received: List[Envelope] = []

    @bus.events.subscribe(HeartbeatRoute.all())
    def _on_hb(env):
        received.append(env)

    assert isinstance(_on_hb, SubscriptionHandle)
    bus.events.publish(
        HeartbeatRoute.for_plugin(CTF, "ctffind4"), _env({"pulse": 1})
    )
    assert len(received) == 1


def test_decorator_accepts_policy_kwarg(bus):
    """Policy must pass through the decorator form too —
    ``@bus.tasks.consumer(route, policy=TaskConsumerPolicy(...))``
    is how plugins opt into prefetch / retries / DLQ."""
    received: List[Envelope] = []
    custom_policy = TaskConsumerPolicy(prefetch=1, max_retries=5)

    @bus.tasks.consumer(TaskRoute.for_category(CTF), policy=custom_policy)
    def handle(env):
        received.append(env)

    bus.tasks.send(TaskRoute.for_category(CTF), _env({"x": 1}))
    assert len(received) == 1


# ---------------------------------------------------------------------------
# Both forms produce identical effect
# ---------------------------------------------------------------------------

def test_both_forms_register_equivalent_consumers():
    """Same handler registered two ways should behave identically.
    Running the same sequence of sends through each must produce
    the same handler-invocation record."""
    # Imperative form
    imp_binder = MockBinder()
    imp_bus = DefaultMessageBus(imp_binder)
    imp_bus.start()

    imp_received: List[Envelope] = []

    def imp_handler(env):
        imp_received.append(env)

    imp_bus.tasks.consumer(TaskRoute.for_category(CTF), imp_handler)

    # Decorator form
    dec_binder = MockBinder()
    dec_bus = DefaultMessageBus(dec_binder)
    dec_bus.start()

    dec_received: List[Envelope] = []

    @dec_bus.tasks.consumer(TaskRoute.for_category(CTF))
    def dec_handler(env):
        dec_received.append(env)

    # Same traffic through both
    payloads = [{"n": 1}, {"n": 2}, {"n": 3}]
    for p in payloads:
        imp_bus.tasks.send(TaskRoute.for_category(CTF), _env(p))
        dec_bus.tasks.send(TaskRoute.for_category(CTF), _env(p))

    assert [e.data for e in imp_received] == payloads
    assert [e.data for e in dec_received] == payloads

    imp_bus.close()
    dec_bus.close()
