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
    CryoEmImageTaskData,
    CryoEmMotionCorTaskData,
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
    MotioncorTask,
    MrcToPngTaskData,
    OutputFile,
    PARTICLE_PICKING,
    PENDING,
    TWO_D_CLASSIFICATION,
    TaskBase,
    TaskCategory,
    TaskDto,
    TaskOutcome,
    TaskResultDto,
    TaskStatus,
    TaskStatusEnum,
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
    # tasks.py — envelope.
    "TaskBase",
    "TaskCategory",
    "TaskDto",
    "JobDto",
    "TaskOutcome",
    "TaskStatus",
    "TaskStatusEnum",
    # tasks.py — data.
    "CryoEmImageTaskData",
    "MrcToPngTaskData",
    "FftTaskData",
    "CtfTaskData",
    "CryoEmMotionCorTaskData",
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
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    # tasks.py — result/debug.
    "ImageMetaData",
    "OutputFile",
    "TaskResultDto",
    "DebugInfo",
]
