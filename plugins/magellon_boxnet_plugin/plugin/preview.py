"""PREVIEW capability for the BoxNet picker.

The initial preview runs the CNN once, caches the downsampled particle
probability map, and returns picks without writing an IPP record.
Retune re-runs local-maxima extraction on the cached score map.
"""
from __future__ import annotations

import base64
import io
import time
import uuid
from typing import Any, Dict, Optional

import numpy as np

from magellon_sdk.capabilities import (
    PickingPreviewResult,
    PickingRetuneRequest,
    PickingRetuneResult,
)

from plugin.models import BoxnetPickerInput


_PREVIEW_TTL_SECONDS = 600
_PREVIEW_MAX_ENTRIES = 20
_previews: Dict[str, Dict[str, Any]] = {}


def run_preview(input_data: BoxnetPickerInput) -> PickingPreviewResult:
    """Run BoxNet once and return unsaved particles for the overlay."""
    if not input_data.image_path:
        raise ValueError("boxnet preview: image_path is required")

    from plugin.algorithm import compute_boxnet_score_map, picks_from_score_map
    from plugin.compute import _load_mrc, _resolve_local_path

    local_image_path = _resolve_local_path(input_data.image_path) or input_data.image_path
    image = _load_mrc(local_image_path)
    scale = int(input_data.scale)
    min_distance = int(input_data.min_distance)

    score_map = compute_boxnet_score_map(
        image,
        scale=scale,
        device=input_data.device,
        invert=bool(input_data.invert),
    )
    picks = picks_from_score_map(
        score_map,
        threshold=float(input_data.threshold),
        min_distance=min_distance,
        scale=scale,
    )

    preview_id = str(uuid.uuid4())
    _remember_preview(
        preview_id,
        {
            "score_map": score_map,
            "scale": scale,
            "min_distance": min_distance,
            "image_shape": [int(image.shape[0]), int(image.shape[1])],
        },
    )

    return PickingPreviewResult(
        preview_id=preview_id,
        particles=_particles_for_wire(picks),
        num_particles=len(picks),
        num_templates=0,
        target_pixel_size=float(scale),
        image_binning=scale,
        image_shape=[int(image.shape[0]), int(image.shape[1])],
        score_map_png_base64=_score_map_to_base64_png(score_map),
        score_range=[float(np.min(score_map)), float(np.max(score_map))],
    )


def run_retune(
    preview_id: str, params: PickingRetuneRequest,
) -> Optional[PickingRetuneResult]:
    """Re-threshold the cached BoxNet score map."""
    preview = _get_preview(preview_id)
    if preview is None:
        return None

    from plugin.algorithm import picks_from_score_map

    min_distance = int(params.radius or preview["min_distance"])
    picks = picks_from_score_map(
        preview["score_map"],
        threshold=float(params.threshold),
        min_distance=min_distance,
        scale=int(preview["scale"]),
        max_peaks=int(params.max_peaks) if params.max_peaks else None,
        max_threshold=params.max_threshold,
    )
    return PickingRetuneResult(
        particles=_particles_for_wire(picks),
        num_particles=len(picks),
    )


def discard_preview(preview_id: str) -> bool:
    _purge_expired()
    return _previews.pop(preview_id, None) is not None


def _remember_preview(preview_id: str, entry: Dict[str, Any]) -> None:
    _purge_expired()
    if len(_previews) >= _PREVIEW_MAX_ENTRIES:
        oldest = min(_previews.items(), key=lambda item: item[1]["created_at"])[0]
        _previews.pop(oldest, None)
    entry["created_at"] = time.monotonic()
    _previews[preview_id] = entry


def _get_preview(preview_id: str) -> Optional[Dict[str, Any]]:
    _purge_expired()
    return _previews.get(preview_id)


def _purge_expired() -> None:
    now = time.monotonic()
    expired = [
        key for key, entry in _previews.items()
        if now - float(entry.get("created_at", 0.0)) > _PREVIEW_TTL_SECONDS
    ]
    for key in expired:
        _previews.pop(key, None)


def _particles_for_wire(picks: list[dict]) -> list[dict]:
    particles: list[dict] = []
    for pick in picks:
        center = pick.get("center") or [pick.get("x"), pick.get("y")]
        particles.append(
            {
                "x": int(center[0]),
                "y": int(center[1]),
                "score": float(pick.get("score", 0.0)),
                "radius": int(pick.get("radius", 0) or 0),
            }
        )
    return particles


def _score_map_to_base64_png(score_map: np.ndarray) -> str:
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


__all__ = ["discard_preview", "run_preview", "run_retune"]
