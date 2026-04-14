"""Pydantic contracts for the MotionCor plugin family."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class MotionCorInput(BaseModel):
    """Inputs for motion correction of a single movie (TIFF/MRC/EER).

    Matches the common subset of MotionCor2 options that every dataset needs.
    Omitted flags can be added as this plugin matures; anything non-canonical
    should live in `extra_args` rather than grow the schema.
    """
    movie_path: str = Field(..., description="Absolute path to the input movie (MRC/TIFF/EER).")
    output_dir: str = Field(..., description="Directory where MotionCor writes artifacts.")

    pixel_size: float = Field(..., gt=0, description="Physical pixel size in Å/pixel")
    dose_per_frame: float = Field(..., gt=0, description="Electron dose per frame (e-/Å²)")
    voltage_kv: float = Field(300.0, description="Acceleration voltage (kV)")

    gain_reference_path: Optional[str] = Field(None, description="Gain reference (MRC or DM4).")
    rotate_gain: int = Field(0, ge=0, le=3, description="Rotations of the gain ref (0, 1, 2, 3 * 90°)")
    flip_gain: int = Field(0, ge=0, le=2, description="0=none, 1=vertical, 2=horizontal")

    ft_bin: float = Field(1.0, gt=0, description="Fourier-binning factor for the output")
    patch_rows: int = Field(5, ge=1)
    patch_cols: int = Field(5, ge=1)
    iterations: int = Field(10, ge=1)
    b_factor_global: int = Field(500, description="Global B-factor")
    b_factor_local: int = Field(100, description="Local B-factor")

    gpu_ids: str = Field("0", description="GPU IDs, space-separated (e.g. '0 1')")

    extra_args: List[str] = Field(
        default_factory=list,
        description="Extra raw MotionCor2 flags to append verbatim (escape hatch).",
    )


class DriftSample(BaseModel):
    """One x/y drift value at a frame boundary (pixels)."""
    frame: int
    dx: float
    dy: float


class MotionCorResultSummary(BaseModel):
    total_drift_pixels: float = Field(..., description="Cumulative drift magnitude (pixels)")
    max_frame_drift_pixels: float = Field(..., description="Largest single-frame drift (pixels)")
    num_frames: int


class MotionCorOutput(BaseModel):
    aligned_mrc_path: str = Field(..., description="Absolute path to the motion-corrected micrograph (MRC)")
    log_path: Optional[str] = Field(None, description="Absolute path to the MotionCor log")
    drift: List[DriftSample] = Field(default_factory=list)
    summary: MotionCorResultSummary
