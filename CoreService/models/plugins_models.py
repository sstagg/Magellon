"""Compatibility shim — plugin-contract DTOs now live in ``magellon_sdk.models``.

Every shape this module used to declare is re-exported from the SDK so
existing CoreService call sites (``from models.plugins_models import
TaskDto, …``) keep working without edits.

``MOTIONCOR_TASK`` was CoreService's historical name for the task-type
constant; plugins use ``MOTIONCOR``. The alias below preserves the
CoreService spelling.
"""
from magellon_sdk.models import (  # noqa: F401
    COMPLETED,
    CTF_TASK,
    CheckRequirementsResult,
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
    PluginInfo,
    PluginInfoSingleton,
    PluginStatus,
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

# CoreService's legacy name for the motioncor task-type constant.
MOTIONCOR_TASK = MOTIONCOR
