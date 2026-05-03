"""Fast unit tests for the CTF plugin contract.

Mirrors the FFT / topaz contract test suites. Phase 1b
(2026-05-03) moved the active-task ContextVar + daemon loop into the
SDK; these tests pin that the migration didn't regress the plugin's
SDK seam — schemas, manifest, step-event shape, result-factory wire
contract — without needing a real broker or the ctffind4 binary.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

import pytest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# Contract: CTF category
# ---------------------------------------------------------------------------


def test_input_schema_matches_ctf_category_contract():
    from magellon_sdk.categories.contract import CTF
    from plugin.plugin import CtfPlugin

    assert CtfPlugin.input_schema() is CTF.input_model


def test_output_schema_is_ctf_plugin_output_wrapper():
    """CTF wraps the TaskResultMessage that ``do_ctf`` builds inline
    — see CtfPluginOutput. Pin this so a future refactor that changes
    the wrapping shape has to update the test together."""
    from plugin.plugin import CtfPlugin, CtfPluginOutput

    assert CtfPlugin.output_schema() is CtfPluginOutput


def test_get_info_provenance():
    from plugin.plugin import CtfPlugin

    info = CtfPlugin().get_info()
    assert info.name == "CTF Plugin"
    assert info.version == "1.0.2"


def test_manifest_advertises_cpu_intensive_and_rmq_default():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import CtfPlugin

    manifest = CtfPlugin().manifest()
    assert Capability.CPU_INTENSIVE in manifest.capabilities
    assert Capability.IDEMPOTENT in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# Phase 1b — back-compat shims
# ---------------------------------------------------------------------------


def test_ctf_broker_runner_shim_resolves_to_sdk_runner():
    from magellon_sdk.runner import PluginBrokerRunner
    from plugin.plugin import CtfBrokerRunner

    assert CtfBrokerRunner is PluginBrokerRunner


def test_get_active_task_shim_resolves_to_sdk_helper():
    from magellon_sdk.runner import current_task
    from plugin.plugin import get_active_task

    assert get_active_task is current_task


# ---------------------------------------------------------------------------
# execute() — outside-runner-context path
# ---------------------------------------------------------------------------


def test_execute_raises_when_no_active_task():
    """CTF doesn't try to fall back to a synthesized task — it requires
    the runner context. The error message points test authors at the
    SDK helper to set the var."""
    from magellon_sdk.models.tasks import CtfInput
    from plugin.plugin import CtfPlugin

    with pytest.raises(RuntimeError, match="set_active_task"):
        CtfPlugin().execute(CtfInput(inputFile="/tmp/x.mrc"))


# ---------------------------------------------------------------------------
# execute() — emits started → progress → completed via SDK helpers
# ---------------------------------------------------------------------------


def test_execute_emits_lifecycle_via_sdk_helpers(monkeypatch, tmp_path):
    """``execute`` should publish via the SDK ``emit_step`` helper,
    routing through the singleton daemon loop. Mock do_ctf and
    get_publisher; assert the emit ordering."""
    from magellon_sdk.models import TaskMessage, TaskResultMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod
    from service import step_events as step_events_mod

    captured = []

    class _RecPub:
        async def publish(self, subject, envelope):
            captured.append((envelope.type, envelope.data))

    async def _fake_get_publisher():
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="ctf")

    # CTF uses safe_emit_* helpers from service.step_events; those
    # call get_publisher from the same module. The plugin imports it
    # at module load.
    monkeypatch.setattr(step_events_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)

    # Mock do_ctf to return a synthetic TaskResultMessage immediately.
    async def _fake_do_ctf(task: TaskMessage) -> TaskResultMessage:
        return TaskResultMessage(
            task_id=task.id, job_id=task.job_id, code=200, message="ok"
        )

    monkeypatch.setattr(plugin_mod, "do_ctf", _fake_do_ctf)

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import CtfInput
        out = plugin_mod.CtfPlugin().execute(CtfInput(inputFile="/tmp/x.mrc"))
    finally:
        reset_active_task(token)

    assert isinstance(out, plugin_mod.CtfPluginOutput)
    assert out.result_dto.task_id == task_id

    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert "magellon.step.progress" in types
    assert types[-1] == "magellon.step.completed"
    for _, data in captured:
        assert data["job_id"] == str(job_id)
        assert data["task_id"] == str(task_id)


def test_execute_emits_failed_on_compute_error(monkeypatch, tmp_path):
    from magellon_sdk.models import TaskMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod
    from service import step_events as step_events_mod

    captured = []

    class _RecPub:
        async def publish(self, subject, envelope):
            captured.append((envelope.type, envelope.data))

    async def _fake_get_publisher():
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="ctf")

    async def _boom(task):
        raise RuntimeError("ctffind crashed")

    monkeypatch.setattr(step_events_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "do_ctf", _boom)

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import CtfInput
        with pytest.raises(RuntimeError, match="ctffind crashed"):
            plugin_mod.CtfPlugin().execute(CtfInput(inputFile="/tmp/x.mrc"))
    finally:
        reset_active_task(token)

    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert types[-1] == "magellon.step.failed"
    assert captured[-1][1]["error"] == "ctffind crashed"


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------


def test_build_ctf_result_unwraps_plugin_output_shell():
    """``do_ctf`` builds the TaskResultMessage; CtfPluginOutput is a
    pass-through. ``build_ctf_result`` must hand the inner DTO to the
    runner without re-wrapping."""
    from magellon_sdk.models import TaskMessage, TaskResultMessage
    from plugin.plugin import CtfPluginOutput, build_ctf_result

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    inner = TaskResultMessage(
        task_id=task.id, job_id=task.job_id, code=200, message="ok",
        output_data={"defocus_u": 12000.0, "defocus_v": 12100.0},
    )
    wrapper = CtfPluginOutput(result_dto=inner)
    out = build_ctf_result(task, wrapper)
    assert out is inner
    assert out.output_data["defocus_u"] == 12000.0
