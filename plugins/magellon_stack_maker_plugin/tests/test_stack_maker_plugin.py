"""Contract pin tests for the stack-maker plugin.

Pins the SDK contract pieces the dispatcher and result projector
expect — anything past that (algorithm correctness, file format
fidelity) lives in the algorithm-level tests in the Sandbox crate
and in the Phase 5b integration tests (deferred)."""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def test_input_and_output_schema_match_category_contract():
    """The plugin's declared schemas must equal the SDK contract — if
    they drift, the dispatcher and the plugin can't speak the same
    language."""
    from magellon_sdk.categories.contract import PARTICLE_EXTRACTION_CATEGORY
    from plugin.plugin import StackMakerPlugin

    assert StackMakerPlugin.input_schema() is PARTICLE_EXTRACTION_CATEGORY.input_model
    assert StackMakerPlugin.output_schema() is PARTICLE_EXTRACTION_CATEGORY.output_model


def test_get_info_matches_provenance():
    from plugin.plugin import StackMakerPlugin

    info = StackMakerPlugin().get_info()
    assert info.name == "Stack Maker"
    assert info.version == "0.1.0"


def test_manifest_advertises_progress_and_rmq_default():
    from magellon_sdk.models.manifest import Capability, Transport
    from plugin.plugin import StackMakerPlugin

    manifest = StackMakerPlugin().manifest()
    assert Capability.PROGRESS_REPORTING in manifest.capabilities
    assert manifest.default_transport == Transport.RMQ


def test_image_token_uses_relion_order():
    """Phase 5 fix: ``NNNNNN@stack.mrcs`` (RELION order — what the CAN
    classifier expects). Pre-Phase-5 the Sandbox crate emitted
    ``stack.mrcs@NNNNNN`` which broke downstream consumption."""
    from plugin.algorithm import _format_image_token

    assert _format_image_token("/work/out/stack.mrcs", 7) == "000007@stack.mrcs"
    # No stack path → bare zero-padded index.
    assert _format_image_token(None, 7) == "000007"


def test_star_uses_image_pixel_size_column(tmp_path):
    """Phase 5 fix: ``_rlnImagePixelSize`` (what the classifier reads),
    not the original ``_rlnPixelSize``."""
    from plugin.algorithm import (
        ParticleStackConfig,
        _as_particle_coords,
        build_particle_records,
        write_relion_star,
    )

    micrograph = np.random.rand(64, 64).astype(np.float32)
    coords = _as_particle_coords([{"x": 32.0, "y": 32.0}])
    config = ParticleStackConfig(
        box_size=16,
        edge_width=2,
        micrograph_pixel_size_angstrom=1.23,
        image_name="m.mrc",
    )
    rows = build_particle_records(micrograph, coords, config)
    star = tmp_path / "out.star"
    write_relion_star(rows, str(star), stack_path="stack.mrcs", micrograph_pixel_size_angstrom=1.23)
    text = star.read_text()
    assert "_rlnImagePixelSize" in text
    assert "_rlnPixelSize " not in text  # the wrong name doesn't slip in


def test_build_extraction_result_carries_envelope_identifiers():
    """The result must echo job_id/task_id from the envelope so
    JobEventWriter can correlate it back to the originating task."""
    from magellon_sdk.categories.outputs import ParticleExtractionOutput
    from magellon_sdk.models import TaskMessage
    from plugin.plugin import build_extraction_result

    job_id = uuid4()
    task_id = uuid4()
    task = TaskMessage(id=task_id, job_id=job_id, data={})
    output = ParticleExtractionOutput(
        mrcs_path="/work/out/stack.mrcs",
        star_path="/work/out/stack.star",
        particle_count=42,
        apix=1.23,
        box_size=256,
        edge_width=2,
        micrograph_name="m.mrc",
        source_micrograph_path="/work/in/m.mrc",
        extras={"json_path": "/work/out/stack.json"},
    )

    result = build_extraction_result(task, output)
    assert result.job_id == job_id
    assert result.task_id == task_id
    assert result.code == 200
    assert result.message == "Extracted 42 particles"
    assert result.image_path == "/work/in/m.mrc"
    assert result.output_data["mrcs_path"] == "/work/out/stack.mrcs"
    assert result.output_data["star_path"] == "/work/out/stack.star"
    assert result.output_data["particle_count"] == 42
    assert result.output_data["json_path"] == "/work/out/stack.json"
    assert {f.name for f in result.output_files} == {"stack.mrcs", "stack.star", "stack.json"}


def test_execute_round_trip_extracts_and_normalizes(tmp_path):
    """End-to-end happy path: synthetic micrograph + 2 picks → MRCS +
    STAR written, particle_count is 2, paths populated."""
    import json

    import mrcfile

    from magellon_sdk.models.tasks import ParticleExtractionInput
    from plugin.plugin import StackMakerPlugin

    # Synthetic micrograph
    mic = np.random.rand(128, 128).astype(np.float32)
    mic_path = tmp_path / "synth.mrc"
    with mrcfile.new(str(mic_path), overwrite=True) as f:
        f.set_data(mic)

    # Picks JSON
    picks = [{"x": 64.0, "y": 64.0, "score": 0.9}, {"x": 32.0, "y": 32.0, "score": 0.7}]
    picks_path = tmp_path / "picks.json"
    picks_path.write_text(json.dumps(picks))

    out_dir = tmp_path / "out"
    inp = ParticleExtractionInput(
        micrograph_path=str(mic_path),
        particles_path=str(picks_path),
        box_size=32,
        edge_width=2,
        apix=1.0,
        output_dir=str(out_dir),
    )

    output = StackMakerPlugin().execute(inp)

    assert output.particle_count == 2
    assert Path(output.mrcs_path).exists()
    assert Path(output.star_path).exists()
    assert "json_path" in output.extras
    assert Path(output.extras["json_path"]).exists()

    # MRCS shape: 2 particles × 32 × 32
    with mrcfile.open(output.mrcs_path, permissive=True) as f:
        assert f.data.shape == (2, 32, 32)
