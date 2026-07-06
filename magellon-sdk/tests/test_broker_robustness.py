"""Broker-robustness behaviors added in 2.5.0.

Covers, without needing a live broker:

- consumer reconnect loop (fake client: drop → reconnect → resume)
- honest redelivery counting via republish (+ fallback nack on failure)
- async task handlers executed to completion on both binders
- PluginBrokerRunner.consumer_healthy surface

The real-broker complement lives in test_e2e_rabbitmq.py.
"""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import List

import pytest

from magellon_sdk.bus.binders.rmq import binder as rmq_binder
from magellon_sdk.bus.binders.rmq.binder import (
    _REDELIVERY_HEADER,
    _RmqConsumerHandle,
    _invoke,
    _requeue_with_count,
)
from magellon_sdk.envelope import Envelope


# ---------------------------------------------------------------------------
# Reconnect loop
# ---------------------------------------------------------------------------


class _FakeClient:
    """Stands in for RabbitmqClient: first consume drops, second blocks
    until stop_consuming is called."""

    def __init__(self):
        self.connects = 0
        self.consume_calls = 0
        self.connection = None
        self.channel = SimpleNamespace(stop_consuming=self._stop)
        self._stop_event = threading.Event()

    def _stop(self):
        self._stop_event.set()

    def connect(self):
        self.connects += 1

    def close_connection(self):
        pass

    def start_consuming(self):
        self.consume_calls += 1
        if self.consume_calls == 1:
            raise ConnectionError("broker went away")
        self._stop_event.wait(timeout=10)


def test_consumer_handle_reconnects_after_drop(monkeypatch):
    monkeypatch.setattr(rmq_binder, "_RECONNECT_BACKOFF_INITIAL", 0.01)
    client = _FakeClient()
    setup_calls: List[_FakeClient] = []
    binder = SimpleNamespace(_forget_consumer=lambda h: None)

    handle = _RmqConsumerHandle(client, binder, setup_calls.append, "tasks:test")

    t = threading.Thread(target=handle.run_until_shutdown, daemon=True)
    t.start()

    deadline = time.time() + 5
    while client.consume_calls < 2 and time.time() < deadline:
        time.sleep(0.01)
    assert client.consume_calls == 2, "loop did not resume consuming after the drop"
    assert client.connects == 1, "reconnect did not call connect()"
    assert setup_calls == [client], "setup closure not re-run on reconnect"
    assert handle.healthy is True

    # Interrupt start_consuming, then close() so the loop exits.
    client._stop()
    handle.close()
    t.join(timeout=5)
    assert not t.is_alive()
    assert handle.healthy is False


def test_consumer_handle_close_interrupts_backoff(monkeypatch):
    """close() during the backoff wait exits promptly, not after 60s."""
    monkeypatch.setattr(rmq_binder, "_RECONNECT_BACKOFF_INITIAL", 30.0)

    class _AlwaysDown(_FakeClient):
        def start_consuming(self):
            self.consume_calls += 1
            raise ConnectionError("down")

    client = _AlwaysDown()
    handle = _RmqConsumerHandle(
        client, SimpleNamespace(_forget_consumer=lambda h: None),
        lambda c: None, "tasks:test",
    )
    t = threading.Thread(target=handle.run_until_shutdown, daemon=True)
    t.start()
    time.sleep(0.05)  # let it enter the backoff wait
    start = time.time()
    handle.close()
    t.join(timeout=5)
    assert not t.is_alive()
    assert time.time() - start < 5


# ---------------------------------------------------------------------------
# Honest redelivery counting
# ---------------------------------------------------------------------------


class _FakeChannel:
    def __init__(self, publish_raises=False):
        self.publishes = []
        self.acks = []
        self.nacks = []
        self._publish_raises = publish_raises

    def basic_publish(self, **kwargs):
        if self._publish_raises:
            raise ConnectionError("channel dead")
        self.publishes.append(kwargs)

    def basic_ack(self, delivery_tag):
        self.acks.append(delivery_tag)

    def basic_nack(self, delivery_tag, requeue):
        self.nacks.append((delivery_tag, requeue))


def _fake_method(tag=7):
    return SimpleNamespace(delivery_tag=tag, redelivered=False)


def _fake_properties(headers=None):
    return SimpleNamespace(headers=headers or {}, content_type="application/json")


def test_requeue_republishes_with_incremented_count():
    ch = _FakeChannel()
    _requeue_with_count(
        ch, _fake_method(), _fake_properties({_REDELIVERY_HEADER: 1}), b"{}",
        queue_name="q", redelivery_count=1,
    )
    assert len(ch.publishes) == 1
    published = ch.publishes[0]
    assert published["routing_key"] == "q"
    assert published["properties"].headers[_REDELIVERY_HEADER] == 2
    assert ch.acks == [7]
    assert ch.nacks == []


def test_requeue_falls_back_to_nack_when_publish_fails():
    ch = _FakeChannel(publish_raises=True)
    _requeue_with_count(
        ch, _fake_method(), _fake_properties(), b"{}",
        queue_name="q", redelivery_count=0,
    )
    assert ch.acks == []
    assert ch.nacks == [(7, True)]


def test_requeue_honors_bounded_retry_delay(monkeypatch):
    slept = []
    monkeypatch.setattr(rmq_binder.time, "sleep", slept.append)
    ch = _FakeChannel()
    _requeue_with_count(
        ch, _fake_method(), _fake_properties(), b"{}",
        queue_name="q", redelivery_count=0, retry_after_seconds=999,
    )
    assert slept == [rmq_binder._MAX_RETRY_DELAY_S]


# ---------------------------------------------------------------------------
# Async handlers
# ---------------------------------------------------------------------------


def _envelope() -> Envelope:
    return Envelope(source="test", type="test.event", data={"k": "v"})


def test_invoke_runs_async_handler_to_completion():
    ran = []

    async def handler(env):
        ran.append(env.data)

    _invoke(handler, _envelope())
    assert ran == [{"k": "v"}]


def test_invoke_propagates_async_handler_exception():
    async def handler(env):
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        _invoke(handler, _envelope())


def test_inmemory_binder_executes_async_handler():
    from magellon_sdk.bus.bootstrap import build_inmemory_bus
    from magellon_sdk.bus.routes import TaskRoute

    bus = build_inmemory_bus()
    route = TaskRoute.named("async_test_queue")
    done = threading.Event()
    seen = []

    async def handler(env):
        seen.append(env.data)
        done.set()

    handle = bus.tasks.consumer(route, handler)
    bus.tasks.send(route, _envelope())
    assert done.wait(timeout=5), "async handler was not executed"
    assert seen == [{"k": "v"}]
    handle.close()


# ---------------------------------------------------------------------------
# Runner health surface
# ---------------------------------------------------------------------------


def test_runner_consumer_healthy_reflects_handle():
    from magellon_sdk.runner import PluginBrokerRunner

    runner = object.__new__(PluginBrokerRunner)  # skip __init__ plumbing
    runner._task_handle = None
    assert runner.consumer_healthy is False

    runner._task_handle = SimpleNamespace(healthy=False)
    assert runner.consumer_healthy is False

    runner._task_handle = SimpleNamespace(healthy=True)
    assert runner.consumer_healthy is True
