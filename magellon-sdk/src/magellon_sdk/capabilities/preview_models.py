"""Wire shapes for the PREVIEW capability (PT-2, 2026-05-04).

The interactive preview-and-retune flow has two phases:

  1. **Preview** — expensive: load image, compute correlation maps,
     cache them in memory, return the initial picks plus a
     thumbnail score-map PNG. This is the slow phase (~hundreds of
     ms to seconds depending on image size).

  2. **Retune** — cheap: re-threshold the cached score maps with
     new tunable params. Sub-100ms. No recomputation.

Both shapes here are picker-specific (designed around the FFT
template-matching picker that's the canonical PARTICLE_PICKING
backend today). A future category that wants its own preview flow
defines its own models and points its CategoryContract at them.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _PickedParticle(BaseModel):
    """One particle returned from the preview / retune endpoints.

    Coordinates are in original-image pixels (after the picker's
    binning step has been undone). Score is engine-specific.
    """

    model_config = ConfigDict(extra="allow")

    x: int
    y: int
    score: float


class PickingPreviewResult(BaseModel):
    """Returned by ``POST /preview`` after the expensive computation.

    Carries enough state for the React preview UX to render an
    overlay AND to make subsequent retune calls work — the
    ``preview_id`` is the cache key the plugin uses to find the
    cached score maps without recomputing.
    """

    preview_id: str
    """Opaque token. Pass back to ``/preview/{preview_id}/retune``
    or ``DELETE /preview/{preview_id}`` to act on the same cached
    score maps."""

    particles: List[_PickedParticle]
    num_particles: int
    num_templates: int
    target_pixel_size: float
    image_binning: int
    image_shape: Optional[List[int]] = None
    """``[height, width]`` of the binned image. None when the
    plugin didn't bin (binning_factor=1)."""

    score_map_png_base64: Optional[str] = None
    """Base64-encoded PNG thumbnail of the merged score map.
    Optional — pickers that don't materialize a visualizable map
    skip this."""

    score_range: Optional[List[float]] = None
    """``[min, max]`` of raw score values. Lets the React UI map
    threshold slider positions to score values without re-running
    statistics on the PNG."""


class PickingRetuneRequest(BaseModel):
    """Tunable params for ``POST /preview/{id}/retune``.

    Same shape every retune call sees. Plugins that don't support
    one of the fields ignore it; values silently round-trip on
    successive calls.
    """

    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    max_threshold: Optional[float] = None
    max_peaks: int = Field(default=500, gt=0)
    overlap_multiplier: float = Field(default=1.0, gt=0)
    max_blob_size_multiplier: float = Field(default=1.0, gt=0)
    min_blob_roundness: float = Field(default=0.0, ge=0.0, le=1.0)
    peak_position: Literal["maximum", "center"] = "maximum"


class PickingRetuneResult(BaseModel):
    """Returned by ``POST /preview/{id}/retune``.

    Just the new particle list — the score maps are still cached
    so the next retune is also cheap. ``image_shape`` and the PNG
    thumbnail don't change between retunes; consumers reuse the
    values from the original :class:`PickingPreviewResult`.
    """

    particles: List[_PickedParticle]
    num_particles: int
