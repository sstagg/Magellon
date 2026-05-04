"""PI-3: algorithm parity between in-process pp/template-picker and the
external magellon_template_picker_plugin.

The two algorithms are forks: external was branched from the in-process
one in commit 8513666 (Phase 6, 2026-05-03). At fork day the code was
identical save for two comment lines (verified by file diff). This test
pins the equivalence so a future change to either side that drifts the
output surfaces immediately — operators expecting "external picker
matches in-process picker" don't get silently surprised.

Compares: pick coordinates, count, ordering. Tolerance is exact match
since the algorithms are byte-identical Python (no nondeterminism in
the FFT path).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_PICKER_DIR = REPO_ROOT / "plugins" / "magellon_template_picker_plugin"


def _load_external_pick_particles():
    """Import the external plugin's pick_particles without polluting
    sys.modules permanently. The external repo's package layout is
    ``plugin/algorithm.py``; we add its parent to sys.path just for
    the import then back out."""
    if not EXTERNAL_PICKER_DIR.is_dir():
        pytest.skip(
            f"external plugin source not present at {EXTERNAL_PICKER_DIR}",
        )
    added = str(EXTERNAL_PICKER_DIR)
    sys.path.insert(0, added)
    try:
        # Use a unique module name to avoid collision with the
        # in-process picker's ``plugin`` namespace if any.
        import importlib
        spec = importlib.util.spec_from_file_location(
            "_external_picker_algorithm",
            EXTERNAL_PICKER_DIR / "plugin" / "algorithm.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod.pick_particles
    finally:
        try:
            sys.path.remove(added)
        except ValueError:
            pass


def _make_gaussian_blob(size: int, sigma: float, center: tuple) -> np.ndarray:
    y, x = np.ogrid[:size, :size]
    cy, cx = center
    return np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * sigma ** 2)).astype(np.float32)


def _fixture_micrograph(size: int = 512) -> np.ndarray:
    """Same fixture shape as the in-process picker's existing tests
    (``test_template_picker.py:_make_micrograph_with_particles``).
    Holding the fixture stable means a regression in either picker
    surfaces as a different pick set."""
    rng = np.random.RandomState(42)
    image = rng.normal(0, 0.05, (size, size)).astype(np.float32)
    for cy, cx in [(128, 128), (128, 384), (384, 128), (384, 384), (256, 256)]:
        image += _make_gaussian_blob(size, 8.0, (cy, cx))
    return image


def _fixture_template() -> np.ndarray:
    return _make_gaussian_blob(64, 8.0, (32, 32))


def _normalize_picks(particles):
    """Reduce a particle list to a comparable form. The two impls
    might emit fields in different order; comparing on
    ``(x, y, score)`` triples avoids dict-comparison gotchas."""
    return sorted(
        (p["x"], p["y"], round(p["score"], 6)) for p in particles
    )


def test_external_picker_matches_in_process_picker_on_synthetic_micrograph():
    """End-to-end parity check on a deterministic synthetic image.

    Both pickers should:
      - find the same number of particles
      - at the same coordinates
      - with identical scores (to 6 decimals)

    Drift here means the algorithms diverged. Either fix the diff or
    update this test consciously; do not silently relax the assertion.
    """
    from plugins.pp.template_picker.algorithm import pick_particles as in_process_pick

    external_pick = _load_external_pick_particles()

    image = _fixture_micrograph(size=512)
    template = _fixture_template()
    params = {
        "diameter_angstrom": 64.0,
        "pixel_size_angstrom": 1.0,
        "threshold": 0.1,
        "max_peaks": 100,
    }

    in_proc_result = in_process_pick(image=image, templates=[template], params=params)
    ext_result = external_pick(image=image, templates=[template], params=params)

    in_proc_picks = _normalize_picks(in_proc_result["particles"])
    ext_picks = _normalize_picks(ext_result["particles"])

    assert len(ext_picks) == len(in_proc_picks), (
        f"pick count drift: in-process={len(in_proc_picks)} "
        f"external={len(ext_picks)}"
    )
    assert ext_picks == in_proc_picks, (
        "pick coordinate / score drift between in-process and external "
        "template pickers; the algorithms have diverged"
    )


def test_external_picker_score_map_matches_in_process_picker():
    """Beyond particle coords, the merged score map should be
    bitwise-equivalent. The preview UX (Move 1) depends on the score
    map — drift here would mean preview pixels don't match the actual
    pick output."""
    from plugins.pp.template_picker.algorithm import pick_particles as in_process_pick

    external_pick = _load_external_pick_particles()

    image = _fixture_micrograph(size=256)
    template = _make_gaussian_blob(48, 6.0, (24, 24))
    params = {
        "diameter_angstrom": 48.0,
        "pixel_size_angstrom": 1.0,
        "threshold": 0.05,
        "max_peaks": 50,
    }

    in_proc = in_process_pick(image=image, templates=[template], params=params)
    ext = external_pick(image=image, templates=[template], params=params)

    np.testing.assert_allclose(
        ext["merged_score_map"],
        in_proc["merged_score_map"],
        rtol=1e-6,
        atol=1e-6,
        err_msg="score map drift between in-process and external pickers",
    )
