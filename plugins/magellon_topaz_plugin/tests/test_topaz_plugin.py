"""Fast unit tests for the topaz plugin contract.

The pre-existing ``test_smoke.py`` runs the full ONNX pipeline and
takes 30-60s on a real micrograph; these tests run in milliseconds and
verify the SDK plumbing without loading the bundled models. Mirrors
the FFT plugin's contract test suite.

Phase 1b (2026-05-03): topaz no longer carries its own ContextVar +
daemon-loop + step-reporter helpers — they live in
:mod:`magellon_sdk.runner.active_task`. These tests pin that the
plugin still emits started/progress/completed events with the SDK
helpers and that the wire-shape contract matches the category models.
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
# Contract: TOPAZ_PICK + DENOISE category models
# ---------------------------------------------------------------------------


def test_pick_schemas_match_topaz_pick_contract():
    from magellon_sdk.categories.contract import TOPAZ_PICK
    from plugin.plugin import TopazPickPlugin

    assert TopazPickPlugin.input_schema() is TOPAZ_PICK.input_model
    assert TopazPickPlugin.output_schema() is TOPAZ_PICK.output_model


def test_denoise_schemas_match_denoise_contract():
    from magellon_sdk.categories.contract import DENOISE
    from plugin.plugin import TopazDenoisePlugin

    assert TopazDenoisePlugin.input_schema() is DENOISE.input_model
    assert TopazDenoisePlugin.output_schema() is DENOISE.output_model


def test_pick_get_info_provenance():
    from plugin.plugin import TopazPickPlugin

    info = TopazPickPlugin().get_info()
    assert info.name == "Topaz Particle Picking"
    assert info.version == "1.0.0"


def test_denoise_get_info_provenance():
    from plugin.plugin import TopazDenoisePlugin

    info = TopazDenoisePlugin().get_info()
    assert info.name == "Topaz-Denoise"
    assert info.version == "1.0.0"


def test_pick_manifest_advertises_progress_and_rmq_default():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import TopazPickPlugin

    manifest = TopazPickPlugin().manifest()
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# Phase 1b — back-compat shims preserve old import names
# ---------------------------------------------------------------------------


def test_topaz_broker_runner_shim_resolves_to_sdk_runner():
    """Phase 1b promoted the runner subclass into the SDK base. Old
    callers (main.py before migration, downstream tests) imported
    ``TopazBrokerRunner`` from ``plugin.plugin`` — keep the alias for
    one release."""
    from magellon_sdk.runner import PluginBrokerRunner
    from plugin.plugin import TopazBrokerRunner

    assert TopazBrokerRunner is PluginBrokerRunner


def test_get_active_task_shim_resolves_to_sdk_helper():
    from magellon_sdk.runner import current_task
    from plugin.plugin import get_active_task

    assert get_active_task is current_task


# ---------------------------------------------------------------------------
# Step events — emitted via the SDK helpers, not per-plugin glue
# ---------------------------------------------------------------------------


def test_pick_execute_emits_started_progress_completed(monkeypatch, tmp_path):
    """``execute()`` should emit started → at least one progress →
    completed via :func:`magellon_sdk.runner.emit_step`. Mock the
    compute path + the publisher; assert event types and that
    job_id/task_id from the active task ride through unchanged."""
    from magellon_sdk.models import TaskMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod

    captured = []

    class _RecPub:
        async def publish(self, subject, envelope):
            captured.append((envelope.type, envelope.data))

    async def _fake_get_publisher():
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="topaz")

    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(
        plugin_mod, "run_pick",
        lambda input_file, **kwargs: [
            {"center": [10, 10], "radius": 14, "score": 5.5},
            {"center": [20, 20], "radius": 14, "score": 4.2},
        ],
    )

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import TopazPickInput
        out = plugin_mod.TopazPickPlugin().execute(
            TopazPickInput(input_file=str(tmp_path / "img.mrc"))
        )
    finally:
        reset_active_task(token)

    assert out.num_particles == 2
    types = [c[0] for c in captured]
    # Started, ≥1 progress, completed. Ordering matches FFT's pattern.
    assert types[0] == "magellon.step.started"
    assert "magellon.step.progress" in types
    assert types[-1] == "magellon.step.completed"
    # Each event carries the active-task identifiers — that's the
    # whole reason the ContextVar exists.
    for _, data in captured:
        assert data["job_id"] == str(job_id)
        assert data["task_id"] == str(task_id)
        assert data["step"].startswith("topaz.")


def test_pick_execute_emits_failed_on_compute_error(monkeypatch, tmp_path):
    from magellon_sdk.models import TaskMessage
    from magellon_sdk.runner import set_active_task, reset_active_task
    from plugin import plugin as plugin_mod

    captured = []

    class _RecPub:
        async def publish(self, subject, envelope):
            captured.append((envelope.type, envelope.data))

    async def _fake_get_publisher():
        from magellon_sdk.events import StepEventPublisher
        return StepEventPublisher(_RecPub(), plugin_name="topaz")

    def _boom(input_file, **kwargs):
        raise RuntimeError("topaz crashed")

    monkeypatch.setattr(plugin_mod, "get_publisher", _fake_get_publisher)
    monkeypatch.setattr(plugin_mod, "run_pick", _boom)

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={})
    token = set_active_task(task)
    try:
        from magellon_sdk.models.tasks import TopazPickInput
        with pytest.raises(RuntimeError, match="topaz crashed"):
            plugin_mod.TopazPickPlugin().execute(
                TopazPickInput(input_file=str(tmp_path / "img.mrc"))
            )
    finally:
        reset_active_task(token)

    types = [c[0] for c in captured]
    assert types[0] == "magellon.step.started"
    assert types[-1] == "magellon.step.failed"
    assert captured[-1][1]["error"] == "topaz crashed"


# ---------------------------------------------------------------------------
# Result factories
# ---------------------------------------------------------------------------


def test_build_pick_result_carries_envelope_ids_and_path_only():
    """Rule 1 (project_artifact_bus_invariants.md, ratified
    2026-05-03): bus carries refs and summaries only. The pre-fix
    topaz path inlined picks up to a 5000-cap then flipped to
    path-only — the consultant flagged that size cliff as the
    canonical rule-1 violation. Pinned: build_pick_result must NOT
    include the picks list in output_data."""
    from magellon_sdk.categories.outputs import ParticlePickingOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_pick_result

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={"input_file": "/tmp/in.mrc"})
    output = ParticlePickingOutput(
        num_particles=2,
        particles_json_path="/tmp/picks.json",
        picks=None,  # plugin no longer populates this
    )

    result = build_pick_result(task, output)
    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.code == 200
    assert result.image_path == "/tmp/in.mrc"
    assert result.output_data["num_particles"] == 2
    assert result.output_data["particles_json_path"] == "/tmp/picks.json"
    # Rule 1 enforcement: picks NOT inlined into the bus payload.
    assert "picks" not in result.output_data
    assert {f.path for f in result.output_files} == {"/tmp/picks.json"}


def test_build_denoise_result_includes_intensity_summary():
    from magellon_sdk.categories.outputs import MicrographDenoisingOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_denoise_result

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={"input_file": "/tmp/in.mrc"})
    output = MicrographDenoisingOutput(
        output_path="/tmp/out_denoised.mrc",
        source_image_path="/tmp/in.mrc",
        model="unet",
        image_shape=[512, 512],
        pixel_min=-1.5, pixel_max=1.5,
        pixel_mean=0.0, pixel_std=0.5,
    )
    result = build_denoise_result(task, output)
    assert result.code == 200
    assert result.output_data["output_path"] == "/tmp/out_denoised.mrc"
    assert result.output_data["pixel_mean"] == 0.0
    assert result.output_files[0].path == "/tmp/out_denoised.mrc"
