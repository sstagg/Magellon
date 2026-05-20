"""PREVIEW capability for the topaz picker.

The interactive preview-and-retune flow:

  1. :func:`run_preview` — the expensive half: load + preprocess the
     micrograph and run the detector CNN (~40 s). The raw score map is
     cached in a TTLCache; the initial picks + a thumbnail PNG of the
     score map are returned.
  2. :func:`run_retune` — the cheap half: re-run NMS over the cached
     score map with a new threshold / radius. Milliseconds, no CNN.
  3. :func:`discard_preview` — drop the cached score map.

Wire shapes are the SDK's ``PickingPreviewResult`` /
``PickingRetuneRequest`` / ``PickingRetuneResult``.
"""
from __future__ import annotations

import base64
import io
import logging
import uuid
from typing import Optional

import numpy as np
from cachetools import TTLCache

from magellon_sdk.capabilities import (
    PickingPreviewResult,
    PickingRetuneRequest,
    PickingRetuneResult,
)
from magellon_sdk.models.tasks import TopazPickInput

from plugin.compute import compute_score_map, picks_from_score_map

logger = logging.getLogger(__name__)


# A topaz score map for a 7k micrograph at scale=8 is ~900x900 float32
# (~3 MB). 20 entries is generous for interactive use; 10-min TTL mirrors
# CoreService's sticky-route cache so a stale preview_id 404s in sync.
_PREVIEW_TTL_SECONDS = 600
_PREVIEW_MAX_ENTRIES = 20
_previews: TTLCache = TTLCache(maxsize=_PREVIEW_MAX_ENTRIES, ttl=_PREVIEW_TTL_SECONDS)


def _opts(input_data: TopazPickInput) -> dict:
    return input_data.engine_opts or {}


def run_preview(input_data: TopazPickInput) -> PickingPreviewResult:
    """Run the detector once, cache the score map, return initial picks."""
    if not input_data.input_file:
        raise ValueError("topaz preview: input_file is required")

    opts = _opts(input_data)
    model     = str(opts.get("model", "resnet16"))
    radius    = int(opts.get("radius", 14))
    threshold = float(opts.get("threshold", -3.0))
    scale     = int(opts.get("scale", 8))

    score_map, image_shape = compute_score_map(
        input_data.input_file, model=model, scale=scale,
    )

    preview_id = str(uuid.uuid4())
    _previews[preview_id] = {"score_map": score_map, "scale": scale,
                             "image_shape": image_shape}

    picks = picks_from_score_map(
        score_map, radius=radius, threshold=threshold, scale=scale,
    )
    return PickingPreviewResult(
        preview_id=preview_id,
        particles=[
            {"x": p["center"][0], "y": p["center"][1], "score": p["score"]}
            for p in picks
        ],
        num_particles=len(picks),
        num_templates=0,  # topaz is a CNN detector — no templates
        target_pixel_size=float(scale),
        image_binning=scale,
        image_shape=image_shape,
        score_map_png_base64=_score_map_to_base64_png(score_map),
        score_range=[float(np.min(score_map)), float(np.max(score_map))],
    )


def run_retune(
    preview_id: str, params: PickingRetuneRequest,
) -> Optional[PickingRetuneResult]:
    """Re-run NMS over the cached score map. None when preview is gone."""
    preview = _previews.get(preview_id)
    if preview is None:
        return None

    picks = picks_from_score_map(
        preview["score_map"],
        radius=int(params.radius or 14),
        threshold=float(params.threshold),
        scale=preview["scale"],
    )
    return PickingRetuneResult(
        particles=[
            {"x": p["center"][0], "y": p["center"][1], "score": p["score"]}
            for p in picks
        ],
        num_particles=len(picks),
    )


def discard_preview(preview_id: str) -> bool:
    """Drop a cached preview. True on hit, False on miss."""
    return _previews.pop(preview_id, None) is not None


def _score_map_to_base64_png(score_map: np.ndarray) -> str:
    """Compress a 2D float score map into a base64 PNG thumbnail."""
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
