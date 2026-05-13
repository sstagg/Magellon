"""Plugin-owned input model for the template-picker.

The plugin is the source of truth for its UI form schema (PE2-UI,
2026-05-12). Lifted from CoreService's
``services/particle_picking/models.py`` so the plugin can announce its
own rich JSON schema (sliders, file pickers, accordion groups) via
:class:`Announce.input_schema` — the generic plugin runner page at
``/en/panel/plugins/<id>`` then renders the proper picker form
instead of the bare ``CryoEmImageInput`` 4-field shape.

CoreService keeps its own near-identical ``TemplatePickerInput`` for
``/particle-picking/preview`` server-side validation — that copy is a
deliberate fallback so the React side panel (image-viewer flow) keeps
working even when the plugin isn't live yet. The two definitions
agree on JSON shape; they don't share Python code by design (avoids
CoreService → plugin Python import).

See ``services/particle_picking/models.py`` in CoreService and the
``ui_*`` metadata convention documented at the top of that file.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from magellon_sdk.models.tasks import CryoEmImageInput
from pydantic import BaseModel, ConfigDict, Field


class AngleRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: float = 0.0
    end: float = 360.0
    step: float = 10.0


class TemplatePickerInput(CryoEmImageInput):
    """Rich input model for the template-picker plugin.

    Carries every parameter the algorithm needs as a typed field, so
    the JSON schema published in :class:`Announce.input_schema`
    renders as a real form (not an opaque ``engine_opts`` blob). The
    runner consumes this directly via the SDK's
    ``cls.input_schema()`` hook.

    Inherits from ``CryoEmImageInput`` (2026-05-13) so the SDK
    category dispatcher's ``CryoEmImageInput.model_validate(body)``
    preserves this plugin's extras AND the runtime re-validation
    against ``TemplatePickerInput`` accepts the inherited
    ``image_id`` / ``image_name`` / ``engine_opts`` fields the
    dispatcher injects. Pre-inheritance the plugin used
    ``BaseModel`` + ``extra='forbid'`` and rejected the dispatcher's
    base fields on the wire (3 ValidationError extras).
    """
    # extra='forbid' is fine now that we inherit the base fields —
    # every wire field is declared (either by parent or by this
    # subclass). Any genuinely unknown extra is still a contract
    # violation worth surfacing.
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
        default=[
            "/gpfs/templates/origTemplate1.mrc",
            "/gpfs/templates/origTemplate2.mrc",
            "/gpfs/templates/origTemplate3.mrc",
        ],
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
        default=220.0,
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
        default=0.35,
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
        default=3.16,
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
        default=2.646,
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
        default=True,
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


__all__ = ["AngleRange", "TemplatePickerInput"]
