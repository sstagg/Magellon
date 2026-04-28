"""Tests for :class:`PluginBrokerRunner`.

Post-MB4.1 the runner no longer owns a pika callback — task I/O flows
through the MessageBus and the binder handles ack/nack/DLQ routing.
These tests pin the runner's remaining responsibilities:

- ``_process(bytes) -> bytes``: the pure-function transformation
  (decode task → validate → run → encode result). Unchanged from
  pre-MB4 tests; this is the compat shape plugin-level tests reuse.
- ``_handle_task(envelope) -> None``: the bus-side handler. Runs the
  plugin and publishes the result via ``bus.tasks.send``. Raising
  propagates up to the binder for classification.
- End-to-end with :class:`InMemoryBinder`: a task dispatched via
  ``bus.tasks.send`` round-trips through the runner and emits a
  result on the out-route. No RMQ required.
- Provenance stamping, input validation, pending-config drain —
  inherited behavior that still applies.
"""
from __future__ import annotations

from typing import List, Type
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from magellon_sdk.base import PluginBase
from magellon_sdk.bus import DefaultMessageBus, get_bus
from magellon_sdk.bus.binders.inmemory import InMemoryBinder
from magellon_sdk.bus.binders.mock import MockBinder
from magellon_sdk.bus.routes import TaskResultRoute, TaskRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError, RetryableError
from magellon_sdk.models import CTF_TASK, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.runner import PluginBrokerRunner


# ---------------------------------------------------------------------------
# Test plugin
# ---------------------------------------------------------------------------

class _StubInput(BaseModel):
    image_path: str = ""


class _StubOutput(BaseModel):
    answer: int


class _StubPlugin(PluginBase[_StubInput, _StubOutput]):
    task_category = CTF_TASK

    def __init__(self, *, raise_on_run: Exception | None = None) -> None:
        super().__init__()
        self._raise = raise_on_run

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="stub-plugin", version="0.42.0", developer="test")

    @classmethod
    def input_schema(cls) -> Type[_StubInput]:
        return _StubInput

    @classmethod
    def output_schema(cls) -> Type[_StubOutput]:
        return _StubOutput

    def execute(self, input_data: _StubInput, *, reporter=None) -> _StubOutput:
        if self._raise is not None:
            raise self._raise
        return _StubOutput(answer=42)


def _result_factory(task: TaskMessage, output: _StubOutput) -> TaskResultMessage:
    return TaskResultMessage(
        task_id=task.id,
        job_id=task.job_id,
        code=200,
        message="ok",
        type=task.type,
        output_data={"answer": output.answer},
    )


def _make_task() -> TaskMessage:
    return TaskMessage(
        id=uuid4(),
        job_id=uuid4(),
        type=CTF_TASK,
        data={"image_path": "/gpfs/x.mrc"},
    )


def _make_runner(
    plugin: _StubPlugin, *, bus=None
) -> PluginBrokerRunner:
    return PluginBrokerRunner(
        plugin=plugin,
        settings=MagicMock(),  # discovery/config stay off (no contract)
        in_queue="ctf_in",
        out_queue="ctf_out",
        result_factory=_result_factory,
        bus=bus,
    )


# ---------------------------------------------------------------------------
# Pure-function pipeline (unchanged from pre-MB4.1)
# ---------------------------------------------------------------------------

def test_process_returns_result_with_provenance_stamped():
    """A clean run produces a TaskResultMessage whose plugin_id /
    plugin_version come from the plugin's own get_info()."""
    runner = _make_runner(_StubPlugin())
    body = _make_task().model_dump_json().encode()

    out_bytes = runner._process(body)

    out = TaskResultMessage.model_validate_json(out_bytes)
    assert out.plugin_id == "stub-plugin"
    assert out.plugin_version == "0.42.0"
    assert out.output_data == {"answer": 42}


def test_process_preserves_explicit_provenance_set_by_factory():
    """If the result_factory already filled provenance (engine
    wrapper case), the harness must not clobber it."""
    runner = _make_runner(_StubPlugin())
    runner.result_factory = lambda t, o: TaskResultMessage(
        task_id=t.id,
        plugin_id="gctf-2.1",
        plugin_version="2.1.0",
    )
    body = _make_task().model_dump_json().encode()

    out_bytes = runner._process(body)

    out = TaskResultMessage.model_validate_json(out_bytes)
    assert out.plugin_id == "gctf-2.1"
    assert out.plugin_version == "2.1.0"


def test_process_validates_input_against_plugin_schema():
    """A task whose data doesn't match the plugin's input_schema must
    raise — preferably *before* the plugin's bespoke logic runs."""

    class _StrictInput(BaseModel):
        required_field: int

    class _StrictPlugin(_StubPlugin):
        @classmethod
        def input_schema(cls):
            return _StrictInput

    runner = _make_runner(_StrictPlugin())
    body = _make_task().model_dump_json().encode()

    with pytest.raises(Exception):  # pydantic ValidationError
        runner._process(body)


# ---------------------------------------------------------------------------
# Dynamic config — same semantics post-MB4.1
# ---------------------------------------------------------------------------

def test_pending_config_is_applied_between_tasks():
    """A config push that arrives between deliveries must reach the
    plugin's configure() before the next run."""
    plugin = _StubPlugin()
    runner = _make_runner(plugin)
    runner._config_subscriber = MagicMock()
    runner._config_subscriber.take_pending.return_value = {"new_setting": "v2"}

    runner._process(_make_task().model_dump_json().encode())

    assert plugin._config.get("new_setting") == "v2"


def test_no_pending_config_skips_configure_call():
    """Idle ticks must not churn through configure() — the plugin's
    state machine treats configure() as a transition, so no-op pushes
    would needlessly bump it."""
    plugin = _StubPlugin()
    plugin.configure = MagicMock()  # type: ignore[method-assign]
    runner = _make_runner(plugin)
    runner._config_subscriber = MagicMock()
    runner._config_subscriber.take_pending.return_value = None

    runner._process(_make_task().model_dump_json().encode())

    plugin.configure.assert_not_called()


def test_configure_failure_does_not_break_task_processing():
    """A bad configure() must not derail an otherwise valid task —
    the plugin keeps the previous config and the result still ships.
    Otherwise one bad config push could DLQ every queued task."""
    plugin = _StubPlugin()
    plugin.configure = MagicMock(side_effect=RuntimeError("bad knob"))  # type: ignore[method-assign]
    runner = _make_runner(plugin)
    runner._config_subscriber = MagicMock()
    runner._config_subscriber.take_pending.return_value = {"x": 1}

    out_bytes = runner._process(_make_task().model_dump_json().encode())
    out = TaskResultMessage.model_validate_json(out_bytes)
    assert out.output_data == {"answer": 42}


# ---------------------------------------------------------------------------
# _handle_task — new bus-side entry point
# ---------------------------------------------------------------------------

def test_handle_task_publishes_result_envelope_via_bus(monkeypatch):
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(), bus=bus)
        task = _make_task()
        env = Envelope.wrap(
            source="test",
            type="magellon.task.dispatch",
            subject="ctf_in",
            data=task,
        )

        result_val = runner._handle_task(env)

        assert result_val is None  # binder acks on None return
        assert len(binder.published_tasks) == 1
        subject, result_envelope = binder.published_tasks[0]
        assert subject == "ctf_out"
        assert result_envelope.subject == "ctf_out"
        # The published envelope's data is a TaskResultMessage
        result_dto = result_envelope.data
        if not isinstance(result_dto, TaskResultMessage):
            result_dto = TaskResultMessage.model_validate(result_dto)
        assert result_dto.plugin_id == "stub-plugin"
        assert result_dto.output_data == {"answer": 42}
    finally:
        bus.close()


def test_handle_task_propagates_exceptions_to_binder():
    """Exceptions must propagate up so classify_exception can route
    them (REQUEUE / DLQ). The runner never swallows."""
    bus = DefaultMessageBus(MockBinder())
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(raise_on_run=PermanentError("bad")), bus=bus)
        env = Envelope.wrap(
            source="test", type="t", subject="ctf_in", data=_make_task()
        )
        with pytest.raises(PermanentError):
            runner._handle_task(env)
    finally:
        bus.close()


def test_handle_task_works_with_dict_shaped_data_from_wire():
    """When the binder reconstructs an envelope from wire bytes, the
    data field is a plain dict (not a TaskMessage instance). The handler
    must cope with both shapes."""
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(), bus=bus)
        task = _make_task()
        env = Envelope(
            specversion="1.0",
            id=str(uuid4()),
            source="rmq",
            type="t",
            subject="ctf_in",
            data=task.model_dump(mode="json"),  # dict shape
        )
        runner._handle_task(env)
        assert len(binder.published_tasks) == 1
    finally:
        bus.close()


# ---------------------------------------------------------------------------
# End-to-end: dispatch → consume → result, all in-memory
# ---------------------------------------------------------------------------

def test_end_to_end_task_round_trip_through_inmemory_bus():
    """The integration-test pattern MB4.2+ plugin smoke tests will
    reuse: InMemoryBinder as the broker, real runner, dispatch a
    task, assert on the result envelope — no RMQ needed."""
    binder = InMemoryBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.reset()
    get_bus.override(bus)
    try:
        runner = _make_runner(_StubPlugin(), bus=bus)
        # Register the runner's consumer on the in_route
        handle = bus.tasks.consumer(runner._in_route, runner._handle_task)
        try:
            # Capture results
            results: List[Envelope] = []
            bus.events.subscribe(
                type("P", (), {"subject_glob": "ctf_out"})(),
                results.append,
            )  # NB: TaskResultRoute publishes via tasks.send, not events

            # Publish a task through the bus
            task = _make_task()
            bus.tasks.send(
                TaskRoute.named("ctf_in"),
                Envelope.wrap(source="test", type="t", subject="ctf_in", data=task),
            )

            # Wait for the runner to consume, run, and publish the result
            assert binder.wait_for_drain(timeout=2.0)
        finally:
            handle.close()

        # The result landed on the out subject
        out_subject = "ctf_out"
        result_publishes = [
            (s, e) for s, e in binder.published_tasks if s == out_subject
        ]
        assert len(result_publishes) == 1
        _, result_env = result_publishes[0]
        result_dto = result_env.data
        if not isinstance(result_dto, TaskResultMessage):
            result_dto = TaskResultMessage.model_validate(result_dto)
        assert result_dto.output_data == {"answer": 42}
    finally:
        get_bus.reset()
        bus.close()


def test_runner_uses_get_bus_when_no_explicit_bus_passed():
    """Plugin main.py calls install_rmq_bus() (or similar) and then
    builds a runner without passing bus=; _require_bus resolves via
    get_bus() lazily."""
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.reset()
    get_bus.override(bus)
    try:
        # No bus= arg — runner must pick up the installed bus
        runner = PluginBrokerRunner(
            plugin=_StubPlugin(),
            settings=MagicMock(),
            in_queue="ctf_in",
            out_queue="ctf_out",
            result_factory=_result_factory,
        )
        env = Envelope.wrap(
            source="test", type="t", subject="ctf_in", data=_make_task()
        )
        runner._handle_task(env)
        assert len(binder.published_tasks) == 1
    finally:
        get_bus.reset()
        bus.close()


# ---------------------------------------------------------------------------
# Cancelled-result path (G.1) — closes runner gap #3 from coverage audit
# ---------------------------------------------------------------------------

def test_handle_task_publishes_cancelled_result_on_jobcancelled():
    """JobCancelledError raised by the plugin's reporter (operator
    cancelled the job mid-flight) must NOT propagate up to the binder
    — that would route the message to the DLQ, which confuses
    operators ("why is my cancelled task in the DLQ?"). The runner
    catches the raise, builds a FAILED-status result with
    output_data.cancelled=True, and acks normally."""
    from magellon_sdk.progress import JobCancelledError

    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(raise_on_run=JobCancelledError("user clicked cancel")), bus=bus)
        env = Envelope.wrap(
            source="test", type="t", subject="ctf_in", data=_make_task(),
        )

        result = runner._handle_task(env)

        assert result is None  # binder acks
        assert len(binder.published_tasks) == 1
        _, result_env = binder.published_tasks[0]
        result_dto = result_env.data
        if not isinstance(result_dto, TaskResultMessage):
            result_dto = TaskResultMessage.model_validate(result_dto)
        # The cancelled result wears FAILED status (the wire enum has
        # no CANCELLED code today) but the cancelled flag distinguishes
        # it from a real failure.
        assert result_dto.output_data == {"cancelled": True, "reason": "user clicked cancel"}
        assert "cancelled" in (result_dto.message or "")
    finally:
        bus.close()


def test_cancelled_result_carries_task_and_job_ids():
    """The result processor projects against the task row by id; the
    UI shows the job's cancelled state via job_id. Both must travel."""
    from magellon_sdk.progress import JobCancelledError

    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(raise_on_run=JobCancelledError("x")), bus=bus)
        task = _make_task()
        env = Envelope.wrap(source="t", type="t", subject="ctf_in", data=task)

        runner._handle_task(env)

        result_dto = binder.published_tasks[0][1].data
        if not isinstance(result_dto, TaskResultMessage):
            result_dto = TaskResultMessage.model_validate(result_dto)
        assert result_dto.task_id == task.id
        assert result_dto.job_id == task.job_id
    finally:
        bus.close()


def test_cancelled_result_extracts_image_id_from_task_data():
    """``image_id`` lives inside ``task.data`` (per-category payload),
    not at the top level. The cancelled-result helper has to dig it
    out so the result projector can anchor the cancelled status to
    the right image row."""
    from magellon_sdk.progress import JobCancelledError
    from uuid import uuid4

    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(raise_on_run=JobCancelledError("x")), bus=bus)
        image_id = uuid4()
        task = TaskMessage(
            id=uuid4(), job_id=uuid4(), type=CTF_TASK,
            data={"image_path": "/x.mrc", "image_id": str(image_id)},
        )
        env = Envelope.wrap(source="t", type="t", subject="ctf_in", data=task)

        runner._handle_task(env)

        result_dto = binder.published_tasks[0][1].data
        if not isinstance(result_dto, TaskResultMessage):
            result_dto = TaskResultMessage.model_validate(result_dto)
        assert str(result_dto.image_id) == str(image_id)
    finally:
        bus.close()


def test_cancelled_result_handles_missing_image_id():
    """Some categories don't carry ``image_id`` in their payload at
    all; the cancelled-result builder must not crash when it's
    absent. The result still ships, just without an image anchor."""
    from magellon_sdk.progress import JobCancelledError

    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(raise_on_run=JobCancelledError("x")), bus=bus)
        # task.data without image_id key
        task = _make_task()  # data={"image_path": "/gpfs/x.mrc"}, no image_id
        env = Envelope.wrap(source="t", type="t", subject="ctf_in", data=task)

        runner._handle_task(env)

        # No crash; result still published.
        assert len(binder.published_tasks) == 1


    finally:
        bus.close()


# ---------------------------------------------------------------------------
# Shutdown / lifecycle (gap #3 part B) — stop() must close every resource
# ---------------------------------------------------------------------------

def test_stop_is_idempotent():
    """Operator scripts and finally-blocks both call stop(); calling
    twice must not raise. Otherwise the second call masks the first
    error."""
    runner = _make_runner(_StubPlugin())
    runner.stop()  # nothing started yet
    runner.stop()  # second call


def test_stop_closes_task_handle():
    """The bus consumer handle holds the consumer thread + cancel
    flag — leaking it on shutdown leaves the thread alive after the
    runner exits, which can race with subsequent tests or a process
    restart."""
    runner = _make_runner(_StubPlugin())
    handle = MagicMock()
    runner._task_handle = handle

    runner.stop()

    handle.close.assert_called_once()
    assert runner._task_handle is None  # cleared so a second stop() is safe


def test_stop_closes_heartbeat_loop():
    """The heartbeat thread keeps the plugin in the liveness
    registry. If we don't stop it on shutdown, the registry shows a
    dead replica as live — dispatcher would route work to a queue
    nobody's consuming."""
    runner = _make_runner(_StubPlugin())
    heartbeat = MagicMock()
    runner._heartbeat_loop = heartbeat

    runner.stop()

    heartbeat.stop.assert_called_once()


def test_stop_closes_discovery_publisher():
    """Discovery publisher owns its own broker connection (pre-MB5)
    — leaking it pins broker resources after process exit."""
    runner = _make_runner(_StubPlugin())
    pub = MagicMock()
    runner._discovery_publisher = pub

    runner.stop()

    pub.close.assert_called_once()


def test_stop_closes_config_subscriber():
    """The config subscriber owns its own subscription handle on the
    bus. Leaking it is observable as a dangling subscriber count on
    the broker UI."""
    runner = _make_runner(_StubPlugin())
    sub = MagicMock()
    runner._config_subscriber = sub

    runner.stop()

    sub.stop.assert_called_once()


def test_stop_closes_cancel_listener():
    """G.1 cancel listener also has a subscription that must be
    released; symmetric with config subscriber."""
    runner = _make_runner(_StubPlugin())
    listener = MagicMock()
    runner._cancel_listener = listener

    runner.stop()

    listener.stop.assert_called_once()
    assert runner._cancel_listener is None


def test_stop_does_not_raise_when_resource_close_fails():
    """A flaky resource (broker disconnected mid-stop) raising must
    not abort cleanup of the OTHER resources. Operator pressed Ctrl-C
    and we'd rather close as much as we can."""
    runner = _make_runner(_StubPlugin())
    handle = MagicMock()
    handle.close.side_effect = RuntimeError("broker gone")
    heartbeat = MagicMock()
    runner._task_handle = handle
    runner._heartbeat_loop = heartbeat

    # Should not raise.
    runner.stop()

    # Despite handle.close() blowing up, heartbeat still got stopped.
    heartbeat.stop.assert_called_once()


def test_start_cancel_listener_failure_is_logged_not_raised(caplog):
    """If the cancel listener fails to subscribe (network blip,
    permission issue), the plugin should still come up — task
    processing without cooperative cancel is degraded, not broken.
    The plugin author cares more about the plugin running than about
    cancel working."""
    from magellon_sdk.bus._facade import get_bus

    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    try:
        runner = _make_runner(_StubPlugin(), bus=bus)

        with caplog.at_level("ERROR"):
            # Patch the imported function inside the runner module so the
            # lazy import inside _start_cancel_listener picks up the patched
            # version rather than the real one.
            from magellon_sdk.bus.services import cancel_registry as _cr_mod
            original = _cr_mod.start_cancel_listener
            _cr_mod.start_cancel_listener = MagicMock(side_effect=RuntimeError("subscribe failed"))
            try:
                runner._start_cancel_listener(bus)
            finally:
                _cr_mod.start_cancel_listener = original

        # Listener slot stays None (degraded mode); the runner did not crash.
        assert runner._cancel_listener is None
        assert any("cancel listener failed" in r.message for r in caplog.records)
    finally:
        bus.close()


def test_runner_auto_installs_rmq_bus_when_no_factory_registered(monkeypatch):
    """Pre-MB4.2 compat: a plugin main.py that hasn't been migrated to
    call install_rmq_bus() still works — the runner falls back to
    building + installing an RmqBus from its settings at first use."""
    binder = MockBinder()
    bus = DefaultMessageBus(binder)
    bus.start()
    get_bus.reset()  # no factory, no override

    # Intercept install_rmq_bus in the module where _require_bus imports it
    from magellon_sdk.bus import bootstrap as _bootstrap

    def _fake_install(settings, **kwargs):
        get_bus.override(bus)
        return bus

    monkeypatch.setattr(_bootstrap, "install_rmq_bus", _fake_install)

    try:
        runner = PluginBrokerRunner(
            plugin=_StubPlugin(),
            settings=MagicMock(),
            in_queue="ctf_in",
            out_queue="ctf_out",
            result_factory=_result_factory,
        )
        # _handle_task triggers _require_bus → no factory → fallback
        env = Envelope.wrap(
            source="test", type="t", subject="ctf_in", data=_make_task()
        )
        runner._handle_task(env)
        assert len(binder.published_tasks) == 1
    finally:
        get_bus.reset()
        bus.close()
