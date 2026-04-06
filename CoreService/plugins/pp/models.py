"""
Strict Pydantic contracts for all particle-picking backends.

Every pp backend must accept a subclass of ``PPInput`` and return a
subclass of ``PPOutput``.  The base models define the contract that the
controller and any future RabbitMQ integration can rely on.

UI Metadata Convention  (``json_schema_extra`` keys)
----------------------------------------------------

Rendering:
    ui_widget      : str    — "slider" | "number" | "text" | "file_path"
                              | "file_path_list" | "toggle" | "select" | "hidden"
    ui_group       : str    — accordion section heading
    ui_order       : int    — sort key within group (lower = first)

Slider / number:
    ui_step        : float  — increment step
    ui_marks       : list   — [{value, label}, …] tick marks
    ui_unit        : str    — suffix shown after label ("Å", "px", …)

File pickers:
    ui_file_ext    : list   — accepted extensions [".mrc", ".mrcs"]

Visibility:
    ui_hidden      : bool   — never rendered (backend-internal fields)
    ui_advanced    : bool   — collapsed under "Advanced" by default

Help / placeholder:
    ui_placeholder : str    — input placeholder text
    ui_help        : str    — tooltip / inline help (distinct from Field description)

Conditional visibility:
    ui_depends_on  : dict   — {"field_name": value} — only show when condition met
                              e.g. {"invert_templates": true}

Preview / tuning:
    ui_tunable     : bool   — if True, this param can be re-applied without full recompute
                              (used by the preview/retune flow)

Validation hints:
    ui_required_message : str — custom message when required field is empty
"""

from __future__ import annotations

from typing import List, Literal, Optional

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
        description="2D class-average or projection templates for cross-correlation matching",
        json_schema_extra={
            "ui_widget": "file_path_list",
            "ui_group": "Templates",
            "ui_order": 2,
            "ui_file_ext": [".mrc", ".mrcs"],
            "ui_placeholder": "/path/to/template.mrc",
            "ui_help": "Drag and drop .mrc template files, or type server-side paths. "
                       "Multiple templates are matched independently and merged.",
            "ui_required_message": "At least one template is required for auto-picking.",
        },
    )

    # --- Core picking parameters (group: Auto-picking Settings) ---

    diameter_angstrom: float = Field(
        ...,
        gt=0,
        description="Expected particle diameter",
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
            "ui_help": "Approximate diameter of the target particle. "
                       "Controls the correlation mask radius.",
        },
    )

    threshold: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Normalized cross-correlation score cutoff",
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
            "ui_help": "Lower values detect more particles (including noise); "
                       "higher values are more selective.",
            "ui_tunable": True,
        },
    )

    max_peaks: int = Field(
        default=500,
        gt=0,
        description="Maximum number of particles to return",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 8,
            "ui_step": 50,
            "ui_tunable": True,
        },
    )

    max_threshold: Optional[float] = Field(
        default=None,
        description="Upper score filter — reject suspiciously high scores",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 9,
            "ui_advanced": True,
            "ui_help": "Particles scoring above this value are discarded. "
                       "Useful for removing ice crystals or carbon edges.",
            "ui_tunable": True,
        },
    )

    # --- Pixel sizes (group: Auto-picking Settings) ---

    image_pixel_size: float = Field(
        ...,
        gt=0,
        description="Micrograph pixel size",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 10,
            "ui_step": 0.1,
            "ui_unit": "Å/px",
            "ui_help": "Pixel size of the input micrograph after any binning.",
        },
    )

    template_pixel_size: float = Field(
        ...,
        gt=0,
        description="Template pixel size",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 11,
            "ui_step": 0.1,
            "ui_unit": "Å/px",
            "ui_help": "Pixel size of the template images. Templates are "
                       "rescaled to match the micrograph pixel size.",
        },
    )

    # --- Preprocessing (group: Preprocessing) ---

    bin_factor: int = Field(
        default=1,
        ge=1,
        description="Power-of-two downsampling factor applied to the micrograph",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Preprocessing",
            "ui_order": 20,
            "ui_options": [1, 2, 4, 8],
            "ui_help": "Higher binning speeds up picking but reduces accuracy. "
                       "Bin 2 is usually a good trade-off.",
        },
    )

    invert_templates: bool = Field(
        default=False,
        description="Multiply templates by -1 before matching",
        json_schema_extra={
            "ui_widget": "toggle",
            "ui_group": "Preprocessing",
            "ui_order": 21,
            "ui_help": "Enable if your templates have inverted contrast "
                       "(white particles on dark background).",
        },
    )

    lowpass_resolution: Optional[float] = Field(
        default=None,
        gt=0,
        description="Gaussian low-pass filter cutoff",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Preprocessing",
            "ui_order": 22,
            "ui_step": 1.0,
            "ui_unit": "Å",
            "ui_placeholder": "None (disabled)",
            "ui_help": "Apply a Gaussian low-pass filter to micrograph and templates. "
                       "Helps suppress high-frequency noise. Leave empty to disable.",
        },
    )

    # --- Fine-tuning (group: Advanced) ---

    overlap_multiplier: float = Field(
        default=1.0,
        gt=0,
        description="Minimum separation between picks as a fraction of particle radius",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Advanced",
            "ui_order": 30,
            "ui_step": 0.1,
            "ui_advanced": True,
            "ui_tunable": True,
            "ui_help": "1.0 = one radius apart, 1.5 = 1.5 radii apart. "
                       "Increase to reduce overlapping picks.",
        },
    )

    max_blob_size_multiplier: float = Field(
        default=1.0,
        gt=0,
        description="Maximum connected-component area relative to expected particle area",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Advanced",
            "ui_order": 31,
            "ui_step": 0.1,
            "ui_advanced": True,
            "ui_tunable": True,
        },
    )

    min_blob_roundness: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Reject blobs less circular than this (0=any, 1=perfect circle)",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Advanced",
            "ui_order": 32,
            "ui_step": 0.05,
            "ui_advanced": True,
            "ui_tunable": True,
            "ui_help": "Filter out elongated or irregular peaks. "
                       "0 accepts all shapes; 0.5 rejects very irregular ones.",
        },
    )

    peak_position: Literal["maximum", "center"] = Field(
        default="maximum",
        description="How to assign coordinates within a detected blob",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Advanced",
            "ui_order": 33,
            "ui_advanced": True,
            "ui_tunable": True,
            "ui_help": "'maximum' places the pick at the highest-scoring pixel; "
                       "'center' uses the center-of-mass of the blob.",
        },
    )

    angle_ranges: Optional[List[AngleRange]] = Field(
        default=None,
        description="Per-template rotation sweep (start, end, step in degrees)",
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


# ---------------------------------------------------------------------------
# Preview / retune models
# ---------------------------------------------------------------------------

class PreviewResult(BaseModel):
    """Returned by the preview endpoint after the expensive computation."""
    preview_id: str
    particles: List[ParticlePick]
    num_particles: int
    num_templates: int
    target_pixel_size: float
    image_binning: int
    score_map_png_base64: Optional[str] = None  # base64-encoded PNG of merged score map
    score_range: Optional[List[float]] = None    # [min, max] of score values


class RetuneRequest(BaseModel):
    """Tunable parameters sent to the retune endpoint."""
    model_config = ConfigDict(extra="forbid")

    threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    max_threshold: Optional[float] = None
    max_peaks: int = Field(default=500, gt=0)
    overlap_multiplier: float = Field(default=1.0, gt=0)
    max_blob_size_multiplier: float = Field(default=1.0, gt=0)
    min_blob_roundness: float = Field(default=0.0, ge=0.0, le=1.0)
    peak_position: Literal["maximum", "center"] = "maximum"


class RetuneResult(BaseModel):
    """Returned by the retune endpoint — just particles, no maps."""
    particles: List[ParticlePick]
    num_particles: int
