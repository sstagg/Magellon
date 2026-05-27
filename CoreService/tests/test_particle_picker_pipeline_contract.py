"""Particle picking output compatibility for extraction and 2D classing.

This is an in-process pipeline contract, not a Docker/RabbitMQ lifecycle
test. It pins the data-plane shape shared by template-picker, Topaz, and
BoxNet: each picker writes a particles JSON file that stack-maker can box
directly, and the resulting STAR/MRCS can feed the CAN classifier.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STACK_PLUGIN_ROOT = REPO_ROOT / "plugins" / "magellon_stack_maker_plugin"
CAN_PLUGIN_ROOT = REPO_ROOT / "plugins" / "magellon_can_classifier_plugin"


@contextmanager
def _plugin_import_context(plugin_root: Path):
    """Temporarily import one plugin package named ``plugin``.

    The Magellon plugin layout intentionally uses the same top-level
    package name in every plugin archive. Tests that load multiple
    plugins in one Python process must isolate that package name.
    """
    saved_path = list(sys.path)
    saved_plugin_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "plugin" or name.startswith("plugin.")
    }
    saved_core_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "core" or name.startswith("core.")
    }
    for name in [*saved_plugin_modules, *saved_core_modules]:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(plugin_root))
    try:
        yield
    finally:
        for name in [
            name
            for name in sys.modules
            if (
                name == "plugin"
                or name.startswith("plugin.")
                or name == "core"
                or name.startswith("core.")
            )
        ]:
            sys.modules.pop(name, None)
        sys.modules.update(saved_plugin_modules)
        sys.modules.update(saved_core_modules)
        sys.path[:] = saved_path


def _write_micrograph(path: Path, centers: list[tuple[int, int]]) -> None:
    mrcfile = pytest.importorskip("mrcfile")

    yy, xx = np.indices((128, 128), dtype=np.float32)
    rng = np.random.default_rng(7)
    image = 0.03 * rng.standard_normal((128, 128)).astype(np.float32)
    for i, (x, y) in enumerate(centers):
        radius = 5 if i % 2 == 0 else 8
        image[((xx - x) ** 2 + (yy - y) ** 2) <= radius ** 2] += 1.0
    with mrcfile.new(str(path), overwrite=True) as m:
        m.set_data(image.astype(np.float32))


def test_picker_outputs_feed_stack_maker_and_can_classifier(tmp_path):
    pytest.importorskip("scipy")
    pytest.importorskip("mrcfile")

    picker_payloads = {
        "template-picker": [
            {
                "center": [32, 32],
                "x": 32,
                "y": 32,
                "radius": 12,
                "score": 0.94,
                "template_index": 1,
            },
            {
                "center": [96, 32],
                "x": 96,
                "y": 32,
                "radius": 12,
                "score": 0.88,
                "template_index": 2,
            },
        ],
        "topaz": [
            {"center": [32, 96], "radius": 112, "score": 6.3},
            {"center": [96, 96], "radius": 112, "score": 5.7},
        ],
        "boxnet": [
            {"center": [64, 32], "radius": 56, "score": 0.91},
            {"center": [64, 96], "radius": 56, "score": 0.84},
        ],
    }

    centers = [
        tuple(pick["center"])
        for picks in picker_payloads.values()
        for pick in picks
    ]
    micrograph_path = tmp_path / "micrograph.mrc"
    _write_micrograph(micrograph_path, centers)

    manifest_items = []
    for picker_name, picks in picker_payloads.items():
        for pick in picks:
            assert set(("center", "radius", "score")).issubset(pick)
        picks_path = tmp_path / f"{picker_name}-particles.json"
        picks_path.write_text(json.dumps(picks))
        manifest_items.append(
            {
                "micrograph_path": str(micrograph_path),
                "particles_path": str(picks_path),
                "micrograph_name": f"{picker_name}.mrc",
            }
        )

    manifest_path = tmp_path / "picker-family-batch.json"
    manifest_path.write_text(json.dumps({"items": manifest_items}))

    with _plugin_import_context(STACK_PLUGIN_ROOT):
        from magellon_sdk.models.tasks import ParticleExtractionInput
        from plugin.plugin import StackMakerPlugin

        stack_output = StackMakerPlugin().execute(
            ParticleExtractionInput(
                micrograph_path=str(micrograph_path),
                particles_path=manifest_items[0]["particles_path"],
                box_size=32,
                edge_width=2,
                apix=1.25,
                output_dir=str(tmp_path / "stack"),
                engine_opts={
                    "batch_manifest_path": str(manifest_path),
                    "output_stem": "picker_family_particles",
                },
            )
        )

    assert stack_output.particle_count == 6
    assert Path(stack_output.mrcs_path).exists()
    assert Path(stack_output.star_path).exists()

    with _plugin_import_context(CAN_PLUGIN_ROOT):
        from plugin.compute import classify_stack

        summary = classify_stack(
            mrcs_path=stack_output.mrcs_path,
            star_path=stack_output.star_path,
            output_dir=str(tmp_path / "class2d"),
            apix=stack_output.apix,
            num_classes=2,
            num_presentations=200,
            align_iters=1,
            threads=1,
            can_threads=1,
            compute_backend="cpu",
            max_particles=None,
            invert=False,
            write_aligned_stack=False,
            engine_opts={
                "learn": 0.05,
                "ilearn": 0.001,
                "max_age": 50,
                "center_particles": False,
            },
        )

    assert summary["num_particles_classified"] == 6
    assert 1 <= summary["num_classes_emitted"] <= 2
    for key in (
        "class_averages_path",
        "assignments_csv_path",
        "class_counts_csv_path",
        "run_summary_path",
    ):
        assert Path(summary[key]).exists(), key
