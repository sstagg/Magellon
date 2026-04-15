"""Compatibility shim — re-exports canonical DTOs and adds motioncor-only shapes."""
from typing import List

from pydantic import BaseModel

from magellon_sdk.models import (  # noqa: F401
    COMPLETED,
    CTF_TASK,
    CheckRequirementsResult,
    CryoEmImageTaskData,
    CryoEmMotionCorTaskData,
    DebugInfo,
    FAILED,
    FFT_TASK,
    FftTask,
    FftTaskData,
    IN_PROGRESS,
    ImageMetaData,
    JobDto,
    MOTIONCOR,
    MotioncorTask,
    MrcToPngTaskData,
    OutputFile,
    PARTICLE_PICKING,
    PENDING,
    PluginInfo,
    PluginInfoSingleton,
    RecuirementResultEnum,
    RequirementResult,
    TWO_D_CLASSIFICATION,
    TaskBase,
    TaskCategory,
    TaskDto,
    TaskOutcome,
    TaskResultDto,
    TaskStatus,
    TaskStatusEnum,
)


class CreateFrameAlignRequest(BaseModel):
    """Request payload for the frame-align HTTP endpoint (motioncor-only)."""

    outputmrcpath: str
    data: list
    directory_path: str
    originalsize: list
