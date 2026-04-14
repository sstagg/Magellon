"""Pydantic contracts for the CTF-estimation plugin family."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class CtfEstimationInput(BaseModel):
    """Inputs for one-image CTF estimation using ctffind4.

    Paths are absolute. Numeric units follow ctffind4's conventions:
    pixel size in Å/pixel, defocus in Å, voltage in kV, Cs in mm, phase
    shift in degrees (the plugin converts to radians on the command line
    when needed).
    """
    image_path: str = Field(..., description="Absolute path to the micrograph (MRC).")
    output_dir: str = Field(..., description="Directory where ctffind writes its artifacts.")

    pixel_size: float = Field(..., gt=0, description="Pixel size in Å/pixel")
    acceleration_voltage: float = Field(300.0, description="Beam voltage (kV)")
    spherical_aberration: float = Field(2.7, description="Cs (mm)")
    amplitude_contrast: float = Field(0.07, ge=0, le=1)

    box_size: int = Field(512, gt=0, description="Power-spectrum box size (pixels)")
    min_resolution: float = Field(30.0, gt=0, description="Å")
    max_resolution: float = Field(5.0, gt=0, description="Å")

    min_defocus: float = Field(5000.0, description="Å")
    max_defocus: float = Field(50000.0, description="Å")
    defocus_step: float = Field(100.0, description="Å")

    find_additional_phase_shift: bool = False


class CtfEstimationResult(BaseModel):
    """Parsed output of ctffind4 for a single micrograph."""
    defocus_u: float = Field(..., description="Å — major axis defocus")
    defocus_v: float = Field(..., description="Å — minor axis defocus")
    astigmatism_angle: float = Field(..., description="Degrees")
    additional_phase_shift: Optional[float] = Field(None, description="Radians")
    cc: float = Field(..., description="Cross correlation of best fit")
    resolution_limit: float = Field(..., description="Å — fit extent")


class CtfEstimationOutput(BaseModel):
    result: CtfEstimationResult
    star_path: str = Field(..., description="Absolute path to ctffind .txt / .star output")
    diagnostic_image_path: Optional[str] = Field(None, description="Absolute path to diagnostic MRC (power spectrum)")
    raw_lines: List[str] = Field(default_factory=list, description="Raw stdout for debugging")
