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


def test_input_and_output_schema_match_particle_picker_contract():
    from magellon_sdk.categories.contract import PARTICLE_PICKER
    from plugin.plugin import TemplatePickerPlugin

    assert TemplatePickerPlugin.input_schema() is PARTICLE_PICKER.input_model
    assert TemplatePickerPlugin.output_schema() is PARTICLE_PICKER.output_model


def test_get_info_provenance():
    from plugin.plugin import TemplatePickerPlugin

    info = TemplatePickerPlugin().get_info()
    assert info.name == "Template Picker"
    assert info.version == "0.1.0"


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
    from magellon_sdk.models.tasks import CryoEmImageInput
    from plugin.plugin import TemplatePickerPlugin

    inp = CryoEmImageInput(engine_opts={
        "templates": "/tmp/x.mrc",
        "diameter_angstrom": 200.0,
        "pixel_size_angstrom": 1.0,
    })
    with pytest.raises(ValueError, match="image_path"):
        TemplatePickerPlugin().execute(inp)


def test_execute_rejects_missing_templates():
    from magellon_sdk.models.tasks import CryoEmImageInput
    from plugin.plugin import TemplatePickerPlugin

    inp = CryoEmImageInput(
        image_path="/tmp/m.mrc",
        engine_opts={"diameter_angstrom": 200.0, "pixel_size_angstrom": 1.0},
    )
    with pytest.raises(ValueError, match="templates"):
        TemplatePickerPlugin().execute(inp)


def test_execute_rejects_missing_required_picker_params():
    from magellon_sdk.models.tasks import CryoEmImageInput
    from plugin.plugin import TemplatePickerPlugin

    # Missing diameter_angstrom.
    inp = CryoEmImageInput(
        image_path="/tmp/m.mrc",
        engine_opts={"templates": "/tmp/x.mrc", "pixel_size_angstrom": 1.0},
    )
    with pytest.raises(ValueError, match="diameter_angstrom"):
        TemplatePickerPlugin().execute(inp)


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
    from magellon_sdk.models.tasks import CryoEmImageInput
    from plugin import compute as compute_mod
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
    inp = CryoEmImageInput(
        image_path=str(mic_path),
        engine_opts={
            "templates": str(tmpl_path),
            "diameter_angstrom": 220.0,
            "pixel_size_angstrom": 1.23,
            "threshold": 0.35,
            "output_dir": str(out_dir),
        },
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
