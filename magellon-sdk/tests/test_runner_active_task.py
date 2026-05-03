"""Tests for :mod:`magellon_sdk.runner.active_task` — the helpers Phase 1
(2026-05-03) absorbed from per-plugin code (FFT, topaz, motioncor,
ctf, ptolemy each previously hand-rolled them)."""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from magellon_sdk.models import TaskMessage
from magellon_sdk.runner import (
    PluginBrokerRunner,
    current_task,
    emit_step,
    get_step_event_loop,
    make_step_reporter,
    reset_active_task,
    set_active_task,
)


# ---------------------------------------------------------------------------
# ContextVar primitives
# ---------------------------------------------------------------------------


def test_current_task_is_none_outside_runner_context():
    """Tests / REPL / direct ``execute()`` see ``None``; only the
    runner populates the var. Fail-soft: plugin code shouldn't crash
    when nothing's set."""
    assert current_task() is None


def test_set_and_reset_active_task_round_trip():
    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:
        assert current_task() is task
    finally:
        reset_active_task(token)
    assert current_task() is None


def test_nested_set_resets_to_outer():
    """Reset has to restore the *previous* value, not unconditionally
    clear — otherwise nested runner deliveries (a synthetic test
    scenario) would race the ContextVar."""
    outer = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    inner = TaskMessage(id=uuid4(), job_id=uuid4(), data={})

    outer_token = set_active_task(outer)
    try:
        assert current_task() is outer
        inner_token = set_active_task(inner)
        try:
            assert current_task() is inner
        finally:
            reset_active_task(inner_token)
        assert current_task() is outer
    finally:
        reset_active_task(outer_token)
    assert current_task() is None


# ---------------------------------------------------------------------------
# Daemon-loop singleton
# ---------------------------------------------------------------------------


def test_get_step_event_loop_is_singleton():
    """One process, one loop — repeat calls return the same instance.
    A new loop per call would defeat the purpose (pika heartbeat
    stalls the original code path tripped over)."""
    a = get_step_event_loop()
    b = get_step_event_loop()
    assert a is b
    assert a.is_running()


def test_emit_step_runs_coroutine_on_daemon_loop():
    captured = []

    async def _coro():
        captured.append("ran")

    emit_step(_coro())
    assert captured == ["ran"]


def test_emit_step_swallows_exceptions():
    """A failing step-event coroutine must never propagate — that's
    the explicit non-fatal contract for observability."""

    async def _crashy():
        raise RuntimeError("publisher exploded")

    # Must not raise.
    emit_step(_crashy())


# ---------------------------------------------------------------------------
# make_step_reporter
# ---------------------------------------------------------------------------


def test_make_step_reporter_returns_none_without_active_task():
    """No active task means we're outside a runner-driven delivery.
    The reporter would have nothing to bind ``job_id`` to — return
    None and let the plugin no-op."""
    async def _factory():
        # Should never even be called; return value irrelevant.
        return object()

    assert make_step_reporter("fft", _factory) is None


def test_make_step_reporter_returns_none_when_factory_returns_none():
    """Step events disabled (factory returns None) → no reporter."""
    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:

        async def _factory():
            return None

        assert make_step_reporter("fft", _factory) is None
    finally:
        reset_active_task(token)


def test_make_step_reporter_returns_none_when_factory_raises():
    """Factory that raises (e.g. NATS unreachable) must not abort the
    plugin's execute — return None and continue."""
    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:

        async def _factory():
            raise RuntimeError("publisher init failed")

        assert make_step_reporter("fft", _factory) is None
    finally:
        reset_active_task(token)


def test_make_step_reporter_binds_active_task_ids():
    """Happy path: when an active task is set and the factory
    succeeds, the returned BoundStepReporter is keyed on the task's
    ``job_id`` / ``task_id``."""
    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})

    class _FakePublisher:
        async def publish(self, subject, envelope):
            return None

    async def _factory():
        from magellon_sdk.events import StepEventPublisher

        return StepEventPublisher(_FakePublisher(), plugin_name="fft")

    token = set_active_task(task)
    try:
        reporter = make_step_reporter("fft", _factory)
        assert reporter is not None
        # BoundStepReporter doesn't expose the bound IDs publicly;
        # exercise an emit and verify we don't crash.
        emit_step(reporter.started())
    finally:
        reset_active_task(token)


# ---------------------------------------------------------------------------
# PluginBrokerRunner integration — _process / _handle_task set the var
# ---------------------------------------------------------------------------


def test_plugin_broker_runner_sets_active_task_during_process(monkeypatch):
    """The runner's legacy ``_process`` (used by plugin-level tests)
    must set the ContextVar so plugins recover the task in
    ``execute()``. Phase 1 moved this from ``FftBrokerRunner._process``
    to the SDK base."""
    from magellon_sdk.base import PluginBase
    from magellon_sdk.models.manifest import (
        Capability,
        IsolationLevel,
        ResourceHints,
        Transport,
    )
    from magellon_sdk.models import OutputFile, PluginInfo, TaskResultMessage
    from magellon_sdk.models.tasks import FftInput
    from magellon_sdk.categories.outputs import FftOutput
    from magellon_sdk.progress import NullReporter

    seen = {}

    class _CapPlugin(PluginBase[FftInput, FftOutput]):
        capabilities = [Capability.CPU_INTENSIVE]
        supported_transports = [Transport.RMQ]
        default_transport = Transport.RMQ
        isolation = IsolationLevel.CONTAINER
        resource_hints = ResourceHints(memory_mb=10, cpu_cores=1, typical_duration_seconds=1)

        def get_info(self):
            return PluginInfo(name="cap", version="0.0.1", description="test")

        @classmethod
        def input_schema(cls):
            return FftInput

        @classmethod
        def output_schema(cls):
            return FftOutput

        def execute(self, input_data, *, reporter=NullReporter()):
            seen["task"] = current_task()
            return FftOutput(output_path="/tmp/out.png")

    def _factory(task, output):
        return TaskResultMessage(
            job_id=task.job_id,
            task_id=task.id,
            type=task.type,
            code=200,
            message="ok",
            output_data={"output_path": output.output_path},
            output_files=[OutputFile(name="out.png", path=output.output_path, required=True)],
        )

    class _FakeSettings:
        HOST_NAME = "localhost"
        PORT = 5672
        USER_NAME = "guest"
        PASSWORD = "guest"
        VIRTUAL_HOST = "/"

    runner = PluginBrokerRunner(
        plugin=_CapPlugin(),
        settings=_FakeSettings(),
        in_queue="cap_in",
        out_queue="cap_out",
        result_factory=_factory,
        contract=None,
        enable_discovery=False,
        enable_config=False,
    )

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={"image_path": "/tmp/x.mrc"})
    runner._process(task.model_dump_json().encode("utf-8"))

    assert seen["task"] is not None
    assert seen["task"].id == task_id
    assert seen["task"].job_id == job_id
    # ContextVar reset to None after _process returned.
    assert current_task() is None


# ---------------------------------------------------------------------------
# Phase 3b: subject_kind / subject_id round-trip from task to result
# ---------------------------------------------------------------------------


def _build_runner_for_subject_tests():
    """Compact harness for the subject-stamping tests below."""
    from magellon_sdk.base import PluginBase
    from magellon_sdk.models.manifest import (
        Capability,
        IsolationLevel,
        ResourceHints,
        Transport,
    )
    from magellon_sdk.models import OutputFile, PluginInfo, TaskResultMessage
    from magellon_sdk.models.tasks import FftInput
    from magellon_sdk.categories.outputs import FftOutput
    from magellon_sdk.progress import NullReporter

    class _SubjectPlugin(PluginBase[FftInput, FftOutput]):
        capabilities = [Capability.CPU_INTENSIVE]
        supported_transports = [Transport.RMQ]
        default_transport = Transport.RMQ
        isolation = IsolationLevel.CONTAINER
        resource_hints = ResourceHints(
            memory_mb=10, cpu_cores=1, typical_duration_seconds=1
        )

        def get_info(self):
            return PluginInfo(name="subj", version="0.0.1", description="t")

        @classmethod
        def input_schema(cls):
            return FftInput

        @classmethod
        def output_schema(cls):
            return FftOutput

        def execute(self, input_data, *, reporter=NullReporter()):
            return FftOutput(output_path="/tmp/out.png")

    def _factory(task, output):
        return TaskResultMessage(
            job_id=task.job_id,
            task_id=task.id,
            type=task.type,
            code=200,
            message="ok",
            output_data={"output_path": output.output_path},
            output_files=[OutputFile(name="out.png", path=output.output_path, required=True)],
        )

    class _FakeSettings:
        HOST_NAME = "localhost"
        PORT = 5672
        USER_NAME = "guest"
        PASSWORD = "guest"
        VIRTUAL_HOST = "/"

    return PluginBrokerRunner(
        plugin=_SubjectPlugin(),
        settings=_FakeSettings(),
        in_queue="subj_in",
        out_queue="subj_out",
        result_factory=_factory,
        contract=None,
        enable_discovery=False,
        enable_config=False,
    )


def test_task_result_message_carries_subject_axis_fields():
    """TaskResultMessage gained subject_kind / subject_id in Phase 3b
    so the round-trip preserves the dispatch-time subject across the
    result publish."""
    from magellon_sdk.models import TaskResultMessage

    fields = TaskResultMessage.model_fields
    assert "subject_kind" in fields
    assert "subject_id" in fields
    # Both nullable so pre-Phase-3 plugins keep working unchanged.
    assert fields["subject_kind"].default is None
    assert fields["subject_id"].default is None


def test_runner_stamps_subject_from_task_when_result_omits_it():
    """Plugins that don't thread subject through their result_factory
    (most of them) should still see the round-trip — the runner's
    _stamp_subject fills it from the incoming task."""
    runner = _build_runner_for_subject_tests()

    job_id = uuid4()
    task_id = uuid4()
    stack_id = uuid4()
    task = TaskMessage(
        id=task_id,
        job_id=job_id,
        data={"image_path": "/tmp/x.mrc"},
        subject_kind="particle_stack",
        subject_id=stack_id,
    )

    raw = runner._process(task.model_dump_json().encode("utf-8"))
    import json
    payload = json.loads(raw.decode("utf-8"))

    assert payload["subject_kind"] == "particle_stack"
    assert payload["subject_id"] == str(stack_id)


def test_runner_preserves_plugin_set_subject_when_provided():
    """If a plugin explicitly stamps subject_kind/subject_id on the
    result (e.g. an extractor that emits a particle_stack artifact and
    sets subject to the new artifact), the runner must NOT overwrite
    it. _stamp_subject only fills None."""
    from magellon_sdk.base import PluginBase
    from magellon_sdk.models.manifest import (
        Capability,
        IsolationLevel,
        ResourceHints,
        Transport,
    )
    from magellon_sdk.models import OutputFile, PluginInfo, TaskResultMessage
    from magellon_sdk.models.tasks import FftInput
    from magellon_sdk.categories.outputs import FftOutput
    from magellon_sdk.progress import NullReporter

    class _AssertivePlugin(PluginBase[FftInput, FftOutput]):
        capabilities = [Capability.CPU_INTENSIVE]
        supported_transports = [Transport.RMQ]
        default_transport = Transport.RMQ
        isolation = IsolationLevel.CONTAINER
        resource_hints = ResourceHints(
            memory_mb=10, cpu_cores=1, typical_duration_seconds=1
        )

        def get_info(self):
            return PluginInfo(name="assert", version="0.0.1", description="t")

        @classmethod
        def input_schema(cls):
            return FftInput

        @classmethod
        def output_schema(cls):
            return FftOutput

        def execute(self, input_data, *, reporter=NullReporter()):
            return FftOutput(output_path="/tmp/out.png")

    plugin_subject_id = uuid4()

    def _factory(task, output):
        return TaskResultMessage(
            job_id=task.job_id,
            task_id=task.id,
            type=task.type,
            code=200,
            message="ok",
            # Plugin asserts a different subject — e.g. extractor
            # produces a new artifact and points the result at it.
            subject_kind="particle_stack",
            subject_id=plugin_subject_id,
            output_data={"output_path": output.output_path},
            output_files=[OutputFile(name="out.png", path=output.output_path, required=True)],
        )

    class _FakeSettings:
        HOST_NAME = "localhost"
        PORT = 5672
        USER_NAME = "guest"
        PASSWORD = "guest"
        VIRTUAL_HOST = "/"

    runner = PluginBrokerRunner(
        plugin=_AssertivePlugin(),
        settings=_FakeSettings(),
        in_queue="a_in",
        out_queue="a_out",
        result_factory=_factory,
        contract=None,
        enable_discovery=False,
        enable_config=False,
    )

    # Incoming task has DIFFERENT subject — runner should NOT overwrite
    # the plugin's value.
    incoming_subject_id = uuid4()
    task = TaskMessage(
        id=uuid4(),
        job_id=uuid4(),
        data={"image_path": "/tmp/x.mrc"},
        subject_kind="image",
        subject_id=incoming_subject_id,
    )
    raw = runner._process(task.model_dump_json().encode("utf-8"))
    import json
    payload = json.loads(raw.decode("utf-8"))

    assert payload["subject_kind"] == "particle_stack"
    assert payload["subject_id"] == str(plugin_subject_id)


def test_runner_does_not_set_subject_when_task_has_none():
    """Pre-Phase-3 callers leave both fields None on the task. The
    result must also stay None — fall-through behavior."""
    runner = _build_runner_for_subject_tests()

    task = TaskMessage(
        id=uuid4(),
        job_id=uuid4(),
        data={"image_path": "/tmp/x.mrc"},
        # subject_kind, subject_id default None
    )
    raw = runner._process(task.model_dump_json().encode("utf-8"))
    import json
    payload = json.loads(raw.decode("utf-8"))

    assert payload["subject_kind"] is None
    assert payload["subject_id"] is None
