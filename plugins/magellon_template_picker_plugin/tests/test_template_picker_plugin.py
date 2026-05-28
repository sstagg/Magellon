"""Contract pin tests for the external template-picker plugin.

Mirrors the FFT / topaz / stack-maker test suites. Phase 6
(2026-05-03) — confirms the SDK contract holds for the new plugin
and the back-compat shim absent (we use PluginBrokerRunner directly,
no per-plugin subclass).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def test_input_schema_is_plugin_owned_rich_model():
    """PE2-UI (2026-05-12): the plugin owns its input model so the
    runner page renders sliders + file pickers + accordion groups
    instead of the category contract's bare CryoEmImageInput shape.
    The plugin's TemplatePickerInput is distinct from PARTICLE_PICKER's
    minimum-shared-shape on purpose — the category contract stays as
    the floor used when no live plugin is announcing."""
    from plugin.models import TemplatePickerInput
    from plugin.plugin import TemplatePickerPlugin

    assert TemplatePickerPlugin.input_schema() is TemplatePickerInput
    # Rich UI metadata should round-trip through the JSON schema —
    # this is what the runner page renders.
    schema = TemplatePickerInput.model_json_schema()
    assert "template_paths" in schema["properties"]
    assert schema["properties"]["template_paths"]["ui_widget"] == "file_path_list"


def test_output_schema_matches_particle_picker_contract():
    """Output stays at the category-shared shape (ParticlePickingOutput)
    so downstream consumers can swap pickers without recompiling. Only
    the input shape is plugin-owned."""
    from magellon_sdk.categories.contract import PARTICLE_PICKER
    from plugin.plugin import TemplatePickerPlugin

    assert TemplatePickerPlugin.output_schema() is PARTICLE_PICKER.output_model


def test_get_info_provenance():
    from plugin.plugin import TemplatePickerPlugin

    info = TemplatePickerPlugin().get_info()
    assert info.name == "Template Picker"
    assert info.version == "0.1.1"


def test_manifest_advertises_progress_and_rmq_default():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import TemplatePickerPlugin

    manifest = TemplatePickerPlugin().manifest()
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------


def test_execute_rejects_missing_image_path():
    """image_path is required at the Pydantic layer now — the missing
    value triggers a ValidationError at construction time, not deep
    inside execute()."""
    from pydantic import ValidationError
    from plugin.models import TemplatePickerInput

    with pytest.raises(ValidationError, match="image_path"):
        TemplatePickerInput(template_paths=["/tmp/x.mrc"], diameter_angstrom=200.0)


def test_execute_rejects_empty_template_paths():
    """template_paths has min_length=1; validation fires at the model
    boundary so execute() doesn't have to defend itself."""
    from pydantic import ValidationError
    from plugin.models import TemplatePickerInput

    with pytest.raises(ValidationError, match="template_paths"):
        TemplatePickerInput(image_path="/tmp/m.mrc", template_paths=[])


def test_execute_picker_params_have_sensible_defaults():
    """Pre-PE2 the plugin required engine_opts to carry diameter,
    pixel sizes, etc. Post-PE2 those are typed fields with defaults
    matching the side-panel + README reference values, so a runner-page
    submission with just an image_path is valid."""
    from plugin.models import TemplatePickerInput

    inp = TemplatePickerInput(image_path="/tmp/m.mrc")
    assert inp.diameter_angstrom == 220.0
    assert inp.image_pixel_size == 3.16
    assert inp.template_pixel_size == 2.646
    assert inp.threshold == 0.35
    assert inp.bin_factor == 1
    assert inp.invert_templates is True


def test_preprocess_bins_image_and_rescales_templates():
    """The plugin path must apply bin_factor before FFT matching.

    A previous regression only used bin_factor to shrink the reported
    radius, leaving the full-resolution image in the expensive FFT loop.
    """
    from plugin.compute import _preprocess_image_and_templates

    image = np.arange(16, dtype=np.float32).reshape(4, 4)
    template = np.ones((4, 4), dtype=np.float32)

    working_image, working_templates, target_apix, effective_bin = (
        _preprocess_image_and_templates(
            image=image,
            templates=[template],
            image_pixel_size_angstrom=1.0,
            template_pixel_size_angstrom=1.0,
            bin_factor=2,
            invert_templates=False,
            lowpass_resolution=None,
        )
    )

    assert effective_bin == 2
    assert target_apix == pytest.approx(2.0)
    assert working_image.shape == (2, 2)
    assert np.allclose(working_image, np.array([[2.5, 4.5], [10.5, 12.5]], dtype=np.float32))
    assert working_templates[0].shape == (2, 2)


# ---------------------------------------------------------------------------
# Compute helpers (path resolution)
# ---------------------------------------------------------------------------


def test_resolve_template_paths_accepts_single_path(tmp_path):
    from plugin.compute import _resolve_template_paths

    p = tmp_path / "t1.mrc"
    p.touch()
    assert _resolve_template_paths(str(p)) == [str(p)]


def test_resolve_template_paths_accepts_list(tmp_path):
    from plugin.compute import _resolve_template_paths

    a = tmp_path / "t1.mrc"
    b = tmp_path / "t2.mrc"
    a.touch(); b.touch()
    assert _resolve_template_paths([str(a), str(b)]) == [str(a), str(b)]


def test_resolve_template_paths_expands_glob(tmp_path):
    from plugin.compute import _resolve_template_paths

    a = tmp_path / "t1.mrc"
    b = tmp_path / "t2.mrc"
    a.touch(); b.touch()
    pat = str(tmp_path / "t*.mrc")
    out = _resolve_template_paths(pat)
    # sorted glob matches
    assert sorted(out) == sorted([str(a), str(b)])


def test_resolve_template_paths_raises_on_empty_glob(tmp_path):
    from plugin.compute import _resolve_template_paths

    with pytest.raises(ValueError, match="0 files"):
        _resolve_template_paths(str(tmp_path / "no_match_*.mrc"))


# ---------------------------------------------------------------------------
# execute() round-trip with mocked algorithm
# ---------------------------------------------------------------------------


def test_execute_round_trip_with_mocked_algorithm(monkeypatch, tmp_path):
    """End-to-end through ``run_template_pick`` with the heavy
    pick_particles call mocked. Verifies path resolution + JSON write
    + output shape."""
    import mrcfile

    from magellon_sdk.categories.outputs import ParticlePickingOutput
    from plugin.models import TemplatePickerInput
    from plugin.plugin import TemplatePickerPlugin

    # Synthetic micrograph + template MRCs.
    mic = np.random.rand(64, 64).astype(np.float32)
    tmpl = np.random.rand(16, 16).astype(np.float32)
    mic_path = tmp_path / "m.mrc"
    tmpl_path = tmp_path / "t.mrc"
    with mrcfile.new(str(mic_path), overwrite=True) as f:
        f.set_data(mic)
    with mrcfile.new(str(tmpl_path), overwrite=True) as f:
        f.set_data(tmpl)

    fake_picks = [
        {"x": 32, "y": 32, "score": 0.9},
        {"x": 16, "y": 16, "score": 0.7},
    ]

    def _fake_pick(image, templates, params):
        return {"particles": fake_picks}

    # Patch the algorithm's pick_particles where compute imports it.
    import plugin.algorithm as algorithm_mod
    monkeypatch.setattr(algorithm_mod, "pick_particles", _fake_pick)

    out_dir = tmp_path / "out"
    inp = TemplatePickerInput(
        image_path=str(mic_path),
        template_paths=[str(tmpl_path)],
        diameter_angstrom=220.0,
        image_pixel_size=1.23,
        template_pixel_size=1.23,
        threshold=0.35,
        output_dir=str(out_dir),
    )

    out = TemplatePickerPlugin().execute(inp)

    assert isinstance(out, ParticlePickingOutput)
    assert out.num_particles == 2
    assert out.image_shape == [64, 64]
    # Rule 1: picks list NOT inlined even though size is small.
    assert out.picks is None
    # particles.json was written + contains the mocked picks.
    assert out.particles_json_path.endswith("particles.json")
    saved = json.loads(Path(out.particles_json_path).read_text())
    assert len(saved) == 2
    assert saved[0]["score"] == 0.9
    assert saved[0]["center"] == [32, 32]
    assert saved[0]["radius"] == 89
    assert saved[0]["x"] == 32
    assert saved[0]["y"] == 32


def test_preview_bins_working_arrays_and_returns_source_coordinates(monkeypatch, tmp_path):
    """Preview computes on binned arrays but returns source-image pixels.

    The image-viewer side panel overlays preview particles on the original
    micrograph canvas, so returned x/y/radius must be full-resolution.
    """
    import mrcfile

    from plugin.models import TemplatePickerInput
    from plugin.preview import discard_preview, run_preview

    mic = np.arange(64 * 64, dtype=np.float32).reshape(64, 64)
    tmpl = np.ones((16, 16), dtype=np.float32)
    mic_path = tmp_path / "m.mrc"
    tmpl_path = tmp_path / "t.mrc"
    with mrcfile.new(str(mic_path), overwrite=True) as f:
        f.set_data(mic)
    with mrcfile.new(str(tmpl_path), overwrite=True) as f:
        f.set_data(tmpl)

    def _fake_pick(image, templates, params):
        assert image.shape == (16, 16)
        assert templates[0].shape == (4, 4)
        assert params["pixel_size_angstrom"] == pytest.approx(8.0)
        assert params["bin"] == 1.0
        score_map = np.ones(image.shape, dtype=np.float32)
        angle_map = np.zeros(image.shape, dtype=np.float32)
        return {
            "particles": [{"x": 2, "y": 3, "score": 0.6}],
            "template_results": [{
                "score_map": score_map,
                "angle_map": angle_map,
                "template_index": 1,
            }],
            "merged_score_map": score_map,
        }

    import plugin.algorithm as algorithm_mod
    monkeypatch.setattr(algorithm_mod, "pick_particles", _fake_pick)

    result = run_preview(
        TemplatePickerInput(
            image_path=str(mic_path),
            template_paths=[str(tmpl_path)],
            diameter_angstrom=200.0,
            image_pixel_size=2.0,
            template_pixel_size=2.0,
            bin_factor=4,
            invert_templates=False,
        )
    )
    body = result.model_dump()

    assert body["image_shape"] == [64, 64]
    assert body["image_binning"] == 4
    assert body["target_pixel_size"] == pytest.approx(8.0)
    assert body["particles"][0]["x"] == 10
    assert body["particles"][0]["y"] == 14
    assert body["particles"][0]["center"] == [10, 14]
    assert body["particles"][0]["radius"] == 50
    assert discard_preview(body["preview_id"]) is True


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------


def test_build_pick_result_carries_envelope_ids_and_path_only():
    """Rule 1 again: build_pick_result emits paths + scalar
    summaries; never inlines particle coordinates."""
    from magellon_sdk.categories.outputs import ParticlePickingOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_pick_result

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    output = ParticlePickingOutput(
        num_particles=42,
        particles_json_path="/work/out/particles.json",
        image_shape=[7676, 7420],
        picks=None,
    )

    result = build_pick_result(task, output)
    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.code == 200
    assert "42 particles" in result.message
    assert result.output_data["particles_json_path"] == "/work/out/particles.json"
    assert result.output_data["num_particles"] == 42
    # Picks not in output_data — refs only.
    assert "picks" not in result.output_data
    assert {f.path for f in result.output_files} == {"/work/out/particles.json"}
