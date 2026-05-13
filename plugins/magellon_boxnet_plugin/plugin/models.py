"""Plugin-owned input model for the BoxNet picker.

PE2-UI (2026-05-12): the plugin announces its own rich JSON schema via
:class:`Announce.input_schema`. The runner page reads the schema and
renders sliders / file pickers / accordion groups; the runner consumes
the same shape via the SDK's ``cls.input_schema()`` hook.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class BoxnetPickerInput(BaseModel):
    """Inputs for the external BoxNet CNN picker.

    Required: just ``image_path``. The rest have defaults tuned to
    Warp's training regime (~8 Å/pixel, threshold ~0.3 on the particle
    channel).
    """
    model_config = ConfigDict(extra="forbid")

    # --- Files (group: Image) ---

    image_path: str = Field(
        ...,
        description="Absolute path to micrograph .mrc file",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Image",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".mrcs", ".tif", ".tiff"],
            "ui_hidden": True,
        },
    )

    # --- Core picking parameters (group: Auto-picking Settings) ---

    threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Particle-channel probability cutoff",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Auto-picking Settings",
            "ui_order": 5,
            "ui_step": 0.05,
            "ui_marks": [
                {"value": 0.2, "label": "Low"},
                {"value": 0.5, "label": "Medium"},
                {"value": 0.8, "label": "High"},
            ],
            "ui_help": "BoxNet softmax probability that a pixel belongs "
                       "to the particle class. Lower values detect more "
                       "candidates (including noise).",
            "ui_tunable": True,
        },
    )

    min_distance: int = Field(
        default=14,
        ge=1,
        description="Minimum centre-to-centre spacing in preprocessed pixels",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 6,
            "ui_step": 1,
            "ui_help": "Local-maxima NMS radius. Roughly half the "
                       "particle diameter in downsampled (preprocessed) "
                       "pixels.",
            "ui_tunable": True,
        },
    )

    # --- Preprocessing (group: Preprocessing) ---

    scale: int = Field(
        default=8,
        ge=1,
        description="Downsample factor on input",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Preprocessing",
            "ui_order": 20,
            "ui_options": [1, 2, 4, 8],
            "ui_help": "BoxNet was trained at ~8 Å/pixel; a 1 Å/pixel "
                       "micrograph needs scale=8. PNG-derived test "
                       "fixtures already at training resolution use 1.",
        },
    )

    # --- Advanced ---

    device: Literal["auto", "cpu", "cuda"] = Field(
        default="auto",
        description="Inference device",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Advanced",
            "ui_order": 30,
            "ui_advanced": True,
        },
    )

    # --- Output (hidden from UI) ---

    output_dir: Optional[str] = Field(
        default=None,
        description="Directory to write particles.json (default: next to image)",
        json_schema_extra={
            "ui_hidden": True,
        },
    )


__all__ = ["BoxnetPickerInput"]
