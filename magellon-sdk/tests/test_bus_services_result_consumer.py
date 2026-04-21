"""Unit tests for :mod:`magellon_sdk.bus.services.result_consumer` (MB4.B).

Pins the thin contract:

- ``start_result_consumers(routes, handler, bus)`` calls
  ``bus.tasks.consumer`` once per route, in order, with the same
  handler each time, and returns the handles in the same order.
- Empty ``routes`` is a no-op that doesn't touch the bus.
- ``result_consumer_engine`` (the blocking variant) early-returns
  on empty routes and never touches the bus.
- The bus argument is explicit: there is no fallback to
  ``get_bus()`` inside the service, so callers that want a mock bus
  pass it directly.

End-to-end coverage (envelope decode, processor invocation, DLQ
classification) lives in CoreService's ``tests/test_result_consumer.py``,
which exercises the real wrapper + this service together.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.bus.services.result_consumer import (
    result_consumer_engine,
    start_result_consumers,
)


def _fake_bus_with(consumer_return_values):
    """Build a MagicMock bus whose ``tasks.consumer`` returns the
    given handles in order."""
    bus = MagicMock()
    bus.tasks.consumer.side_effect = consumer_return_values
    return bus


def test_start_registers_one_consumer_per_route_in_order():
    routes = [TaskRoute.named("ctf_out"), TaskRoute.named("mc_out")]
    handler = MagicMock()
    handle_a, handle_b = MagicMock(name="a"), MagicMock(name="b")
    bus = _fake_bus_with([handle_a, handle_b])

    handles = start_result_consumers(routes, handler, bus)

    assert handles == [handle_a, handle_b]
    assert bus.tasks.consumer.call_count == 2
    subjects = [
        call.args[0].subject for call in bus.tasks.consumer.call_args_list
    ]
    assert subjects == ["ctf_out", "mc_out"]
    # Same handler passed on every registration.
    for call in bus.tasks.consumer.call_args_list:
        assert call.args[1] is handler


def test_start_with_empty_routes_is_a_noop():
    bus = MagicMock()
    handles = start_result_consumers([], MagicMock(), bus)

    assert handles == []
    bus.tasks.consumer.assert_not_called()


def test_engine_returns_immediately_on_empty_routes():
    """The blocking engine must not call into the bus or block when
    there's nothing to subscribe to — that's the dormant-deployment
    safety valve."""
    bus = MagicMock()
    # If this called run_until_shutdown on something, the test would hang.
    result_consumer_engine([], MagicMock(), bus)

    bus.tasks.consumer.assert_not_called()


def test_engine_blocks_on_first_handle_and_closes_all_on_return():
    """Happy-path blocking: register N handles, block on handle[0]'s
    run_until_shutdown, close every handle on exit."""
    routes = [TaskRoute.named("a"), TaskRoute.named("b")]
    handler = MagicMock()
    handle_a, handle_b = MagicMock(name="a"), MagicMock(name="b")
    bus = _fake_bus_with([handle_a, handle_b])

    result_consumer_engine(routes, handler, bus)

    handle_a.run_until_shutdown.assert_called_once()
    handle_a.close.assert_called_once()
    handle_b.close.assert_called_once()
