"""Concrete RPC flow: CoreService -> particle-picking plugin.

This is the migration shape for plugin HTTP control calls:

1. CoreService resolves a live particle-picking backend from liveness.
2. CoreService calls ``bus.rpc`` on that backend's RPC queue.
3. One plugin replica answers with a small response envelope.
4. No task row, result queue, artifact, or plugin HTTP port is involved.

With RabbitMQ the binder creates the reply queue automatically per call
and uses ``correlation_id`` to match the response. This test uses the
in-memory binder, so the call sites stay visible without a live broker.
"""
from __future__ import annotations

from magellon_sdk.bus import DefaultMessageBus
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.routes import RpcRoute
from magellon_sdk.envelope import Envelope


def _env(data: dict, *, event_type: str) -> Envelope:
    return Envelope.wrap(
        source="magellon/tests/particle-picker-rpc",
        type=event_type,
        subject="particle-picking",
        data=data,
    )


def test_coreservice_calls_particle_picker_backend_without_http_port_discovery():
    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)

    # What CoreService would learn from the liveness registry. The task
    # queue remains for long-running picking jobs; this RPC queue is only
    # for short control-plane questions.
    backend_id = "boxnet-picker"
    rpc_queue = "particle_picking_boxnet_rpc_queue"

    # Plugin side: the particle-picking worker listens on its RPC queue.
    # In RabbitMQ, multiple boxnet replicas would consume this same queue;
    # one available replica answers each call.
    plugin_route = RpcRoute.named(
        f"magellon.rpc.particle_picking.{backend_id}",
        queue=rpc_queue,
    )

    with bus:

        @bus.rpc.responder(plugin_route)
        def boxnet_validate_request(request: Envelope) -> Envelope:
            image_path = request.data["image_path"]
            threshold = request.data["engine_opts"].get("threshold", 0.5)
            return _env(
                {
                    "backend_id": backend_id,
                    "accepted": image_path.endswith(".mrc") and 0.0 <= threshold <= 1.0,
                    "normalized": {
                        "image_path": image_path,
                        "threshold": threshold,
                    },
                },
                event_type="magellon.rpc.particle_picking.validate.response",
            )

        # CoreService side: no container IP/port. It calls the same
        # symbolic backend route with the physical queue resolved from
        # liveness.
        coreservice_route = RpcRoute.named(
            f"magellon.rpc.particle_picking.{backend_id}",
            queue=rpc_queue,
        )

        response = bus.rpc.call(
            coreservice_route,
            _env(
                {
                    "image_path": "/gpfs/session/sum/example.mrc",
                    "engine_opts": {"threshold": 0.35},
                },
                event_type="magellon.rpc.particle_picking.validate.request",
            ),
            timeout=1.0,
        )

    assert response.data == {
        "backend_id": "boxnet-picker",
        "accepted": True,
        "normalized": {
            "image_path": "/gpfs/session/sum/example.mrc",
            "threshold": 0.35,
        },
    }
    assert binder.rpc_calls[0][0] == "magellon.rpc.particle_picking.boxnet-picker"
    assert binder.published_tasks == []
