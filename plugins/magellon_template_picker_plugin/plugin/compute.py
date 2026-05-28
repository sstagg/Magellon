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
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def _bin_image(image: np.ndarray, bin_factor: int) -> np.ndarray:
    """Average-bin a 2D image by a power-of-two factor."""
    bin_factor = int(bin_factor)
    if not _is_power_of_two(bin_factor):
        raise ValueError("bin_factor must be a power-of-two integer (1,2,4,8,...)")
    if bin_factor == 1:
        return np.asarray(image, dtype=np.float32)

    height, width = image.shape
    binned_height = (height // bin_factor) * bin_factor
    binned_width = (width // bin_factor) * bin_factor
    if binned_height == 0 or binned_width == 0:
        raise ValueError("bin_factor is too large for image dimensions")

    cropped = np.asarray(image[:binned_height, :binned_width], dtype=np.float32)
    reshaped = cropped.reshape(
        binned_height // bin_factor,
        bin_factor,
        binned_width // bin_factor,
        bin_factor,
    )
    return reshaped.mean(axis=(1, 3), dtype=np.float32)


def _rescale_template(
    template: np.ndarray,
    template_apix: float,
    target_apix: float,
) -> np.ndarray:
    """Resample a template so its pixel size matches the working image."""
    if template_apix <= 0 or target_apix <= 0:
        raise ValueError("pixel sizes must be > 0")
    scale = float(template_apix) / float(target_apix)
    if abs(scale - 1.0) < 1e-6:
        return np.asarray(template, dtype=np.float32)

    from scipy import ndimage  # lazy

    out = ndimage.zoom(np.asarray(template, dtype=np.float32), zoom=scale, order=1)
    if out.ndim != 2 or min(out.shape) < 2:
        raise ValueError(
            "template became too small after pixel-size/bin rescaling; "
            "lower bin_factor or use a larger template"
        )
    return out.astype(np.float32)


def _lowpass_gaussian(
    image: np.ndarray,
    apix: float,
    resolution_angstrom: Optional[float],
) -> np.ndarray:
    if resolution_angstrom is None:
        return np.asarray(image, dtype=np.float32)
    if resolution_angstrom <= 0:
        raise ValueError("lowpass_resolution must be > 0")
    if apix <= 0:
        raise ValueError("pixel size must be > 0")

    from scipy import ndimage  # lazy

    sigma_pixels = 0.187 * float(resolution_angstrom) / float(apix)
    if sigma_pixels <= 0:
        return np.asarray(image, dtype=np.float32)
    return ndimage.gaussian_filter(image, sigma=sigma_pixels).astype(np.float32)


def _preprocess_image_and_templates(
    *,
    image: np.ndarray,
    templates: Sequence[np.ndarray],
    image_pixel_size_angstrom: float,
    template_pixel_size_angstrom: Optional[float],
    bin_factor: int,
    invert_templates: bool,
    lowpass_resolution: Optional[float],
) -> Tuple[np.ndarray, List[np.ndarray], float, int]:
    """Prepare the working arrays used by the FFT matcher.

    The algorithm operates in the coordinate system of the arrays it is
    given. This helper performs the binning/resampling first and returns
    the effective working pixel size so callers can scale particles back
    to source-image coordinates.
    """
    effective_bin = int(bin_factor or 1)
    binned_image = _bin_image(image, effective_bin)
    target_apix = float(image_pixel_size_angstrom) * float(effective_bin)
    binned_image = _lowpass_gaussian(binned_image, target_apix, lowpass_resolution)

    template_apix = float(template_pixel_size_angstrom or image_pixel_size_angstrom)
    processed_templates: List[np.ndarray] = []
    for template in templates:
        tmpl = np.asarray(template, dtype=np.float32)
        if invert_templates:
            tmpl = -1.0 * tmpl
        tmpl = _rescale_template(tmpl, template_apix, target_apix)
        tmpl = _lowpass_gaussian(tmpl, target_apix, lowpass_resolution)
        processed_templates.append(tmpl.astype(np.float32))

    return binned_image.astype(np.float32), processed_templates, target_apix, effective_bin


def _scale_particle_to_original(
    particle: Dict[str, Any],
    *,
    bin_factor: int,
    default_radius: Optional[float] = None,
) -> Dict[str, Any]:
    """Map one picker particle from working-image pixels to source pixels."""
    out = dict(particle)
    scale = int(bin_factor or 1)

    center = out.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        x = float(center[0])
        y = float(center[1])
    else:
        x = float(out.get("x", 0))
        y = float(out.get("y", 0))

    if scale > 1:
        x = (x + 0.5) * scale - 0.5
        y = (y + 0.5) * scale - 0.5

    x_i = int(round(x))
    y_i = int(round(y))
    out["x"] = x_i
    out["y"] = y_i
    out["center"] = [x_i, y_i]

    if "radius" in out and out["radius"] is not None:
        radius = float(out["radius"])
        out["radius"] = max(1, int(round(radius * scale)))
    elif default_radius is not None:
        out["radius"] = max(1, int(round(float(default_radius))))

    return out


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


def _canonical_radius_pixels(
    *,
    diameter_angstrom: float,
    pixel_size_angstrom: float,
    bin_factor: float,
) -> int:
    radius = float(diameter_angstrom) / float(pixel_size_angstrom) / 2.0
    radius = radius / max(1.0, float(bin_factor))
    return max(1, int(round(radius)))


def _canonicalize_particle_pick(
    particle: Dict[str, Any],
    *,
    default_radius: int,
) -> Dict[str, Any]:
    """Return the shared picker artifact shape while preserving extras."""
    out = dict(particle)
    center = out.get("center")
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        if "x" in out and "y" in out:
            center = [out["x"], out["y"]]
        elif "x_coordinate" in out and "y_coordinate" in out:
            center = [out["x_coordinate"], out["y_coordinate"]]
        else:
            raise ValueError("template pick must include center or x/y coordinates")
    x = int(round(float(center[0])))
    y = int(round(float(center[1])))
    out["center"] = [x, y]
    out.setdefault("x", x)
    out.setdefault("y", y)
    raw_radius = out.get("radius", default_radius)
    if raw_radius is None:
        raw_radius = default_radius
    out["radius"] = max(1, int(round(float(raw_radius))))
    out["score"] = float(out.get("score", 0.0))
    return out


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
    opts = engine_opts or {}
    templates = [_load_template_cached(p) for p in template_paths]
    bin_factor = int(opts.get("bin", opts.get("bin_factor", 1)) or 1)
    lowpass_resolution = opts.get("lowpass_resolution")
    image_working, templates_working, target_apix, effective_bin = (
        _preprocess_image_and_templates(
            image=image,
            templates=templates,
            image_pixel_size_angstrom=float(pixel_size_angstrom),
            template_pixel_size_angstrom=template_pixel_size_angstrom,
            bin_factor=bin_factor,
            invert_templates=bool(opts.get("invert_templates", False)),
            lowpass_resolution=lowpass_resolution,
        )
    )

    params: Dict[str, Any] = {
        "diameter_angstrom": float(diameter_angstrom),
        "pixel_size_angstrom": float(target_apix),
        "threshold": float(threshold),
        # Preprocessing has already applied the bin factor. The matcher
        # should treat the working image as its native coordinate system.
        "bin": 1.0,
    }
    # Optional knobs flow through engine_opts unmodified.
    for k in (
        "max_threshold", "max_peaks", "overlap_multiplier",
        "max_blob_size_multiplier", "min_blob_roundness", "peak_position",
        "border_pixels", "angle_ranges",
    ):
        if k in opts:
            params[k] = opts[k]

    result = pick_particles(image=image_working, templates=templates_working, params=params)
    default_radius = _canonical_radius_pixels(
        diameter_angstrom=diameter_angstrom,
        pixel_size_angstrom=pixel_size_angstrom,
        bin_factor=1.0,
    )
    particles = [
        _canonicalize_particle_pick(
            _scale_particle_to_original(p, bin_factor=effective_bin),
            default_radius=default_radius,
        )
        for p in result.get("particles", [])
    ]

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
