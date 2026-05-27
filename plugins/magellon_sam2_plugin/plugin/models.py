"""Input / output models for the SAM2 particle-picker plugin.

Two call paths:
  * execute / execute_sync  — batch auto-pick using SAM2AutomaticMaskGenerator
  * POST /click-pick        — interactive single-click segmentation

Both share the same image loading and contrast pre-processing.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from magellon_sdk.models.tasks import CryoEmImageInput
from pydantic import BaseModel, ConfigDict, Field


class Sam2PickInput(CryoEmImageInput):
    """Full-image SAM2 auto-picking parameters.

    The automatic mask generator finds every region that looks like a
    distinct object, then the filter chain keeps only mask candidates
    that match expected particle geometry (area, circularity).
    """
    model_config = ConfigDict(extra="allow")

    image_path: str = Field(
        ...,
        description="Absolute path to the micrograph (.mrc / .mrcs / .tif)",
        json_schema_extra={
            "ui_widget": "file_path",
            "ui_group": "Image",
            "ui_order": 1,
            "ui_file_ext": [".mrc", ".mrcs", ".tif", ".tiff"],
            "ui_hidden": True,
        },
    )

    model_variant: str = Field(
        default="facebook/sam2.1-hiera-tiny",
        description="SAM2 model variant (HuggingFace repo ID or local path)",
        json_schema_extra={
            "ui_widget": "select",
            "ui_group": "Model",
            "ui_order": 2,
            "ui_options": [
                "facebook/sam2.1-hiera-tiny",
                "facebook/sam2.1-hiera-small",
                "facebook/sam2.1-hiera-base-plus",
                "facebook/sam2.1-hiera-large",
            ],
            "ui_help": "Larger variants are more accurate but slower. Tiny runs on CPU in ~3s/image.",
        },
    )

    stability_score_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="SAM2 mask stability score threshold",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Auto-picking Settings",
            "ui_order": 10,
            "ui_step": 0.05,
            "ui_tunable": True,
            "ui_help": "Higher = fewer but more stable masks.",
        },
    )

    predicted_iou_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="SAM2 predicted IoU threshold",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Auto-picking Settings",
            "ui_order": 11,
            "ui_step": 0.05,
            "ui_tunable": True,
            "ui_help": "Minimum predicted mask quality. Lower = more picks, potentially noisier.",
        },
    )

    image_pixel_size: float = Field(
        default=1.0,
        gt=0,
        description="Micrograph pixel size (Å/px) — used with diameter bounds to filter masks",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 20,
            "ui_step": 0.1,
            "ui_unit": "Å/px",
        },
    )

    particle_diameter_min_angstrom: float = Field(
        default=100.0,
        gt=0,
        description="Minimum expected particle diameter",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 21,
            "ui_step": 10.0,
            "ui_unit": "Å",
        },
    )

    particle_diameter_max_angstrom: float = Field(
        default=500.0,
        gt=0,
        description="Maximum expected particle diameter",
        json_schema_extra={
            "ui_widget": "number",
            "ui_group": "Auto-picking Settings",
            "ui_order": 22,
            "ui_step": 10.0,
            "ui_unit": "Å",
        },
    )

    min_circularity: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Reject masks less circular than this (0=any, 1=perfect circle)",
        json_schema_extra={
            "ui_widget": "slider",
            "ui_group": "Auto-picking Settings",
            "ui_order": 23,
            "ui_step": 0.05,
            "ui_tunable": True,
            "ui_help": "Filters out elongated debris and carbon edges.",
        },
    )

    output_dir: Optional[str] = Field(
        default=None,
        description="Directory for output artifacts",
        json_schema_extra={"ui_hidden": True},
    )


class ClickPoint(BaseModel):
    x: float = Field(..., description="Horizontal coordinate in image pixels (column)")
    y: float = Field(..., description="Vertical coordinate in image pixels (row)")
    label: int = Field(default=1, description="1 = foreground (include), 0 = background (exclude)")


class ClickPickRequest(BaseModel):
    """Body for the plugin's POST /click-pick endpoint."""
    model_config = ConfigDict(extra="forbid")

    image_path: str
    click_points: List[ClickPoint]
    model_variant: str = "facebook/sam2.1-hiera-tiny"
    mask_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class ClickPickResult(BaseModel):
    """Response from POST /click-pick."""
    centroid_x: float
    centroid_y: float
    mask_polygon: List[List[float]]  # [[x,y], ...] ordered convex hull
    confidence: float                # SAM2 predicted IoU score
    radius_estimate: float           # sqrt(area/π) in pixels
    image_shape: List[int]           # [height, width]


__all__ = [
    "Sam2PickInput",
    "ClickPoint",
    "ClickPickRequest",
    "ClickPickResult",
]
