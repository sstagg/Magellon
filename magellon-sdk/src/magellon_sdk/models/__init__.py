"""Canonical plugin-contract types.

Organized into submodules so the surface area stays navigable:

- :mod:`.plugin` — plugin identity, lifecycle, requirement checks
- :mod:`.tasks`  — task envelope, task-data DTOs, result shapes, constants

Everything exported from either submodule is re-exported here, so
``from magellon_sdk.models import PluginInfo, TaskDto`` keeps working.
"""
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    PluginManifest,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.plugin import (
    CheckRequirementsResult,
    PluginInfo,
    PluginInfoSingleton,
    PluginStatus,
    RecuirementResultEnum,
    RequirementResult,
)
from magellon_sdk.models.tasks import (
    COMPLETED,
    CTF_TASK,
    CryoEmImageInput,
    CryoEmImageTaskData,
    CryoEmMotionCorTaskData,
    CtfInput,
    CtfTask,
    CtfTaskData,
    DebugInfo,
    FAILED,
    FFT_TASK,
    FftInput,
    FftTask,
    FftTaskData,
    IN_PROGRESS,
    ImageMetaData,
    JobDto,
    JobMessage,
    MICROGRAPH_DENOISING,
    MOTIONCOR,
    MicrographDenoiseInput,
    MicrographDenoiseTaskData,
    MotionCorInput,
    MotioncorTask,
    MrcToPngInput,
    MrcToPngTaskData,
    OutputFile,
    PARTICLE_PICKING,
    PENDING,
    PtolemyInput,
    PtolemyTaskData,
    TWO_D_CLASSIFICATION,
    TaskBase,
    TaskCategory,
    TaskDto,
    TaskMessage,
    TaskOutcome,
    TaskResultDto,
    TaskResultMessage,
    TaskStatus,
    TaskStatusEnum,
    TopazPickInput,
    TopazPickTaskData,
)

__all__ = [
    # manifest.py — capability-aware plugin description.
    "Capability",
    "IsolationLevel",
    "PluginManifest",
    "ResourceHints",
    "Transport",
    # plugin.py.
    "CheckRequirementsResult",
    "PluginInfo",
    "PluginInfoSingleton",
    "PluginStatus",
    "RecuirementResultEnum",
    "RequirementResult",
    # tasks.py — envelope (SDK 1.3+ canonical names).
    "TaskBase",
    "TaskCategory",
    "TaskMessage",
    "JobMessage",
    "TaskOutcome",
    "TaskStatus",
    "TaskStatusEnum",
    # tasks.py — envelope legacy aliases.
    "TaskDto",
    "JobDto",
    # tasks.py — input shapes (SDK 1.3+ canonical names).
    "CryoEmImageInput",
    "MrcToPngInput",
    "FftInput",
    "CtfInput",
    "MotionCorInput",
    "TopazPickInput",
    "MicrographDenoiseInput",
    "PtolemyInput",
    # tasks.py — input shapes legacy aliases.
    "CryoEmImageTaskData",
    "MrcToPngTaskData",
    "FftTaskData",
    "CtfTaskData",
    "CryoEmMotionCorTaskData",
    "TopazPickTaskData",
    "MicrographDenoiseTaskData",
    "PtolemyTaskData",
    # tasks.py — concrete tasks.
    "FftTask",
    "CtfTask",
    "MotioncorTask",
    # tasks.py — constants.
    "FFT_TASK",
    "CTF_TASK",
    "PARTICLE_PICKING",
    "TWO_D_CLASSIFICATION",
    "MOTIONCOR",
    "MICROGRAPH_DENOISING",
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    # tasks.py — result/debug.
    "ImageMetaData",
    "OutputFile",
    "TaskResultMessage",
    "TaskResultDto",
    "DebugInfo",
]
