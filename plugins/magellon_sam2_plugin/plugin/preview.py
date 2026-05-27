"""PREVIEW capability for the SAM2 plugin.

Preview runs auto-pick once, caches the result, and lets the client
retune thresholds against the cached masks without re-running the encoder.
This is the same contract as the template-picker's preview flow.
"""
from __future__ import annotations

import uuid
from typing import Dict, Optional

try:
    from cachetools import TTLCache
    _CACHE: TTLCache = TTLCache(maxsize=8, ttl=600)
except ImportError:
    _CACHE: Dict[str, dict] = {}  # type: ignore[assignment]


def run_preview(input_data) -> object:
    from magellon_sdk.capabilities.preview_models import PickingPreviewResult
    from plugin.compute import auto_pick

    result = auto_pick(
        image_path=input_data.image_path,
        model_variant=getattr(input_data, "model_variant", "facebook/sam2.1-hiera-tiny"),
        stability_score_threshold=getattr(input_data, "stability_score_threshold", 0.85),
        predicted_iou_threshold=getattr(input_data, "predicted_iou_threshold", 0.75),
        image_pixel_size=getattr(input_data, "image_pixel_size", 1.0),
        particle_diameter_min_angstrom=getattr(input_data, "particle_diameter_min_angstrom", 100.0),
        particle_diameter_max_angstrom=getattr(input_data, "particle_diameter_max_angstrom", 500.0),
        min_circularity=getattr(input_data, "min_circularity", 0.3),
    )

    import json
    from pathlib import Path
    particles = []
    path = result.get("particles_json_path")
    if path and Path(path).exists():
        with open(path) as f:
            raw = json.load(f)
        particles = [{"x": p["x"], "y": p["y"], "score": p.get("score", 0.0)} for p in raw]

    preview_id = str(uuid.uuid4())
    _CACHE[preview_id] = {
        "input": input_data,
        "result": result,
        "particles": particles,
    }

    return PickingPreviewResult(
        preview_id=preview_id,
        particles=particles,
        num_particles=len(particles),
        image_shape=result.get("image_shape"),
        score_map_png_base64=None,
        score_range=None,
    )


def run_retune(preview_id: str, params) -> Optional[object]:
    from magellon_sdk.capabilities.preview_models import PickingRetuneResult
    entry = _CACHE.get(preview_id)
    if not entry:
        return None

    threshold = getattr(params, "threshold", 0.75)
    max_peaks = getattr(params, "max_peaks", 500)

    particles = [p for p in entry["particles"] if p.get("score", 0.0) >= threshold]
    if max_peaks:
        particles = sorted(particles, key=lambda p: p.get("score", 0.0), reverse=True)[:max_peaks]

    return PickingRetuneResult(particles=particles)


def discard_preview(preview_id: str) -> bool:
    if preview_id in _CACHE:
        del _CACHE[preview_id]
        return True
    return False
