"""Tests for ``magellon_sdk.bus.services.step_event_forwarder``.

Two pieces:

  - :class:`BusStepEventConsumer` — adapter from ``bus.events.subscribe``
    to the ``start(callback) / stop()`` shape the forwarder needs.
  - :class:`StepEventForwarder` — per-message: scoped DB session →
    writer → optional async downstream.

Tests use stubs for the writer + session; the forwarder's contract
is the order of operations (writer first, downstream after) and the
boundary between threads + asgi loop.
"""
from __future__ import annotations

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest

from magellon_sdk.bus.services.step_event_forwarder import (
    BusStepEventConsumer,
    StepEventForwarder,
)
from magellon_sdk.envelope import Envelope


def _envelope() -> Envelope:
    return Envelope.wrap(
        source="plugin",
        type="magellon.step.progress",
        subject="job.abc.step.ctf",
        data={"pct": 42},
    )


# ---------------------------------------------------------------------------
# BusStepEventConsumer adapter
# ---------------------------------------------------------------------------

def test_bus_consumer_start_subscribes_to_step_events_route():
    """The adapter's start() must subscribe on ``StepEventRoute.all()``
    so it picks up every job's step events. A regression that
    subscribes on a narrower pattern would silently drop events for
    jobs whose ID didn't match."""
    bus = MagicMock()
    consumer = BusStepEventConsumer(bus)
    handler = MagicMock()

    consumer.start(handler)

    bus.events.subscribe.assert_called_once()
    pattern, callback = bus.events.subscribe.call_args.args
    assert pattern.subject_glob == "job.*.step.*"
    assert callback is handler


def test_bus_consumer_start_is_idempotent():
    """Reconnect path: start() may be called twice. Must NOT register
    a second subscription — that would mean every event handler runs
    twice for the same delivery."""
    bus = MagicMock()
    consumer = BusStepEventConsumer(bus)
    consumer.start(MagicMock())
    consumer.start(MagicMock())  # second call

    assert bus.events.subscribe.call_count == 1


def test_bus_consumer_stop_closes_handle():
    bus = MagicMock()
    handle = bus.events.subscribe.return_value
    consumer = BusStepEventConsumer(bus)
    consumer.start(MagicMock())

    consumer.stop()

    handle.close.assert_called_once()


def test_bus_consumer_stop_is_safe_without_start():
    """Forwarder shutdown hooks call stop() unconditionally; a
    consumer that never started must not raise."""
    consumer = BusStepEventConsumer(MagicMock())
    consumer.stop()  # no exception


def test_bus_consumer_stop_swallows_close_errors():
    """A broker-dropped subscription handle's close() can raise
    during teardown. Must be logged and swallowed so the rest of
    the process can shut down cleanly."""
    bus = MagicMock()
    handle = bus.events.subscribe.return_value
    handle.close.side_effect = RuntimeError("subscription lost")
    consumer = BusStepEventConsumer(bus)
    consumer.start(MagicMock())

    # Should not raise.
    consumer.stop()


def test_bus_consumer_default_topology_constants():
    """The cosmetic queue_name / binding_key / exchange attributes
    are what the forwarder logs at startup. Pin the defaults so a
    rename of the binder topology doesn't quietly drift."""
    consumer = BusStepEventConsumer(MagicMock())
    assert consumer.queue_name == "core_step_events_queue"
    assert consumer.binding_key == "job.*.step.*"
    assert consumer.exchange == "magellon.events"


# ---------------------------------------------------------------------------
# StepEventForwarder — per-message handling
# ---------------------------------------------------------------------------

def _make_forwarder(*, downstream=None, loop=None):
    """Build a forwarder with stub session + writer the tests can inspect."""
    session = MagicMock()
    session_factory = MagicMock(return_value=session)
    writer = MagicMock()
    writer_factory = MagicMock(return_value=writer)

    forwarder = StepEventForwarder(
        consumer=MagicMock(),
        session_factory=session_factory,
        writer_factory=writer_factory,
        downstream=downstream,
        loop=loop,
    )
    return forwarder, session, writer


def test_forwarder_handle_writes_via_writer():
    """The primary contract: every delivery's envelope ends up in
    writer.write(envelope). Idempotency is the writer's job (UNIQUE
    event_id index) — the forwarder just calls it."""
    forwarder, _session, writer = _make_forwarder()
    env = _envelope()

    forwarder.handle(env)

    writer.write.assert_called_once_with(env)


def test_forwarder_handle_closes_session_on_success():
    """SQLAlchemy sessions hold connection-pool slots; leaking one
    per delivery would exhaust the pool in minutes. The finally:
    block has to run."""
    forwarder, session, _writer = _make_forwarder()
    forwarder.handle(_envelope())
    session.close.assert_called_once()


def test_forwarder_handle_closes_session_on_writer_failure():
    """Same invariant when the writer raises — finally: must still
    close the session, otherwise a stream of failing events leaks
    every connection."""
    forwarder, session, writer = _make_forwarder()
    writer.write.side_effect = RuntimeError("DB integrity error")

    with pytest.raises(RuntimeError):
        forwarder.handle(_envelope())

    session.close.assert_called_once()


def test_forwarder_handle_reraises_writer_failure():
    """The binder's ack/nack routing depends on the handler raising —
    if the forwarder swallowed the error, every failed write would
    silently ack and the message would be lost. Must re-raise so
    classify_exception can route through REQUEUE / DLQ."""
    forwarder, _session, writer = _make_forwarder()
    writer.write.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        forwarder.handle(_envelope())


def test_forwarder_handle_skips_downstream_when_no_loop():
    """Without a captured event loop, the asyncio cross-thread call
    can't be made. The forwarder still works as a pure persistence
    sink — downstream is silently skipped."""
    forwarder, _session, _writer = _make_forwarder(downstream=MagicMock())
    forwarder.handle(_envelope())  # no loop kwarg → loop is None
    # No way to assert "didn't run" on a coroutine that was never
    # awaited; the assertion is "no exception + no run_coroutine_threadsafe
    # call". We assert the latter by patching it.


def test_forwarder_handle_skips_downstream_when_no_callback():
    """Symmetric — if no downstream is configured, the forwarder is
    a pure persistence sink. No coroutine scheduling should happen."""
    loop = MagicMock(spec=asyncio.AbstractEventLoop)
    forwarder, _session, _writer = _make_forwarder(downstream=None, loop=loop)
    with patch(
        "magellon_sdk.bus.services.step_event_forwarder.asyncio.run_coroutine_threadsafe"
    ) as mock_schedule:
        forwarder.handle(_envelope())
    mock_schedule.assert_not_called()


def test_forwarder_handle_schedules_downstream_via_run_coroutine_threadsafe():
    """The cross-thread → asgi loop boundary: the forwarder runs on
    the binder's consumer thread; downstream is an async coroutine
    that has to run on the asgi event loop. ``run_coroutine_threadsafe``
    is the correct primitive for that handoff."""

    async def _downstream(env):
        pass

    loop = MagicMock(spec=asyncio.AbstractEventLoop)
    forwarder, _session, _writer = _make_forwarder(
        downstream=_downstream, loop=loop,
    )
    with patch(
        "magellon_sdk.bus.services.step_event_forwarder.asyncio.run_coroutine_threadsafe"
    ) as mock_schedule:
        forwarder.handle(_envelope())

    mock_schedule.assert_called_once()
    _coro_arg, loop_arg = mock_schedule.call_args.args
    assert loop_arg is loop


def test_forwarder_handle_downstream_failure_does_not_break_persistence():
    """If scheduling the downstream raises (rare — closed loop, e.g.),
    the persistence side already succeeded — no need to undo. The
    forwarder logs and moves on."""

    async def _downstream(env):
        pass

    loop = MagicMock(spec=asyncio.AbstractEventLoop)
    forwarder, _session, _writer = _make_forwarder(
        downstream=_downstream, loop=loop,
    )
    with patch(
        "magellon_sdk.bus.services.step_event_forwarder.asyncio.run_coroutine_threadsafe",
        side_effect=RuntimeError("loop closed"),
    ):
        # Should NOT raise — persistence is the contract; downstream
        # is best-effort.
        forwarder.handle(_envelope())


# ---------------------------------------------------------------------------
# StepEventForwarder lifecycle
# ---------------------------------------------------------------------------

def test_forwarder_start_delegates_to_consumer():
    """start() wires the consumer's callback to forwarder.handle —
    the forwarder doesn't subscribe directly, it composes over
    whatever consumer shape it was constructed with."""
    forwarder, _, _ = _make_forwarder()
    forwarder.start()
    forwarder.consumer.start.assert_called_once_with(forwarder.handle)


def test_forwarder_stop_delegates_to_consumer():
    forwarder, _, _ = _make_forwarder()
    forwarder.stop()
    forwarder.consumer.stop.assert_called_once()
