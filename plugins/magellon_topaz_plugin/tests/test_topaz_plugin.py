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
# Announced UI schema — engine_opts knobs declared with ui_* metadata
# ---------------------------------------------------------------------------


def test_announced_input_schema_carries_ui_rich_topaz_knobs():
    """``announced_input_schema()`` exposes the flat model/threshold/
    radius/scale form (which the React SchemaForm edits and wraps back
    into ``engine_opts`` on dispatch) — ``input_schema()`` itself stays
    the bare ``TopazPickInput`` used for validation."""
    from plugin.plugin import TopazPickPlugin

    schema = TopazPickPlugin.announced_input_schema()
    props = schema["properties"]
    assert set(props) == {"model", "threshold", "radius", "scale"}

    assert props["model"]["enum"] == ["resnet16", "resnet8"]
    assert props["model"]["ui_widget"] == "select"

    assert props["threshold"]["ui_widget"] == "slider"
    assert props["threshold"]["minimum"] == -8.0
    assert props["threshold"]["maximum"] == 8.0
    assert [m["label"] for m in props["threshold"]["ui_marks"]] == [
        "Sensitive", "Default", "Strict",
    ]

    assert props["radius"]["minimum"] == 4
    assert props["radius"]["maximum"] == 64

    assert props["scale"]["enum"] == [4, 8, 16]

    # threshold + radius retune cheaply (NMS only); model + scale would
    # need a full CNN recompute, so they are NOT tunable.
    assert props["threshold"]["ui_tunable"] is True
    assert props["radius"]["ui_tunable"] is True
    assert props["model"]["ui_tunable"] is False
    assert props["scale"]["ui_tunable"] is False
    # All four sit in the single "Topaz" accordion group.
    assert all(props[k]["ui_group"] == "Topaz" for k in props)


def test_pick_manifest_input_schema_is_the_ui_rich_form():
    """The announce path (start_discovery) and manifest() both read
    ``announced_input_schema()`` — pin that the manifest carries the
    UI-rich shape, not the bare TopazPickInput schema."""
    from plugin.plugin import TopazPickPlugin

    manifest = TopazPickPlugin().manifest()
    assert manifest.input_schema is not None
    assert set(manifest.input_schema["properties"]) == {
        "model", "threshold", "radius", "scale",
    }


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
        lambda input_file, **kwargs: (
            [
                {"center": [10, 10], "radius": 14, "score": 5.5},
                {"center": [20, 20], "radius": 14, "score": 4.2},
            ],
            [4096, 4096],
        ),
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
    # run_pick reports the source micrograph shape; execute() threads it
    # onto the output so consumers can size a canvas without re-reading.
    assert out.image_shape == [4096, 4096]
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
    task = TaskMessage(
        id=task_id, job_id=job_id,
        data={"input_file": "/tmp/in.mrc", "engine_opts": {"threshold": -2.5}},
    )
    output = ParticlePickingOutput(
        num_particles=2,
        particles_json_path="/tmp/picks.json",
        image_shape=[4096, 4096],
        picks=None,  # plugin no longer populates this
    )

    result = build_pick_result(task, output)
    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.code == 200
    assert result.image_path == "/tmp/in.mrc"
    assert result.output_data["num_particles"] == 2
    assert result.output_data["particles_json_path"] == "/tmp/picks.json"
    # Score threshold echoed from engine_opts so the result processor
    # classifies picks against the topaz log-likelihood cutoff.
    assert result.output_data["threshold"] == -2.5
    # Image shape echoed so the canvas sizes exactly, not by estimate.
    assert result.output_data["image_shape"] == [4096, 4096]
    # Rule 1 enforcement: picks NOT inlined into the bus payload.
    assert "picks" not in result.output_data
    assert {f.path for f in result.output_files} == {"/tmp/picks.json"}


def test_build_pick_result_threshold_defaults_when_engine_opts_absent():
    """A task with no engine_opts (or no threshold) falls back to the
    topaz tutorial default of -3.0 — never the 0.35 correlation default."""
    from magellon_sdk.categories.outputs import ParticlePickingOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_pick_result

    task = TaskMessage(id=uuid4(), job_id=uuid4(), data={"input_file": "/tmp/in.mrc"})
    output = ParticlePickingOutput(num_particles=0, particles_json_path="/tmp/p.json")

    result = build_pick_result(task, output)
    assert result.output_data["threshold"] == -3.0


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


# ---------------------------------------------------------------------------
# PREVIEW capability — preview / retune / discard. compute_score_map is
# mocked so these run in milliseconds without the bundled ONNX models;
# picks_from_score_map (real NMS) runs against a tiny synthetic map.
# ---------------------------------------------------------------------------


def _synthetic_score_map():
    """64x64 detector grid: five bright peaks well above the -3.0
    default cutoff, background far below it."""
    import numpy as np
    m = np.full((64, 64), -8.0, dtype=np.float32)
    for (r, c) in [(10, 10), (10, 40), (40, 10), (40, 40), (25, 25)]:
        m[r, c] = 5.0
    return m


def test_run_preview_caches_score_map_and_returns_result(monkeypatch):
    from magellon_sdk.models.tasks import TopazPickInput
    from plugin import preview as preview_mod

    monkeypatch.setattr(
        preview_mod, "compute_score_map",
        lambda input_file, **kw: (_synthetic_score_map(), [512, 512]),
    )
    inp = TopazPickInput(
        input_file="/tmp/x.mrc",
        engine_opts={"threshold": -3.0, "radius": 4, "scale": 8},
    )
    result = preview_mod.run_preview(inp)

    assert result.preview_id
    assert result.num_particles == len(result.particles) == 5
    assert result.image_shape == [512, 512]
    assert result.score_map_png_base64       # PNG thumbnail rendered
    assert result.score_range == [-8.0, 5.0]
    assert result.image_binning == 8
    preview_mod.discard_preview(result.preview_id)


def test_run_retune_rethresholds_cached_map_without_recompute(monkeypatch):
    from magellon_sdk.capabilities import PickingRetuneRequest
    from magellon_sdk.models.tasks import TopazPickInput
    from plugin import preview as preview_mod

    calls = {"n": 0}

    def _counted(input_file, **kw):
        calls["n"] += 1
        return _synthetic_score_map(), [512, 512]

    monkeypatch.setattr(preview_mod, "compute_score_map", _counted)
    pv = preview_mod.run_preview(
        TopazPickInput(input_file="/tmp/x.mrc",
                       engine_opts={"threshold": -3.0, "radius": 4, "scale": 8})
    )
    assert calls["n"] == 1

    # Threshold above every peak → zero picks, and no second CNN call.
    rt = preview_mod.run_retune(
        pv.preview_id, PickingRetuneRequest(threshold=6.0, radius=4),
    )
    assert rt is not None and rt.num_particles == 0
    assert calls["n"] == 1  # retune did not recompute the score map

    # Unknown / expired preview id → None (router maps it to 404).
    assert preview_mod.run_retune(
        "no-such-id", PickingRetuneRequest(threshold=-3.0),
    ) is None
    preview_mod.discard_preview(pv.preview_id)


def test_discard_preview_is_idempotent_miss(monkeypatch):
    from magellon_sdk.models.tasks import TopazPickInput
    from plugin import preview as preview_mod

    monkeypatch.setattr(
        preview_mod, "compute_score_map",
        lambda f, **k: (_synthetic_score_map(), [256, 256]),
    )
    pv = preview_mod.run_preview(TopazPickInput(input_file="/tmp/x.mrc"))
    assert preview_mod.discard_preview(pv.preview_id) is True
    assert preview_mod.discard_preview(pv.preview_id) is False


def test_pick_plugin_advertises_preview_and_delegates(monkeypatch):
    from magellon_sdk.models.manifest import Capability
    from magellon_sdk.models.tasks import TopazPickInput
    from plugin import preview as preview_mod
    from plugin.plugin import TopazDenoisePlugin, TopazPickPlugin

    pick = TopazPickPlugin()
    assert Capability.PREVIEW in pick.capabilities
    # Denoise shares the container but has no interactive preview.
    assert Capability.PREVIEW not in TopazDenoisePlugin().capabilities

    monkeypatch.setattr(
        preview_mod, "compute_score_map",
        lambda f, **k: (_synthetic_score_map(), [128, 128]),
    )
    pv = pick.preview(
        TopazPickInput(input_file="/tmp/x.mrc", engine_opts={"radius": 4})
    )
    assert pv.num_particles == 5
    assert pick.discard_preview(pv.preview_id) is True
