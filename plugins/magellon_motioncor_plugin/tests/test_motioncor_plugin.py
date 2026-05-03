"""Fast unit tests for the MotionCor plugin contract.

Mirrors the FFT / topaz / CTF contract test suites. Phase 1b
(2026-05-03) moved the active-task ContextVar + daemon loop into the
SDK and made the ``service.motioncor_service`` import lazy in
``execute()``; these tests pin that the migration didn't regress the
SDK seam without needing cv2 / mrcfile / matplotlib (which the
service / utils chain drags in).
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# Contract: MOTIONCOR category
# ---------------------------------------------------------------------------


def test_input_schema_matches_motioncor_category_contract():
    from magellon_sdk.categories.contract import MOTIONCOR_CATEGORY
    from plugin.plugin import MotioncorPlugin

    assert MotioncorPlugin.input_schema() is MOTIONCOR_CATEGORY.input_model


def test_output_schema_is_motioncor_plugin_output_wrapper():
    """Same wrapper pattern as CTF — do_motioncor builds the
    TaskResultMessage inline; ``build_motioncor_result`` unwraps."""
    from plugin.plugin import MotioncorPlugin, MotioncorPluginOutput

    assert MotioncorPlugin.output_schema() is MotioncorPluginOutput


def test_get_info_provenance():
    from plugin.plugin import MotioncorPlugin

    info = MotioncorPlugin().get_info()
    assert info.name == "MotionCor Plugin"
    assert info.version == "1.0.0"


def test_manifest_advertises_gpu_required():
    """MotionCor3 needs a GPU. Pin so it doesn't accidentally schedule
    onto a CPU-only host."""
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import MotioncorPlugin

    manifest = MotioncorPlugin().manifest()
    assert Capability.GPU_REQUIRED in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ
    # Memory hint must be high enough to schedule onto g4dn.2xlarge —
    # see project_motioncor_gpu_sizing.md (g4dn.xlarge silently
    # SIGKILLs from OOM).
    assert manifest.resources.memory_mb >= 8000
    assert manifest.resources.gpu_count == 1


# ---------------------------------------------------------------------------
# Phase 1b — back-compat shims
# ---------------------------------------------------------------------------


def test_motioncor_broker_runner_shim_resolves_to_sdk_runner():
    from magellon_sdk.runner import PluginBrokerRunner
    from plugin.plugin import MotioncorBrokerRunner

    assert MotioncorBrokerRunner is PluginBrokerRunner


def test_get_active_task_shim_resolves_to_sdk_helper():
    from magellon_sdk.runner import current_task
    from plugin.plugin import get_active_task

    assert get_active_task is current_task


# ---------------------------------------------------------------------------
# execute() — outside-runner path + emits via SDK helpers
# ---------------------------------------------------------------------------


def test_execute_raises_when_no_active_task():
    from magellon_sdk.models.tasks import MotionCorInput
    from plugin.plugin import MotioncorPlugin

    inp = MotionCorInput(inputFile="/tmp/m.mrc", Gain="/tmp/gain.mrc")
    with pytest.raises(RuntimeError, match="set_active_task"):
        MotioncorPlugin().execute(inp)


def test_execute_emits_lifecycle_via_sdk_helpers(monkeypatch, tmp_path):
    """Mirror of the CTF lifecycle test — Phase 1b made the
    do_motioncor import lazy so we can stub it without dragging cv2
    in. The lazy import lives in service.motioncor_service so we
    inject the stub via sys.modules to win the import race."""
    import sys as _sys
    import types as _types

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
        return StepEventPublisher(_RecPub(), plugin_name="motioncor")

    monkeypatch.setattr(step_events_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)

    # Stub service.motioncor_service so the lazy import inside
    # execute() doesn't drag in cv2 / utils.
    fake_svc = _types.ModuleType("service.motioncor_service")

    async def _fake_do_motioncor(task: TaskMessage) -> TaskResultMessage:
        return TaskResultMessage(
            task_id=task.id, job_id=task.job_id, code=200, message="ok"
        )

    fake_svc.do_motioncor = _fake_do_motioncor
    monkeypatch.setitem(_sys.modules, "service.motioncor_service", fake_svc)

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import MotionCorInput
        inp = MotionCorInput(inputFile="/tmp/m.mrc", Gain="/tmp/gain.mrc")
        out = plugin_mod.MotioncorPlugin().execute(inp)
    finally:
        reset_active_task(token)

    assert isinstance(out, plugin_mod.MotioncorPluginOutput)
    assert out.result_dto.task_id == task_id

    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert "magellon.step.progress" in types
    assert types[-1] == "magellon.step.completed"
    for _, data in captured:
        assert data["job_id"] == str(job_id)
        assert data["task_id"] == str(task_id)


def test_execute_emits_failed_on_compute_error(monkeypatch, tmp_path):
    import sys as _sys
    import types as _types

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
        return StepEventPublisher(_RecPub(), plugin_name="motioncor")

    monkeypatch.setattr(step_events_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)

    fake_svc = _types.ModuleType("service.motioncor_service")

    async def _boom(task):
        raise RuntimeError("motioncor3 crashed")

    fake_svc.do_motioncor = _boom
    monkeypatch.setitem(_sys.modules, "service.motioncor_service", fake_svc)

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import MotionCorInput
        inp = MotionCorInput(inputFile="/tmp/m.mrc", Gain="/tmp/gain.mrc")
        with pytest.raises(RuntimeError, match="motioncor3 crashed"):
            plugin_mod.MotioncorPlugin().execute(inp)
    finally:
        reset_active_task(token)

    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert types[-1] == "magellon.step.failed"
    assert captured[-1][1]["error"] == "motioncor3 crashed"


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------


def test_build_motioncor_result_unwraps_plugin_output_shell():
    from magellon_sdk.models import TaskMessage, TaskResultMessage
    from plugin.plugin import MotioncorPluginOutput, build_motioncor_result

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    inner = TaskResultMessage(
        task_id=task.id, job_id=task.job_id, code=200, message="ok",
        output_data={"aligned_mrc_path": "/work/aligned.mrc"},
    )
    wrapper = MotioncorPluginOutput(result_dto=inner)
    out = build_motioncor_result(task, wrapper)
    assert out is inner
    assert out.output_data["aligned_mrc_path"] == "/work/aligned.mrc"
