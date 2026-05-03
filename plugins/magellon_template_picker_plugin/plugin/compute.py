"""Template-picker compute glue.

Reads an MRC + one or more template MRCs, calls the vendored
``pick_particles``, writes ``particles.json``, returns a small dict
the plugin's result factory consumes.

Heavy imports (mrcfile, scipy) are lazy so plugin contract tests run
without them. Algorithm itself is import-clean against numpy +
(lazy) scipy — see ``plugin/algorithm.py``.
"""
from __future__ import annotations

import glob
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _load_mrc(path: str) -> np.ndarray:
    """Read an .mrc / .mrcs file as a 2D float32 array."""
    import mrcfile  # lazy

    with mrcfile.open(path, permissive=True) as m:
        arr = np.asarray(m.data, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"micrograph at {path} has ndim={arr.ndim}, expected 2")
    return arr


def _resolve_template_paths(spec: Any) -> List[str]:
    """Accept a single path, a list of paths, or a glob pattern."""
    if spec is None:
        raise ValueError("templates is required (path, list, or glob)")
    if isinstance(spec, list):
        return [str(p) for p in spec]
    s = str(spec)
    if any(c in s for c in "*?["):
        matches = sorted(glob.glob(s))
        if not matches:
            raise ValueError(f"templates glob matched 0 files: {s}")
        return matches
    return [s]


def _resolve_output_path(image_path: str, output_dir: Optional[str]) -> str:
    """``<output_dir or image_dir>/particles.json`` next to the image."""
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, "particles.json")
    image_dir = os.path.dirname(os.path.abspath(image_path))
    return os.path.join(image_dir, "particles.json")


def run_template_pick(
    *,
    image_path: str,
    template_paths: List[str],
    diameter_angstrom: float,
    pixel_size_angstrom: float,
    template_pixel_size_angstrom: Optional[float] = None,
    threshold: float = 0.4,
    output_dir: Optional[str] = None,
    engine_opts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """End-to-end pick. Returns a dict with the output path + count
    for the plugin's result factory."""
    from plugin.algorithm import pick_particles  # lazy: pulls scipy

    image = _load_mrc(image_path)
    templates = [_load_mrc(p) for p in template_paths]

    opts = engine_opts or {}
    params: Dict[str, Any] = {
        "diameter_angstrom": float(diameter_angstrom),
        "pixel_size_angstrom": float(pixel_size_angstrom),
        "threshold": float(threshold),
    }
    # Optional knobs flow through engine_opts unmodified.
    for k in (
        "bin", "max_threshold", "max_peaks", "overlap_multiplier",
        "max_blob_size_multiplier", "min_blob_roundness", "peak_position",
        "border_pixels", "angle_ranges",
    ):
        if k in opts:
            params[k] = opts[k]

    # Template apix can override per call (Sandbox CLI accepts mismatch).
    if template_pixel_size_angstrom is not None:
        # The vendored algorithm rescales templates internally when
        # bin/apix differs; override happens via the algorithm's own
        # rescale path. We pass it as a side input via engine_opts.
        params.setdefault("template_pixel_size_angstrom", float(template_pixel_size_angstrom))

    result = pick_particles(image=image, templates=templates, params=params)
    particles = result.get("particles", [])

    out_path = _resolve_output_path(image_path, output_dir)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(particles, f, indent=2)

    return {
        "particles_json_path": out_path,
        "num_particles": len(particles),
        "particles": particles,
        "image_shape": list(image.shape),
    }
