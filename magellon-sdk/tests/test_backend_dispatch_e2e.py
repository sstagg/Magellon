"""End-to-end backend-pin dispatch via the in-memory bus.

Covers what the unit tests in ``test_backend_dispatch.py`` and
``test_bus_dispatcher.py`` (CoreService side) don't: the *full* path
from a real ``PluginLivenessRegistry`` populated by a real
:class:`Announce` through a resolver function that reads the registry,
then through the dispatcher, then onto the in-memory binder, and
finally to a consumer subscribed to the resolved queue.

If any of the pieces drift apart in shape — the registry stops
exposing ``backend_id``, the dispatcher loses the resolver wiring,
the binder stops honoring ``physical_queue`` — this test catches it.
A binder-faithful test double (the in-memory binder mirrors the RMQ
binder's resolver semantics) means no live broker is required.
"""
from __future__ import annotations

import threading
import time
from uuid import uuid4

from magellon_sdk.bus import DefaultMessageBus, get_bus
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.bus.services.liveness_registry import PluginLivenessRegistry
from magellon_sdk.categories.contract import CTF, CategoryContract
from magellon_sdk.discovery import Announce
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import (
    CTF_TASK,
    CtfInput,
    PluginManifest,
    TaskMessage,
)
from magellon_sdk.models.manifest import (
    Capability,
    Transport,
)
from magellon_sdk.models.plugin import PluginInfo


# ---------------------------------------------------------------------------
# Backend-resolver wired against the real liveness registry. Mirrors the
# production ``_live_backend_queue`` in ``CoreService/core/dispatcher_registry.py``,
# minus the local CoreService import. Kept here so the SDK test exercises the
# resolver shape without crossing the package boundary.
# ---------------------------------------------------------------------------

def _resolver_factory(registry: PluginLivenessRegistry):
    def resolve(contract: CategoryContract, backend_id: str):
        target_category = contract.category.name.lower()
        target_backend = backend_id.lower()
        for entry in registry.list_live():
            if (entry.category or "").lower() != target_category:
                continue
            if (entry.backend_id or "").lower() != target_backend:
                continue
            if entry.task_queue:
                return entry.task_queue
        return None
    return resolve


# ---------------------------------------------------------------------------
# Minimal _BusTaskDispatcher copy — the production class lives in
# CoreService and importing it from the SDK tests would invert the
# package dependency. The class is small enough that a faithful copy
# in the test harness is the right trade-off.
# ---------------------------------------------------------------------------

class _BackendNotLive(RuntimeError):
    pass


class _Dispatcher:
    _ENVELOPE_TYPE = "magellon.task.dispatch"
    _ENVELOPE_SOURCE = "magellon/test/dispatcher"

    def __init__(self, *, contract: CategoryContract, backend_resolver):
        self.contract = contract
        self.backend_resolver = backend_resolver
        self.route = TaskRoute.for_category(contract)

    def dispatch(self, task: TaskMessage) -> bool:
        target = getattr(task, "target_backend", None)
        if target:
            queue = self.backend_resolver(self.contract, target)
            if not queue:
                raise _BackendNotLive(target)
            route = TaskRoute.for_backend(self.contract, target, queue)
        else:
            route = self.route
        envelope = Envelope.wrap(
            source=self._ENVELOPE_SOURCE,
            type=self._ENVELOPE_TYPE,
            subject=route.subject,
            data=task,
        )
        return get_bus().tasks.send(route, envelope).ok


# ---------------------------------------------------------------------------
# Test fixtures + helpers
# ---------------------------------------------------------------------------

def _announce(*, plugin_id: str, backend_id: str, task_queue: str) -> Announce:
    return Announce(
        plugin_id=plugin_id,
        plugin_version="0.4.1",
        category="ctf",
        manifest=PluginManifest(
            info=PluginInfo(name=plugin_id, version="0.4.1"),
            backend_id=backend_id,
            capabilities=[Capability.CPU_INTENSIVE],
            supported_transports=[Transport.RMQ],
            default_transport=Transport.RMQ,
        ),
        backend_id=backend_id,
        task_queue=task_queue,
    )


def _ctf_task(target_backend=None) -> TaskMessage:
    data = CtfInput(inputFile="/data/sample.mrc")
    return TaskMessage(
        id=uuid4(),
        job_id=uuid4(),
        type=CTF_TASK,
        data=data.model_dump(),
        target_backend=target_backend,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pinned_dispatch_flows_to_announced_backend_queue():
    """Real registry + real resolver + real dispatcher + in-memory bus
    + a consumer on the resolved queue. A pinned task lands at the
    consumer with the symbolic subject preserved."""
    registry = PluginLivenessRegistry(stale_after_seconds=300)
    registry.record_announce(_announce(
        plugin_id="ctf-ctffind4",
        backend_id="ctffind4",
        task_queue="ctf_ctffind4_q",
    ))
    registry.record_announce(_announce(
        plugin_id="ctf-gctf",
        backend_id="gctf",
        task_queue="ctf_gctf_q",
    ))

    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.override(bus)
    try:
        # Stand up a consumer on each backend's queue; record what
        # arrives on each. Both must see only what was pinned to
        # them.
        ctffind_received = []
        gctf_received = []
        ctffind_event = threading.Event()

        def _ctffind_handler(envelope):
            ctffind_received.append(envelope)
            ctffind_event.set()

        def _gctf_handler(envelope):
            gctf_received.append(envelope)

        from magellon_sdk.bus.policy import TaskConsumerPolicy
        ctffind_handle = bus.tasks.consumer(
            TaskRoute.named("ctf_ctffind4_q"),
            _ctffind_handler,
            policy=TaskConsumerPolicy(),
        )
        gctf_handle = bus.tasks.consumer(
            TaskRoute.named("ctf_gctf_q"),
            _gctf_handler,
            policy=TaskConsumerPolicy(),
        )
        try:
            disp = _Dispatcher(
                contract=CTF,
                backend_resolver=_resolver_factory(registry),
            )

            ok = disp.dispatch(_ctf_task(target_backend="ctffind4"))
            assert ok is True

            # Wait for the consumer to receive — in-memory binder runs
            # consumers on their own threads.
            assert ctffind_event.wait(timeout=2.0), "ctffind handler did not run"
            binder.wait_for_drain(timeout=1.0)

            # ctffind4 got the task; gctf got nothing.
            assert len(ctffind_received) == 1
            assert len(gctf_received) == 0

            envelope = ctffind_received[0]
            # Symbolic subject preserved — operator can grep for the
            # backend pin in audit / log output.
            assert envelope.subject == "magellon.tasks.ctf.ctffind4"
            # Task survived the round trip with target_backend intact.
            received_task = TaskMessage.model_validate(envelope.data)
            assert received_task.target_backend == "ctffind4"
        finally:
            ctffind_handle.close()
            gctf_handle.close()
    finally:
        get_bus.reset()
        bus.close()


def test_unpinned_dispatch_uses_category_default_route_in_e2e():
    """Same harness as above but no target_backend. Task lands on the
    category-default subject ``magellon.tasks.ctf``, not on either
    backend's queue. Confirms that the X.7 routing change does not
    affect today's category-wide path."""
    registry = PluginLivenessRegistry(stale_after_seconds=300)
    registry.record_announce(_announce(
        plugin_id="ctf-ctffind4",
        backend_id="ctffind4",
        task_queue="ctf_ctffind4_q",
    ))

    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.override(bus)
    try:
        category_received = []
        category_event = threading.Event()
        from magellon_sdk.bus.policy import TaskConsumerPolicy

        def _category_handler(envelope):
            category_received.append(envelope)
            category_event.set()

        cat_handle = bus.tasks.consumer(
            TaskRoute.for_category(CTF),
            _category_handler,
            policy=TaskConsumerPolicy(),
        )
        try:
            disp = _Dispatcher(
                contract=CTF,
                backend_resolver=_resolver_factory(registry),
            )
            ok = disp.dispatch(_ctf_task())
            assert ok is True

            assert category_event.wait(timeout=2.0)
            binder.wait_for_drain(timeout=1.0)

            assert len(category_received) == 1
            assert category_received[0].subject == "magellon.tasks.ctf"
        finally:
            cat_handle.close()
    finally:
        get_bus.reset()
        bus.close()


def test_pinned_dispatch_raises_when_backend_not_live_in_e2e():
    """A backend that was never announced has no entry in the
    registry — the resolver returns None and the dispatcher raises.
    Hard-fail beats silent fallback."""
    registry = PluginLivenessRegistry(stale_after_seconds=300)
    registry.record_announce(_announce(
        plugin_id="ctf-ctffind4",
        backend_id="ctffind4",
        task_queue="ctf_ctffind4_q",
    ))

    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.override(bus)
    try:
        disp = _Dispatcher(
            contract=CTF,
            backend_resolver=_resolver_factory(registry),
        )
        try:
            disp.dispatch(_ctf_task(target_backend="gocsf"))
        except _BackendNotLive as e:
            assert "gocsf" in str(e)
            return
        raise AssertionError("dispatcher should have raised BackendNotLive")
    finally:
        get_bus.reset()
        bus.close()


def test_pinned_dispatch_skips_stale_announce_in_e2e():
    """An announce older than the staleness window is filtered out by
    list_live. The resolver sees nothing matching, so a pinned dispatch
    refuses with BackendNotLive — the operator who pinned to a now-dead
    backend gets a hard error instead of a silent fallback."""
    registry = PluginLivenessRegistry(stale_after_seconds=0.1)
    registry.record_announce(_announce(
        plugin_id="ctf-ctffind4",
        backend_id="ctffind4",
        task_queue="ctf_ctffind4_q",
    ))
    # Sleep just past the window. 0.15s = 1.5x the threshold.
    time.sleep(0.15)

    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.override(bus)
    try:
        disp = _Dispatcher(
            contract=CTF,
            backend_resolver=_resolver_factory(registry),
        )
        try:
            disp.dispatch(_ctf_task(target_backend="ctffind4"))
        except _BackendNotLive:
            return
        raise AssertionError(
            "dispatcher should have raised BackendNotLive on stale announce"
        )
    finally:
        get_bus.reset()
        bus.close()
