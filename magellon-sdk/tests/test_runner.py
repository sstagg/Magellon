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
from magellon_sdk.models import CTF_TASK, PluginInfo, TaskDto, TaskResultDto
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


def _result_factory(task: TaskDto, output: _StubOutput) -> TaskResultDto:
    return TaskResultDto(
        task_id=task.id,
        job_id=task.job_id,
        code=200,
        message="ok",
        type=task.type,
        output_data={"answer": output.answer},
    )


def _make_task() -> TaskDto:
    return TaskDto(
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
    """A clean run produces a TaskResultDto whose plugin_id /
    plugin_version come from the plugin's own get_info()."""
    runner = _make_runner(_StubPlugin())
    body = _make_task().model_dump_json().encode()

    out_bytes = runner._process(body)

    out = TaskResultDto.model_validate_json(out_bytes)
    assert out.plugin_id == "stub-plugin"
    assert out.plugin_version == "0.42.0"
    assert out.output_data == {"answer": 42}


def test_process_preserves_explicit_provenance_set_by_factory():
    """If the result_factory already filled provenance (engine
    wrapper case), the harness must not clobber it."""
    runner = _make_runner(_StubPlugin())
    runner.result_factory = lambda t, o: TaskResultDto(
        task_id=t.id,
        plugin_id="gctf-2.1",
        plugin_version="2.1.0",
    )
    body = _make_task().model_dump_json().encode()

    out_bytes = runner._process(body)

    out = TaskResultDto.model_validate_json(out_bytes)
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
    out = TaskResultDto.model_validate_json(out_bytes)
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
        # The published envelope's data is a TaskResultDto
        result_dto = result_envelope.data
        if not isinstance(result_dto, TaskResultDto):
            result_dto = TaskResultDto.model_validate(result_dto)
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
    data field is a plain dict (not a TaskDto instance). The handler
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
        if not isinstance(result_dto, TaskResultDto):
            result_dto = TaskResultDto.model_validate(result_dto)
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
