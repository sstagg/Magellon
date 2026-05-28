"""PREVIEW capability implementation for the template-picker plugin (PT-4).

The interactive preview-and-retune flow:
  1. ``preview()`` — load + preprocess image and templates, call the
     algorithm, cache score maps in a TTLCache, return the initial
     picks + a thumbnail PNG of the merged score map.
  2. ``retune()`` — re-extract from the cached score maps with new
     tunable params. Sub-100ms; no recomputation.
  3. ``discard_preview()`` — drop the cached state on the operator's
     "close preview" gesture.

Wire shape is the SDK's ``PickingPreviewResult`` /
``PickingRetuneRequest`` / ``PickingRetuneResult`` (see
``magellon_sdk.capabilities.preview_models``).
"""
from __future__ import annotations

import base64
import io
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from cachetools import TTLCache

from magellon_sdk.capabilities import (
    PickingPreviewResult,
    PickingRetuneRequest,
    PickingRetuneResult,
)

from plugin.models import TemplatePickerInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-process preview cache
# ---------------------------------------------------------------------------

_PREVIEW_TTL_SECONDS = 600
_PREVIEW_MAX_ENTRIES = 50
_previews: TTLCache = TTLCache(maxsize=_PREVIEW_MAX_ENTRIES, ttl=_PREVIEW_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Public API — called from PluginBase.preview / .retune / .discard_preview
# ---------------------------------------------------------------------------


def run_preview(input_data: TemplatePickerInput) -> PickingPreviewResult:
    """Compute correlation maps; cache them; return preview payload.

    PE2-UI (2026-05-12): now takes the plugin's typed ``TemplatePickerInput``
    directly. Pre-PE2 the body landed as ``CryoEmImageInput`` with an
    ``engine_opts`` dict; that path is gone now that the plugin owns
    its rich input shape.
    """
    from plugin.algorithm import pick_particles
    from plugin.compute import (
        _load_mrc,
        _load_template_cached,
        _preprocess_image_and_templates,
        _resolve_template_paths,
        _scale_particle_to_original,
    )

    if not input_data.image_path:
        raise ValueError("template-picker preview: image_path is required")
    diameter = float(input_data.diameter_angstrom)
    pixel_size = float(input_data.image_pixel_size)
    template_pixel_size = float(input_data.template_pixel_size)
    threshold = float(input_data.threshold)

    template_paths = _resolve_template_paths(input_data.template_paths)
    image = _load_mrc(input_data.image_path)
    # Templates use the (path, mtime)-keyed cache so a slider tick
    # that triggers a fresh /preview doesn't re-read template files
    # off GPFS. Image stays uncached.
    templates = [_load_template_cached(p) for p in template_paths]
    image_working, templates_working, target_apix, effective_bin = (
        _preprocess_image_and_templates(
            image=image,
            templates=templates,
            image_pixel_size_angstrom=pixel_size,
            template_pixel_size_angstrom=template_pixel_size,
            bin_factor=int(input_data.bin_factor),
            invert_templates=bool(input_data.invert_templates),
            lowpass_resolution=input_data.lowpass_resolution,
        )
    )

    params: Dict[str, Any] = {
        "diameter_angstrom": diameter,
        "pixel_size_angstrom": target_apix,
        "threshold": threshold,
        "bin": 1.0,
        "max_peaks": int(input_data.max_peaks),
        "overlap_multiplier": float(input_data.overlap_multiplier),
        "max_blob_size_multiplier": float(input_data.max_blob_size_multiplier),
        "min_blob_roundness": float(input_data.min_blob_roundness),
        "peak_position": input_data.peak_position,
    }
    if input_data.max_threshold is not None:
        params["max_threshold"] = float(input_data.max_threshold)
    if input_data.angle_ranges is not None:
        params["angle_ranges"] = [
            {"start": ar.start, "end": ar.end, "step": ar.step}
            for ar in input_data.angle_ranges
        ]

    result = pick_particles(image=image_working, templates=templates_working, params=params)

    # Cache the per-template score+angle maps so retune doesn't
    # recompute the FFT correlation. The algorithm normalises
    # template index from 0; preserve the same shape on retune.
    preview_id = str(uuid.uuid4())
    radius_pixels_original = diameter / pixel_size / 2.0
    radius_pixels_working = diameter / target_apix / 2.0
    image_shape = (int(image.shape[0]), int(image.shape[1]))
    working_shape = (int(image_working.shape[0]), int(image_working.shape[1]))
    _previews[preview_id] = {
        "template_results": result["template_results"],
        "image_shape": working_shape,
        "original_image_shape": image_shape,
        "radius_pixels": radius_pixels_working,
        "radius_pixels_original": radius_pixels_original,
        "bin_factor": effective_bin,
        "created_at": datetime.now(),
    }

    merged_map = result["merged_score_map"]
    score_min = float(np.min(merged_map))
    score_max = float(np.max(merged_map))

    return PickingPreviewResult(
        preview_id=preview_id,
        particles=[
            {
                **_scale_particle_to_original(
                    p,
                    bin_factor=effective_bin,
                    default_radius=radius_pixels_original,
                ),
                "score": float(p["score"]),
            }
            for p in result["particles"]
        ],
        num_particles=len(result["particles"]),
        num_templates=len(templates),
        target_pixel_size=target_apix,
        image_binning=effective_bin,
        image_shape=[image_shape[0], image_shape[1]],
        score_map_png_base64=_score_map_to_base64_png(merged_map),
        score_range=[score_min, score_max],
    )


def run_retune(
    preview_id: str, params: PickingRetuneRequest,
) -> Optional[PickingRetuneResult]:
    """Re-threshold the cached score maps with new tunable params.

    Returns ``None`` when the preview_id is unknown or expired —
    the SDK router maps that to a 404.
    """
    from plugin.algorithm import (
        _extract_particles_from_map,
        _merge_particles,
        _remove_border_particles,
    )

    preview = _previews.get(preview_id)
    if preview is None:
        return None

    radius_pixels = preview["radius_pixels"]
    radius_pixels_original = preview.get("radius_pixels_original", radius_pixels)
    bin_factor = int(preview.get("bin_factor", 1))
    image_shape = preview["image_shape"]

    all_particles: List[Dict[str, Any]] = []
    for item in preview["template_results"]:
        particles = _extract_particles_from_map(
            score_map=item["score_map"],
            angle_map=item["angle_map"],
            template_index=int(item["template_index"]),
            threshold=params.threshold,
            radius_pixels=radius_pixels,
            max_peaks=params.max_peaks,
            overlap_multiplier=params.overlap_multiplier,
            max_blob_size_multiplier=params.max_blob_size_multiplier,
            min_blob_roundness=params.min_blob_roundness,
            peak_position=params.peak_position,
        )
        particles = _remove_border_particles(
            particles=particles,
            diameter_pixels=radius_pixels * 2.0,
            image_width=image_shape[1],
            image_height=image_shape[0],
        )
        all_particles.extend(particles)

    merged = _merge_particles(
        particles=all_particles,
        radius_pixels=radius_pixels,
        overlap_multiplier=params.overlap_multiplier,
        max_peaks=params.max_peaks,
        max_threshold=params.max_threshold,
    )

    return PickingRetuneResult(
        particles=[
            {
                **_scale_particle_to_original(
                    p,
                    bin_factor=bin_factor,
                    default_radius=radius_pixels_original,
                ),
                "score": float(p["score"]),
            }
            for p in merged
        ],
        num_particles=len(merged),
    )


def discard_preview(preview_id: str) -> bool:
    """Drop a cached preview. Returns True on hit, False on miss."""
    return _previews.pop(preview_id, None) is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _score_map_to_base64_png(score_map: np.ndarray) -> str:
    """Compress a 2D float map into a base64 PNG thumbnail."""
    from PIL import Image

    data = score_map.astype(np.float32)
    finite = np.isfinite(data)
    if finite.any():
        lo = float(np.percentile(data[finite], 1.0))
        hi = float(np.percentile(data[finite], 99.0))
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo:
        hi = lo + 1e-6

    clipped = np.clip(data, lo, hi)
    normalized = ((clipped - lo) / (hi - lo) * 255).astype(np.uint8)

    img = Image.fromarray(normalized, mode="L")
    max_dim = 1024
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize(
            (int(img.width * ratio), int(img.height * ratio)),
            Image.BILINEAR,
        )

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


__all__ = [
    "discard_preview",
    "run_preview",
    "run_retune",
]
