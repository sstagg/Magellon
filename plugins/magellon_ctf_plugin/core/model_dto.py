"""Compatibility shim — re-exports canonical task/plugin DTOs from the SDK.

All of the shapes this plugin used to declare locally live in
``magellon_sdk.models`` now. Existing call sites keep working unchanged.
"""
from magellon_sdk.models import (  # noqa: F401
    COMPLETED,
    CTF_TASK,
    CheckRequirementsResult,
    CryoEmImageTaskData,
    CtfTask,
    CtfTaskData,
    DebugInfo,
    FAILED,
    FFT_TASK,
    FftTask,
    FftTaskData,
    IN_PROGRESS,
    ImageMetaData,
    JobDto,
    MOTIONCOR,
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
