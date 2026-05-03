"""Fast unit tests for the ptolemy plugin contract.

Mirrors the FFT / topaz / CTF / motioncor contract test suites.
Phase 1b (2026-05-03) moved the ContextVar + step-event helpers into
the SDK and made ``plugin.compute`` import lazy in execute(); these
tests verify the SDK seam without needing onnxruntime (the
``plugin.ptolemy.models`` chain drags it in at module load).

Two categories: SQUARE_DETECTION (low-mag) and HOLE_DETECTION
(med-mag). Both share PtolemyInput; differ only in the output.
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
# Contract: SQUARE_DETECT + HOLE_DETECT category models
# ---------------------------------------------------------------------------


def test_square_schemas_match_square_detect_contract():
    from magellon_sdk.categories.contract import SQUARE_DETECT
    from plugin.plugin import PtolemySquarePlugin

    assert PtolemySquarePlugin.input_schema() is SQUARE_DETECT.input_model
    assert PtolemySquarePlugin.output_schema() is SQUARE_DETECT.output_model


def test_hole_schemas_match_hole_detect_contract():
    from magellon_sdk.categories.contract import HOLE_DETECT
    from plugin.plugin import PtolemyHolePlugin

    assert PtolemyHolePlugin.input_schema() is HOLE_DETECT.input_model
    assert PtolemyHolePlugin.output_schema() is HOLE_DETECT.output_model


def test_square_get_info_provenance():
    from plugin.plugin import PtolemySquarePlugin

    info = PtolemySquarePlugin().get_info()
    assert info.name == "Ptolemy Square Detection"
    assert info.version == "1.0.0"


def test_hole_get_info_provenance():
    from plugin.plugin import PtolemyHolePlugin

    info = PtolemyHolePlugin().get_info()
    assert info.name == "Ptolemy Hole Detection"
    assert info.version == "1.0.0"


def test_square_manifest_advertises_progress_and_rmq_default():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import PtolemySquarePlugin

    manifest = PtolemySquarePlugin().manifest()
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# Phase 1b — back-compat shims
# ---------------------------------------------------------------------------


def test_ptolemy_broker_runner_shim_resolves_to_sdk_runner():
    from magellon_sdk.runner import PluginBrokerRunner
    from plugin.plugin import PtolemyBrokerRunner

    assert PtolemyBrokerRunner is PluginBrokerRunner


def test_get_active_task_shim_resolves_to_sdk_helper():
    from magellon_sdk.runner import current_task
    from plugin.plugin import get_active_task

    assert get_active_task is current_task


# ---------------------------------------------------------------------------
# execute() — emits started → progress → completed via SDK helpers
# ---------------------------------------------------------------------------


def _install_recording_publisher(monkeypatch, captured):
    """Wire a recording publisher into both the events module and the
    plugin module (the latter has it imported by name)."""
    class _RecPub:
        async def publish(self, subject, envelope):
            captured.append((envelope.type, envelope.data))

    async def _fake_get_publisher():
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="ptolemy")

    from plugin import events as events_mod
    from plugin import plugin as plugin_mod

    monkeypatch.setattr(events_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)


def _stub_compute(monkeypatch, *, square_dets=None, hole_dets=None):
    """Stub plugin.compute so the lazy import inside execute()
    doesn't drag in onnxruntime / skimage."""
    import sys as _sys
    import types as _types

    fake = _types.ModuleType("plugin.compute")
    fake.run_square_detection = lambda input_file: list(square_dets or [])
    fake.run_hole_detection = lambda input_file: list(hole_dets or [])
    monkeypatch.setitem(_sys.modules, "plugin.compute", fake)


def _make_detection(score=0.9):
    return {
        "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
        "center": [5, 5],
        "area": 100.0,
        "score": float(score),
    }


def test_square_execute_emits_lifecycle(monkeypatch, tmp_path):
    from magellon_sdk.models import TaskMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod

    captured = []
    _install_recording_publisher(monkeypatch, captured)
    _stub_compute(monkeypatch, square_dets=[_make_detection(0.9), _make_detection(0.7)])

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import PtolemyInput
        out = plugin_mod.PtolemySquarePlugin().execute(
            PtolemyInput(input_file=str(tmp_path / "lowmag.mrc"))
        )
    finally:
        reset_active_task(token)

    assert len(out.detections) == 2
    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert "magellon.step.progress" in types
    assert types[-1] == "magellon.step.completed"
    # Step name carries the suffix to distinguish square vs hole.
    for _, data in captured:
        assert data["step"].startswith("ptolemy.")
        assert ".square" in data["step"] or data["step"] == "ptolemy.square"
        assert data["job_id"] == str(job_id)
        assert data["task_id"] == str(task_id)


def test_hole_execute_emits_lifecycle(monkeypatch, tmp_path):
    from magellon_sdk.models import TaskMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod

    captured = []
    _install_recording_publisher(monkeypatch, captured)
    _stub_compute(monkeypatch, hole_dets=[_make_detection(0.85)])

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import PtolemyInput
        out = plugin_mod.PtolemyHolePlugin().execute(
            PtolemyInput(input_file=str(tmp_path / "medmag.mrc"))
        )
    finally:
        reset_active_task(token)

    assert len(out.detections) == 1
    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert types[-1] == "magellon.step.completed"
    # Step name reflects the hole pipeline, not the square one.
    for _, data in captured:
        assert ".hole" in data["step"] or data["step"] == "ptolemy.hole"


def test_square_execute_emits_failed_on_compute_error(monkeypatch, tmp_path):
    import sys as _sys
    import types as _types

    from magellon_sdk.models import TaskMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod

    captured = []
    _install_recording_publisher(monkeypatch, captured)

    fake = _types.ModuleType("plugin.compute")

    def _boom(input_file):
        raise RuntimeError("ptolemy crashed")

    fake.run_square_detection = _boom
    fake.run_hole_detection = _boom
    monkeypatch.setitem(_sys.modules, "plugin.compute", fake)

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import PtolemyInput
        with pytest.raises(RuntimeError, match="ptolemy crashed"):
            plugin_mod.PtolemySquarePlugin().execute(
                PtolemyInput(input_file=str(tmp_path / "lowmag.mrc"))
            )
    finally:
        reset_active_task(token)

    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert types[-1] == "magellon.step.failed"
    assert captured[-1][1]["error"] == "ptolemy crashed"


# ---------------------------------------------------------------------------
# Result factories
# ---------------------------------------------------------------------------


def test_build_square_result_serialises_detections_and_envelope_ids():
    from magellon_sdk.categories.outputs import Detection, SquareDetectionOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_square_result

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={"input_file": "/tmp/lowmag.mrc"})
    output = SquareDetectionOutput(
        detections=[
            Detection(**_make_detection(0.9)),
            Detection(**_make_detection(0.5)),
        ],
    )
    result = build_square_result(task, output)
    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.code == 200
    assert result.image_path == "/tmp/lowmag.mrc"
    assert "found 2 squares" in result.message
    assert len(result.output_data["detections"]) == 2
    # Rule 1: refs + summaries on the bus. Detections are scalar-shape
    # summaries; no inline image bytes.
    for d in result.output_data["detections"]:
        assert "vertices" in d
        assert "center" in d
        assert "score" in d


def test_build_hole_result_serialises_detections():
    from magellon_sdk.categories.outputs import Detection, HoleDetectionOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_hole_result

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={"input_file": "/tmp/medmag.mrc"})
    output = HoleDetectionOutput(detections=[Detection(**_make_detection(0.95))])
    result = build_hole_result(task, output)
    assert result.code == 200
    assert "found 1 holes" in result.message
    assert len(result.output_data["detections"]) == 1
