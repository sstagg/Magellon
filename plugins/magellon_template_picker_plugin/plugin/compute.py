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
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from cachetools import LRUCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template cache (Reviewer F — batch perf)
#
# Pre-fix: every dispatch_capability("/execute", ...) call re-loaded
# every template via mrcfile.open. For a batch of 100 images × 5
# templates that's 500 disk reads; on networked GPFS each is
# milliseconds-to-tens-of-milliseconds, so the redundant work
# dominates. Cache the raw loaded array keyed by (path, mtime); a
# template file edit invalidates the entry on next access.
#
# 64 entries covers the realistic ceiling (operators don't pick
# against >>10 templates simultaneously). LRU instead of TTL because
# templates don't go stale on time — only on edit.
# ---------------------------------------------------------------------------

_TEMPLATE_CACHE_MAX = 64
_template_cache: LRUCache = LRUCache(maxsize=_TEMPLATE_CACHE_MAX)
_template_cache_lock = Lock()


def _template_cache_key(path: str) -> Tuple[str, float]:
    """``(absolute path, mtime)`` — mtime change invalidates the entry
    on next access without us having to track edits explicitly."""
    abs_path = os.path.abspath(path)
    try:
        mtime = os.path.getmtime(abs_path)
    except OSError:
        mtime = -1.0
    return abs_path, mtime


def reset_template_cache() -> None:
    """Test helper. Clears the in-memory template cache so a test
    that mutates a template file mid-run can re-trigger the load."""
    with _template_cache_lock:
        _template_cache.clear()


def _load_mrc(path: str) -> np.ndarray:
    """Read an .mrc / .mrcs file as a 2D float32 array. Image MRCs
    aren't cached (each image is unique to one job); template MRCs
    use ``_load_template_cached`` instead."""
    import mrcfile  # lazy

    with mrcfile.open(path, permissive=True) as m:
        arr = np.asarray(m.data, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"micrograph at {path} has ndim={arr.ndim}, expected 2")
    return arr


def _load_template_cached(path: str) -> np.ndarray:
    """Cached template load keyed by ``(path, mtime)``. Subsequent
    calls in the same process for an unchanged file return the
    cached array; a file edit (mtime change) invalidates."""
    key = _template_cache_key(path)
    with _template_cache_lock:
        cached = _template_cache.get(key)
    if cached is not None:
        return cached
    arr = _load_mrc(path)
    with _template_cache_lock:
        _template_cache[key] = arr
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
    # Templates use the cached loader; image stays uncached (each
    # batch image is unique to one job).
    templates = [_load_template_cached(p) for p in template_paths]

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
