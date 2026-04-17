"""MotionCor-only DTO shapes.

Everything else this plugin needs (TaskDto, TaskResultDto,
CryoEmMotionCorTaskData, etc.) lives in :mod:`magellon_sdk.models` —
import from there directly.
"""
from typing import List

from pydantic import BaseModel


class CreateFrameAlignRequest(BaseModel):
    """Request payload for the frame-align HTTP endpoint (motioncor-only)."""

    outputmrcpath: str
    data: list
    directory_path: str
    originalsize: list
