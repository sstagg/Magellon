"""
Strict Pydantic contracts for all particle-picking backends.

Every pp backend must accept a subclass of ``PPInput`` and return a
subclass of ``PPOutput``.  The base models define the contract that the
controller and any future RabbitMQ integration can rely on.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared particle representation
# ---------------------------------------------------------------------------

class ParticlePick(BaseModel):
    """Single detected particle — common across all pp backends."""
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int
    score: float
    stddev: float = 0.0
    area: int = 0
    roundness: float = 0.0
    template_index: int = 1
    angle: float = 0.0
    label: str = ""


# ---------------------------------------------------------------------------
# Template-picker specific input / output
# ---------------------------------------------------------------------------

class AngleRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: float = 0.0
    end: float = 360.0
    step: float = 10.0


class TemplatePickerInput(BaseModel):
    """
    Everything needed to run a single template-picking job.

    File paths point to MRC files on disk.  The service layer loads them
    into numpy arrays before calling the algorithm.
    """
    model_config = ConfigDict(extra="forbid")

    # Required file references
    image_path: str = Field(..., description="Absolute path to micrograph .mrc file")
    template_paths: List[str] = Field(..., min_length=1, description="Paths to template .mrc files")

    # Pixel sizes
    image_pixel_size: float = Field(..., gt=0, description="Micrograph pixel size in Angstrom")
    template_pixel_size: float = Field(..., gt=0, description="Template pixel size in Angstrom")

    # Core picking parameters
    diameter_angstrom: float = Field(..., gt=0, description="Expected particle diameter in Angstrom")
    threshold: float = Field(default=0.4, ge=0.0, le=1.0, description="Correlation score threshold")
    max_threshold: Optional[float] = Field(default=None, description="Upper score filter")
    max_peaks: int = Field(default=500, gt=0, description="Maximum particles to return")

    # Preprocessing
    bin_factor: int = Field(default=1, ge=1, description="Power-of-two binning factor")
    invert_templates: bool = Field(default=False, description="Invert template contrast")
    lowpass_resolution: Optional[float] = Field(default=None, gt=0, description="Low-pass filter resolution in Angstrom")

    # Fine-tuning
    overlap_multiplier: float = Field(default=1.0, gt=0)
    max_blob_size_multiplier: float = Field(default=1.0, gt=0)
    min_blob_roundness: float = Field(default=0.0, ge=0.0, le=1.0)
    peak_position: Literal["maximum", "center"] = "maximum"
    angle_ranges: Optional[List[AngleRange]] = Field(
        default=None,
        description="Per-template rotation sweep; if None, defaults to 0-360/10 for each",
    )

    # Optional output
    output_dir: Optional[str] = Field(default=None, description="Directory to write result artifacts")


class TemplatePickerOutput(BaseModel):
    """Validated output returned by the template-picker backend."""
    model_config = ConfigDict(extra="forbid")

    particles: List[ParticlePick]
    num_particles: int
    num_templates: int
    target_pixel_size: float
    image_binning: int

    # Optional artifact paths (populated when output_dir is given)
    particles_csv_path: Optional[str] = None
    particles_json_path: Optional[str] = None
    overlay_png_path: Optional[str] = None
    score_map_png_path: Optional[str] = None
    summary: Optional[dict] = None
