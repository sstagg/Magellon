"""
Strict Pydantic contracts for all particle-picking backends.

Every pp backend must accept a subclass of ``PPInput`` and return a
subclass of ``PPOutput``.  The base models define the contract that the
controller and any future RabbitMQ integration can rely on.

UI Metadata Convention
----------------------
Each Field can carry ``json_schema_extra`` with these keys:

    ui_widget   : str   — "slider" | "number" | "text" | "file_path"
                          | "file_path_list" | "toggle" | "select" | "hidden"
    ui_group    : str   — section heading in the settings panel
    ui_order    : int   — sort key within the group (lower = higher)
    ui_marks    : list  — slider mark labels  [{"value": 0.3, "label": "Low"}, ...]
    ui_step     : float — slider/number step size
    ui_unit     : str   — display unit suffix ("Å", "px", …)
    ui_advanced : bool  — if True, collapsed under "Advanced" by default
    ui_hidden   : bool  — if True, not shown in the UI at all
    ui_file_ext : list  — accepted file extensions for file pickers [".mrc", ".mrcs"]
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

    # --- Files (group: Templates) ---

    image_path: str = Field(
        ...,
        description="Absolute path to micrograph .mrc file",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Templates",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".mrcs", ".tif", ".tiff"],
            "ui_hidden": True,  # auto-filled from selected image
        },
    )

    template_paths: List[str] = Field(
        ...,
        min_length=1,
        description="Paths to template .mrc files",
        json_schema_extra={
            "ui_widget": "file_path_list",
            "ui_group": "Templates",
            "ui_order": 2,
            "ui_file_ext": [".mrc", ".mrcs"],
        },
    )

    # --- Pixel sizes (group: Auto-picking Settings) ---

    image_pixel_size: float = Field(
        ...,
        gt=0,
        description="Micrograph pixel size in Angstrom",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 10,
            "ui_step": 0.1,
            "ui_unit": "Å/px",
        },
    )

    template_pixel_size: float = Field(
        ...,
        gt=0,
        description="Template pixel size in Angstrom",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 11,
            "ui_step": 0.1,
            "ui_unit": "Å/px",
        },
    )

    # --- Core picking parameters (group: Auto-picking Settings) ---

    diameter_angstrom: float = Field(
        ...,
        gt=0,
        description="Expected particle diameter in Angstrom",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Auto-picking Settings",
            "ui_order": 5,
            "ui_step": 5,
            "ui_unit": "Å",
            "ui_marks": [
                {"value": 50, "label": "50"},
                {"value": 200, "label": "200"},
                {"value": 500, "label": "500"},
            ],
        },
    )

    threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Correlation score threshold",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Auto-picking Settings",
            "ui_order": 6,
            "ui_step": 0.05,
            "ui_marks": [
                {"value": 0.2, "label": "Low"},
                {"value": 0.5, "label": "Medium"},
                {"value": 0.8, "label": "High"},
            ],
        },
    )

    max_threshold: Optional[float] = Field(
        default=None,
        description="Upper score filter",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 7,
            "ui_advanced": True,
        },
    )

    max_peaks: int = Field(
        default=500,
        gt=0,
        description="Maximum particles to return",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 8,
            "ui_step": 50,
        },
    )

    # --- Preprocessing (group: Preprocessing) ---

    bin_factor: int = Field(
        default=1,
        ge=1,
        description="Power-of-two binning factor",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Preprocessing",
            "ui_order": 20,
            "ui_options": [1, 2, 4, 8],
        },
    )

    invert_templates: bool = Field(
        default=False,
        description="Invert template contrast",
        json_schema_extra={
            "ui_widget": "toggle",
            "ui_group": "Preprocessing",
            "ui_order": 21,
        },
    )

    lowpass_resolution: Optional[float] = Field(
        default=None,
        gt=0,
        description="Low-pass filter resolution in Angstrom",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Preprocessing",
            "ui_order": 22,
            "ui_step": 1.0,
            "ui_unit": "Å",
        },
    )

    # --- Fine-tuning (group: Advanced) ---

    overlap_multiplier: float = Field(
        default=1.0,
        gt=0,
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Advanced",
            "ui_order": 30,
            "ui_step": 0.1,
            "ui_advanced": True,
        },
    )

    max_blob_size_multiplier: float = Field(
        default=1.0,
        gt=0,
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Advanced",
            "ui_order": 31,
            "ui_step": 0.1,
            "ui_advanced": True,
        },
    )

    min_blob_roundness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Advanced",
            "ui_order": 32,
            "ui_step": 0.05,
            "ui_advanced": True,
        },
    )

    peak_position: Literal["maximum", "center"] = Field(
        default="maximum",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Advanced",
            "ui_order": 33,
            "ui_advanced": True,
        },
    )

    angle_ranges: Optional[List[AngleRange]] = Field(
        default=None,
        description="Per-template rotation sweep; if None, defaults to 0-360/10 for each",
        json_schema_extra={
            "ui_widget": "hidden",
            "ui_group": "Advanced",
            "ui_order": 34,
            "ui_advanced": True,
        },
    )

    # --- Output (hidden from UI) ---

    output_dir: Optional[str] = Field(
        default=None,
        description="Directory to write result artifacts",
        json_schema_extra={
            "ui_hidden": True,
        },
    )


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
