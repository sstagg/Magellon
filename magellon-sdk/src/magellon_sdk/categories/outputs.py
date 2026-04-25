"""Canonical output shapes per category.

A plugin's ``execute()`` must return at least the fields its
category declares — the DB projection relies on those. A plugin may
also populate ``extras`` with plugin-specific data that the generic
projection preserves as an opaque blob; specialized consumers can
read it if they know what to look for.

This is the covariant half of the substitutability contract:

    ctffind returns {defocus_u, defocus_v, cc, resolution_limit}
    gctf    returns {defocus_u, defocus_v, cc, resolution_limit,
                     extras={"per_tile_variance": [...], ...}}

Both fit the same slot; the richer one just offers more to anyone
willing to read it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CategoryOutput(BaseModel):
    """Base for every category's canonical output shape.

    ``extras`` is the escape hatch for plugin-specific fields —
    generic consumers (the DB projector) ignore it; specialized
    consumers read it by key.
    """

    extras: Dict[str, Any] = Field(default_factory=dict)


class FftOutput(CategoryOutput):
    """FFT result: path to the rendered PNG and source reference."""

    output_path: str
    source_image_path: Optional[str] = None


class CtfOutput(CategoryOutput):
    """CTF estimation result — every CTF engine must produce these."""

    defocus_u: float
    defocus_v: float
    astigmatism_angle: float
    cc: float
    resolution_limit: float
    additional_phase_shift: Optional[float] = None
    # The raw artifact on disk (star / txt). Optional because not
    # every engine persists one.
    artifact_path: Optional[str] = None
    diagnostic_image_path: Optional[str] = None


class MotionCorOutput(CategoryOutput):
    """Motion-correction result: the aligned movie + drift summary."""

    aligned_mrc_path: str
    log_path: Optional[str] = None
    total_drift_pixels: float
    max_frame_drift_pixels: float
    num_frames: int


class Detection(BaseModel):
    """One square or hole, as returned by ptolemy.

    Coordinate frame: the image's own pixel grid, in ptolemy's
    (axis0, axis1) order — i.e. ``as_matrix_y()`` layout. Consumers
    that need (x, y) for drawing use ``(v[0], v[1])`` directly.
    """

    vertices: List[List[float]]
    center: List[int]
    area: float
    score: float
    brightness: Optional[float] = None  # square only (low-mag proxy for ice quality)


class SquareDetectionOutput(CategoryOutput):
    """Low-mag result: ranked squares (highest score first)."""

    detections: List[Detection]
    detections_json_path: Optional[str] = None
    annotated_png_path: Optional[str] = None


class HoleDetectionOutput(CategoryOutput):
    """Med-mag result: ranked holes (highest score first)."""

    detections: List[Detection]
    detections_json_path: Optional[str] = None
    annotated_png_path: Optional[str] = None


class Particle(BaseModel):
    """One picked particle, in original-image pixel coordinates.

    ``radius`` is in pixels — the NMS radius the picker enforced (or the
    box size convention the picker uses). Score is engine-specific (Topaz
    emits log-likelihood; higher = better). Picker plugins that don't
    know a meaningful radius should set it to 0.
    """

    center: List[int]
    radius: int
    score: float


class ParticlePickingOutput(CategoryOutput):
    """Particle-picking result: particle count + artifact locations.

    Two output channels:
      * ``particles_json_path`` — always written; canonical artifact a
        downstream tool (CryoSPARC, RELION) reads.
      * ``picks`` — optional inline list. Picker plugins that emit small
        result sets (<5k typical) populate this so consumers can render
        the overlay without a second file fetch. Pickers that emit huge
        result sets MAY leave it empty and force readers to consult the
        json file.
    """

    num_particles: int
    particles_csv_path: Optional[str] = None
    particles_json_path: Optional[str] = None
    # Shape as a two-element list (rows, cols); list keeps pydantic
    # happy without a separate tuple type.
    image_shape: Optional[List[int]] = None
    picks: Optional[List[Particle]] = None


class MicrographDenoisingOutput(CategoryOutput):
    """Denoise result: path to the cleaned MRC + intensity stats."""

    output_path: str
    source_image_path: Optional[str] = None
    model: Optional[str] = None
    image_shape: Optional[List[int]] = None
    pixel_min: Optional[float] = None
    pixel_max: Optional[float] = None
    pixel_mean: Optional[float] = None
    pixel_std: Optional[float] = None


__all__ = [
    "CategoryOutput",
    "FftOutput",
    "CtfOutput",
    "MotionCorOutput",
    "ParticlePickingOutput",
    "Detection",
    "SquareDetectionOutput",
    "HoleDetectionOutput",
    "Particle",
    "MicrographDenoisingOutput",
]
