"""End-to-end tests through the in-memory bus.

These tests exercise *whole processes* — dispatch through the bus,
runner consumes, plugin executes, result publishes back, classifier
routes failures to DLQ, cancel events propagate from one bus
subscriber to a registry that another part of the runner reads, etc.
The :class:`InMemoryBinder` (`magellon-sdk/src/magellon_sdk/bus/binders/inmemory.py`)
gives broker-shaped semantics — separate threads for producer and
consumer, ack/nack/DLQ routing via :func:`classify_exception`, fanout
fan-in for events — without a real RabbitMQ.

What this covers that unit tests don't:

  - The runner's :meth:`_handle_task` raises propagate up to the
    binder, which routes via :func:`classify_exception` (verified by
    looking at the binder's DLQ list / requeue redelivery counter).
  - Cancel events on ``magellon.plugins.cancel.<job_id>`` reach the
    process-wide registry that the plugin reads inside ``execute()``.
  - Persistent config pushed via :class:`ConfigPublisher` round-trips
    through the bus, lands on disk, and survives a subscriber close /
    reopen cycle.

The contracts these tests pin are the most expensive ones to recover
from when broken — silent message loss, stuck cancel state, config
drift after restart. Worth testing through the bus rather than mocked
out, because the bug surface is in the wiring, not in any single
unit.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import List, Optional, Type
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from magellon_sdk.base import PluginBase
from magellon_sdk.bus import DefaultMessageBus, get_bus
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.policy import TaskConsumerPolicy
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.bus.routes.event_route import (
    CancelRoute,
    ConfigRoute,
    StepEventRoute,
)
from magellon_sdk.bus.services.cancel_registry import (
    CancelMessage,
    get_cancel_registry,
    start_cancel_listener,
)
from magellon_sdk.categories.contract import CTF
from magellon_sdk.config_broker import ConfigPublisher, ConfigSubscriber, ConfigUpdate
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError, RetryableError
from magellon_sdk.models import CTF_TASK, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.progress import JobCancelledError
from magellon_sdk.runner import PluginBrokerRunner


# ---------------------------------------------------------------------------
# Shared test plugin + helpers
# ---------------------------------------------------------------------------

class _Input(BaseModel):
    image_path: str = "/x.mrc"


class _Output(BaseModel):
    answer: int


class _Plugin(PluginBase[_Input, _Output]):
    """Configurable test plugin.

    ``raise_factory`` returns the exception (or None) for each call.
    Tracks ``call_count`` so retry-then-DLQ tests can assert how many
    times the binder re-delivered.
    """

    task_category = CTF_TASK

    def __init__(
        self,
        *,
        raise_factory=lambda call_count: None,
        check_cancel_for_job: Optional[UUID] = None,
    ) -> None:
        super().__init__()
        self._raise_factory = raise_factory
        self._check_cancel = check_cancel_for_job
        self.call_count = 0

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="e2e-plugin", version="0.1.0", developer="test")

    @classmethod
    def input_schema(cls) -> Type[_Input]:
        return _Input

    @classmethod
    def output_schema(cls) -> Type[_Output]:
        return _Output

    def execute(self, input_data: _Input, *, reporter=None) -> _Output:
        self.call_count += 1
        # Cooperative cancel check — mirrors what BoundStepReporter does
        # internally on started/progress; we inline it here so the test
        # exercises the bus → registry → plugin path without depending
        # on the reporter wiring.
        if self._check_cancel is not None and get_cancel_registry().is_cancelled(self._check_cancel):
            raise JobCancelledError(f"job {self._check_cancel} cancelled")
        exc = self._raise_factory(self.call_count)
        if exc is not None:
            raise exc
        return _Output(answer=42)


def _result_factory(task: TaskMessage, output: _Output) -> TaskResultMessage:
    return TaskResultMessage(
        task_id=task.id,
        job_id=task.job_id,
        code=200,
        message="ok",
        type=task.type,
        output_data={"answer": output.answer},
    )


def _make_task(*, job_id: Optional[UUID] = None) -> TaskMessage:
    return TaskMessage(
        id=uuid4(),
        job_id=job_id or uuid4(),
        type=CTF_TASK,
        data={"image_path": "/gpfs/x.mrc"},
    )


def _make_runner(plugin: _Plugin, bus: DefaultMessageBus) -> PluginBrokerRunner:
    return PluginBrokerRunner(
        plugin=plugin,
        settings=MagicMock(),  # discovery/config off (no contract on the runner)
        in_queue="ctf_in",
        out_queue="ctf_out",
        result_factory=_result_factory,
        bus=bus,
    )


@pytest.fixture
def bus():
    """Fresh bus + InMemoryBinder per test, registered as the global
    so any code path that calls ``get_bus()`` (e.g.
    ``start_cancel_listener``) finds the test instance.

    The cancel registry is also a process-wide singleton — reset it
    between tests so cancellation state from one test doesn't leak
    into the next.
    """
    binder = InMemoryBinder()
    b = DefaultMessageBus(binder)
    b.start()
    get_bus.reset()
    get_bus.override(b)
    get_cancel_registry().reset()
    try:
        yield b
    finally:
        get_cancel_registry().reset()
        get_bus.reset()
        b.close()


def _binder(bus: DefaultMessageBus) -> InMemoryBinder:
    return bus._binder  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# E2E #1 — multi-task pipeline (the work-queue pattern at scale)
# ---------------------------------------------------------------------------

def test_e2e_multi_task_pipeline(bus):
    """Five tasks dispatched, plugin processes all, five results land
    on the out queue with matching task_ids. The most basic full-stack
    smoke test — covers dispatch → consume → execute → result publish."""
    plugin = _Plugin()
    runner = _make_runner(plugin, bus)
    handle = bus.tasks.consumer(runner._in_route, runner._handle_task)

    try:
        tasks = [_make_task() for _ in range(5)]
        for t in tasks:
            bus.tasks.send(
                TaskRoute.named("ctf_in"),
                Envelope.wrap(source="t", type="t", subject="ctf_in", data=t),
            )

        assert _binder(bus).wait_for_drain(timeout=5.0)

        result_publishes = [
            (s, e) for s, e in _binder(bus).published_tasks if s == "ctf_out"
        ]
        assert len(result_publishes) == 5
        assert plugin.call_count == 5

        result_task_ids = set()
        for _, env in result_publishes:
            result = env.data
            if not isinstance(result, TaskResultMessage):
                result = TaskResultMessage.model_validate(result)
            result_task_ids.add(result.task_id)
        assert result_task_ids == {t.id for t in tasks}
    finally:
        handle.close()


# ---------------------------------------------------------------------------
# E2E #2 — cooperative cancel through the full stack
# ---------------------------------------------------------------------------

def test_e2e_cooperative_cancel_propagates_from_bus_to_plugin(bus):
    """The whole cancel path:
      1. Operator publishes CancelMessage on magellon.plugins.cancel.<job_id>
      2. start_cancel_listener subscribes; its handler marks the registry
      3. Plugin's execute() reads the registry, raises JobCancelledError
      4. Runner catches, publishes a FAILED-with-cancelled result, acks

    Bug surface this catches: any link in the chain where the wiring
    breaks (subscriber doesn't subscribe, handler doesn't decode,
    registry doesn't get marked, plugin can't see the marked state).
    """
    job_id = uuid4()

    listener = start_cancel_listener(bus=bus)
    try:
        plugin = _Plugin(check_cancel_for_job=job_id)
        runner = _make_runner(plugin, bus)
        consumer_handle = bus.tasks.consumer(runner._in_route, runner._handle_task)

        try:
            # Mark the job cancelled — publish through the actual bus
            # path operators would use, not by reaching into the registry.
            bus.events.publish(
                CancelRoute.for_job(job_id),
                Envelope.wrap(
                    source="ops",
                    type="magellon.cancel",
                    subject=f"magellon.plugins.cancel.{job_id}",
                    data=CancelMessage(job_id=job_id, reason="user cancelled"),
                ),
            )
            # Wait for the cancel event to reach the registry before
            # dispatching the task. Otherwise we race the subscriber
            # thread.
            assert _binder(bus).wait_for_drain(timeout=2.0)
            assert get_cancel_registry().is_cancelled(job_id)

            task = _make_task(job_id=job_id)
            bus.tasks.send(
                TaskRoute.named("ctf_in"),
                Envelope.wrap(source="t", type="t", subject="ctf_in", data=task),
            )
            assert _binder(bus).wait_for_drain(timeout=2.0)

            result_publishes = [
                (s, e) for s, e in _binder(bus).published_tasks if s == "ctf_out"
            ]
            assert len(result_publishes) == 1
            result = result_publishes[0][1].data
            if not isinstance(result, TaskResultMessage):
                result = TaskResultMessage.model_validate(result)
            assert result.output_data == {
                "cancelled": True,
                "reason": f"job {job_id} cancelled",
            }
            # Plugin was entered exactly once before raising — the
            # cancel check fires in execute() at call_count=1.
            assert plugin.call_count == 1
        finally:
            consumer_handle.close()
    finally:
        listener.stop()


# ---------------------------------------------------------------------------
# E2E #3 — poison routes to DLQ via the binder's classify_exception
# ---------------------------------------------------------------------------

def test_e2e_permanent_error_routes_to_dlq(bus):
    """A plugin raising PermanentError must hit the DLQ on the very
    first delivery — no retries. The InMemoryBinder honors
    ``policy.dlq_enabled=True`` and uses classify_exception just like
    RmqBinder, so this exercises the same routing path that runs in
    production."""
    plugin = _Plugin(raise_factory=lambda _: PermanentError("bad input"))
    runner = _make_runner(plugin, bus)

    # dlq_enabled in the policy is required for the binder to actually
    # route to its DLQ list (otherwise non-requeue actions just ack-drop).
    handle = bus.tasks.consumer(
        runner._in_route, runner._handle_task,
        policy=TaskConsumerPolicy(dlq_enabled=True),
    )
    try:
        bus.tasks.send(
            TaskRoute.named("ctf_in"),
            Envelope.wrap(source="t", type="t", subject="ctf_in", data=_make_task()),
        )
        assert _binder(bus).wait_for_drain(timeout=2.0)

        # No result published (plugin raised; runner re-raised; binder
        # didn't ack with success).
        result_publishes = [
            (s, e) for s, e in _binder(bus).published_tasks if s == "ctf_out"
        ]
        assert result_publishes == []

        # Message landed on the DLQ side of the binder.
        dlq_deliveries = _binder(bus).dlq_for("ctf_in")
        assert len(dlq_deliveries) == 1
        # Exactly one execute attempt — PermanentError must NOT retry.
        assert plugin.call_count == 1
    finally:
        handle.close()


def test_e2e_untyped_exception_requeues_then_dlqs_at_max_retries(bus):
    """An untyped Exception requeues until classify_exception's
    redelivery_count reaches ``DEFAULT_MAX_RETRIES`` (3), then DLQs.
    This is the safety net for plugins that crash with a generic
    ``RuntimeError``: we don't loop forever, but we don't immediately
    give up either. The InMemoryBinder increments ``x-magellon-redelivery``
    on each requeue exactly the way RmqBinder does."""
    plugin = _Plugin(raise_factory=lambda _: RuntimeError("transient?"))
    runner = _make_runner(plugin, bus)
    handle = bus.tasks.consumer(
        runner._in_route, runner._handle_task,
        policy=TaskConsumerPolicy(dlq_enabled=True),
    )
    try:
        bus.tasks.send(
            TaskRoute.named("ctf_in"),
            Envelope.wrap(source="t", type="t", subject="ctf_in", data=_make_task()),
        )
        assert _binder(bus).wait_for_drain(timeout=5.0)

        # 4 attempts: redelivery counts 0, 1, 2, then 3 (>= max_retries) → DLQ.
        assert plugin.call_count == 4
        dlq = _binder(bus).dlq_for("ctf_in")
        assert len(dlq) == 1
    finally:
        handle.close()


def test_e2e_retryable_error_requeues_indefinitely(bus):
    """RetryableError ALWAYS requeues regardless of redelivery count
    (per classify_exception rules) — it's the plugin's explicit
    "this WILL succeed eventually" signal. We can't test "indefinitely"
    so we cap at 5 attempts and verify all 5 went through; nothing
    landed on DLQ.

    Operationally, an unbounded RetryableError loop is the operator's
    problem to detect via DLQ alarms; the SDK's job is to honor the
    plugin's stated intent."""
    attempts = 5
    raises_remaining = [attempts]

    def _factory(call_count: int):
        if call_count <= attempts:
            return RetryableError("not yet", retry_after_seconds=0)
        return None

    plugin = _Plugin(raise_factory=_factory)
    runner = _make_runner(plugin, bus)
    handle = bus.tasks.consumer(
        runner._in_route, runner._handle_task,
        policy=TaskConsumerPolicy(dlq_enabled=True),
    )
    try:
        bus.tasks.send(
            TaskRoute.named("ctf_in"),
            Envelope.wrap(source="t", type="t", subject="ctf_in", data=_make_task()),
        )
        assert _binder(bus).wait_for_drain(timeout=5.0)

        # Plugin succeeded on attempt #6 — 5 retries + 1 success.
        assert plugin.call_count == attempts + 1
        # Nothing on DLQ — RetryableError never escalates.
        assert _binder(bus).dlq_for("ctf_in") == []
        # One successful result published.
        result_publishes = [
            (s, _) for s, _ in _binder(bus).published_tasks if s == "ctf_out"
        ]
        assert len(result_publishes) == 1
    finally:
        handle.close()


# ---------------------------------------------------------------------------
# E2E #4 — persistent config survives subscriber close + reopen
# ---------------------------------------------------------------------------

def test_e2e_persistent_config_survives_subscriber_restart(bus, tmp_path):
    """Whole bus path for the persistent-config feature:
      1. Subscriber A starts with persisted_path
      2. Publisher pushes ConfigUpdate(persistent=True) via bus.events.publish
      3. Subscriber A receives, applies in-memory AND writes to disk
      4. Subscriber A is closed (simulates plugin-replica restart)
      5. Subscriber B starts on the same path
      6. B's first take_pending() returns the previously-persisted state

    This is what the operator experiences when they push a config and
    then a plugin replica restarts: the next replica picks up where
    the last one left off.
    """
    persisted = tmp_path / "ctf.json"

    # Subscriber A — receives the push.
    sub_a = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    sub_a.start()
    try:
        publisher = ConfigPublisher(bus=bus)
        publisher.publish_to_category(CTF, {"max_defocus": 5.0}, persistent=True)

        assert _binder(bus).wait_for_drain(timeout=2.0)

        # File written.
        assert persisted.exists()
        saved = json.loads(persisted.read_text())
        assert saved == {"max_defocus": 5.0}
    finally:
        sub_a.stop()

    # Subscriber B on the same path — simulates the next replica boot.
    sub_b = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    try:
        # First take_pending after construction returns the loaded state.
        assert sub_b.take_pending() == {"max_defocus": 5.0}
    finally:
        sub_b.stop()


def test_e2e_non_persistent_push_lost_on_restart(bus, tmp_path):
    """The dual of the previous test — a push WITHOUT
    ``persistent=True`` does not write to disk, so subscriber B
    starts empty even though A applied the change in memory."""
    persisted = tmp_path / "ctf.json"

    sub_a = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    sub_a.start()
    try:
        ConfigPublisher(bus=bus).publish_to_category(CTF, {"max_defocus": 5.0})  # persistent=False
        assert _binder(bus).wait_for_drain(timeout=2.0)
        # In-memory it landed:
        assert sub_a.take_pending() == {"max_defocus": 5.0}
        # On-disk it didn't:
        assert not persisted.exists()
    finally:
        sub_a.stop()

    # New replica — no persisted state, starts empty.
    sub_b = ConfigSubscriber(
        settings=MagicMock(), contract=CTF, persisted_path=persisted,
    )
    try:
        assert sub_b.take_pending() is None
    finally:
        sub_b.stop()


# ---------------------------------------------------------------------------
# E2E #5 — step events fan out to multiple subscribers
# ---------------------------------------------------------------------------

def test_e2e_step_events_fan_out_to_multiple_subscribers(bus):
    """The kitchen-radio pattern: one publisher, two subscribers,
    each gets its own copy of every event. CoreService's step-event
    forwarder + an audit-log writer would both look like this.

    Note: ``StepEventRoute.all()`` returns an EventPattern (for
    subscribing); publishing uses concrete routes via
    :meth:`StepEventRoute.create`."""
    job_id = uuid4()
    events_a: List[Envelope] = []
    events_b: List[Envelope] = []

    sub_a = bus.events.subscribe(StepEventRoute.all(), events_a.append)
    sub_b = bus.events.subscribe(StepEventRoute.all(), events_b.append)
    try:
        for i in range(3):
            route = StepEventRoute.create(job_id=str(job_id), step=f"step_{i}")
            bus.events.publish(
                route,
                Envelope.wrap(
                    source="plugin",
                    type=f"magellon.step.event_{i}",
                    subject=route.subject,
                    data={"i": i},
                ),
            )
        assert _binder(bus).wait_for_drain(timeout=2.0)

        # Each subscriber received its own copy of all 3.
        assert len(events_a) == 3
        assert len(events_b) == 3
    finally:
        sub_a.close()
        sub_b.close()


# ---------------------------------------------------------------------------
# E2E #6 — pipeline interleaved with cancel: some succeed, then cancel, rest cancelled
# ---------------------------------------------------------------------------

def test_e2e_pipeline_with_cancel_mid_stream(bus):
    """Mixed-state stream: dispatch a few tasks, let them run; THEN
    publish the cancel; THEN dispatch more tasks. The post-cancel
    tasks must produce cancelled results.

    This exercises a real operator flow: tasks for a session are
    being submitted while the operator decides "stop, this is the
    wrong session" mid-import. Tasks that already completed are
    fine; tasks dispatched after the cancel must abort.

    We dispatch in two batches with explicit synchronization between
    them rather than racing one big batch — that way the test pins
    intent ("post-cancel tasks abort") not timing ("the cancel
    arrived between task 2 and task 3")."""
    job_id = uuid4()
    listener = start_cancel_listener(bus=bus)

    plugin = _Plugin(check_cancel_for_job=job_id)
    runner = _make_runner(plugin, bus)
    handle = bus.tasks.consumer(runner._in_route, runner._handle_task)

    try:
        # Batch 1: two tasks, no cancel yet → both should succeed.
        for _ in range(2):
            bus.tasks.send(
                TaskRoute.named("ctf_in"),
                Envelope.wrap(
                    source="t", type="t", subject="ctf_in",
                    data=_make_task(job_id=job_id),
                ),
            )
        assert _binder(bus).wait_for_drain(timeout=5.0)
        # Snapshot how many results landed before cancel.
        pre_cancel_results = [
            (s, e) for s, e in _binder(bus).published_tasks if s == "ctf_out"
        ]
        assert len(pre_cancel_results) == 2
        assert plugin.call_count == 2

        # Now publish the cancel and wait for the registry to receive it.
        bus.events.publish(
            CancelRoute.for_job(job_id),
            Envelope.wrap(
                source="ops",
                type="magellon.cancel",
                subject=f"magellon.plugins.cancel.{job_id}",
                data=CancelMessage(job_id=job_id),
            ),
        )
        deadline = time.monotonic() + 2.0
        while not get_cancel_registry().is_cancelled(job_id) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert get_cancel_registry().is_cancelled(job_id)

        # Batch 2: three more tasks, all post-cancel → all should
        # produce cancelled results.
        for _ in range(3):
            bus.tasks.send(
                TaskRoute.named("ctf_in"),
                Envelope.wrap(
                    source="t", type="t", subject="ctf_in",
                    data=_make_task(job_id=job_id),
                ),
            )
        assert _binder(bus).wait_for_drain(timeout=5.0)

        all_results = [
            (s, e) for s, e in _binder(bus).published_tasks if s == "ctf_out"
        ]
        assert len(all_results) == 5

        succeeded = 0
        cancelled = 0
        for _, env in all_results:
            r = env.data
            if not isinstance(r, TaskResultMessage):
                r = TaskResultMessage.model_validate(r)
            if r.output_data and r.output_data.get("cancelled") is True:
                cancelled += 1
            else:
                succeeded += 1
        # Pre-cancel batch produced 2 succeeds; post-cancel batch
        # produced 3 cancels. No racing.
        assert succeeded == 2
        assert cancelled == 3
        # Plugin was entered for all 5 tasks (cancel check is INSIDE
        # execute, so the plugin gets called once per task).
        assert plugin.call_count == 5
    finally:
        handle.close()
        listener.stop()
