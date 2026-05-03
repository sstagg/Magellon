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
