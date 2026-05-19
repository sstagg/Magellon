"""Executable examples for the three MessageBus lanes.

These tests are intentionally written as usage samples. If you need to
wire a plugin or CoreService caller, start here:

- ``bus.tasks``: durable work queue, one request handled by one worker.
- ``bus.events``: pub-sub fanout, one event delivered to every subscriber.
- ``bus.rpc``: short request/reply, one request answered by one responder.

The examples use :class:`InMemoryBinder` so they run without RabbitMQ,
but the call sites are the same with the RMQ binder.
"""
from __future__ import annotations

import threading
from typing import List

from magellon_sdk.bus import DefaultMessageBus
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.routes import HeartbeatRoute, RpcRoute, TaskRoute
from magellon_sdk.categories.contract import CTF
from magellon_sdk.envelope import Envelope


def _env(data: dict, *, event_type: str = "magellon.example") -> Envelope:
    return Envelope.wrap(
        source="magellon/tests/bus-usage",
        type=event_type,
        subject="example",
        data=data,
    )


def test_tasks_pattern_is_durable_work_for_one_available_worker():
    """Use tasks for real plugin work.

    The caller publishes a task and does not wait for a direct return
    value. One worker consumes the message. Results, if any, should be
    published as a separate task/result envelope rather than returned
    synchronously.
    """
    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)

    with bus:
        route = TaskRoute.for_category(CTF)
        received: List[Envelope] = []
        handled = threading.Event()

        def ctf_worker(request: Envelope) -> None:
            received.append(request)
            handled.set()

        handle = bus.tasks.consumer(route, ctf_worker)

        receipt = bus.tasks.send(
            route,
            _env({"image_path": "/gpfs/session/sum/example.mrc"}),
        )

        assert receipt.ok
        assert handled.wait(timeout=1.0)
        assert binder.wait_for_drain(timeout=1.0)
        assert received[0].data == {"image_path": "/gpfs/session/sum/example.mrc"}

        handle.close()


def test_events_pattern_is_fanout_for_lifecycle_and_notifications():
    """Use events for lifecycle, heartbeat, config, cancel, and progress.

    Every matching subscriber gets a copy. This is the right shape for
    "announce that something happened", not for work assignment.
    """
    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)

    with bus:
        all_heartbeats: List[Envelope] = []
        audit_heartbeats: List[Envelope] = []

        all_handle = bus.events.subscribe(HeartbeatRoute.all(), all_heartbeats.append)
        audit_handle = bus.events.subscribe(HeartbeatRoute.all(), audit_heartbeats.append)

        bus.events.publish(
            HeartbeatRoute.for_plugin(CTF, "ctffind4"),
            _env(
                {"plugin": "ctffind4", "status": "ready"},
                event_type="magellon.plugins.heartbeat",
            ),
        )

        assert binder.wait_for_drain(timeout=1.0)
        assert [e.data["plugin"] for e in all_heartbeats] == ["ctffind4"]
        assert [e.data["plugin"] for e in audit_heartbeats] == ["ctffind4"]

        all_handle.close()
        audit_handle.close()


def test_rpc_pattern_is_short_request_reply_for_control_queries():
    """Use RPC when HTTP would otherwise be needed only for a quick answer.

    The caller does not know a plugin container IP or port. It sends a
    small request to the broker route and waits for one response from
    one available responder. Long work still belongs on ``bus.tasks``.
    """
    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)

    with bus:
        route = RpcRoute.for_backend(CTF, "ctffind4")

        @bus.rpc.responder(route)
        def validate_runtime_config(request: Envelope) -> Envelope:
            exposure = request.data["expected_runtime_seconds"]
            return _env(
                {
                    "accepted": exposure <= 30,
                    "reason": "short control-plane probe",
                },
                event_type="magellon.rpc.response",
            )

        response = bus.rpc.call(
            route,
            _env(
                {"expected_runtime_seconds": 12},
                event_type="magellon.rpc.request",
            ),
            timeout=1.0,
        )

        assert response.data == {
            "accepted": True,
            "reason": "short control-plane probe",
        }
