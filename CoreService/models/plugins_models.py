"""Compatibility shim — plugin-contract DTOs now live in ``magellon_sdk.models``.

Every shape this module used to declare is re-exported from the SDK so
existing CoreService call sites (``from models.plugins_models import
TaskDto, …``) keep working without edits.

SDK 1.3 renamed wire-shape classes (``TaskDto`` → ``TaskMessage``,
``CtfTaskData`` → ``CtfInput``, etc.). Both names are exported here so
the migration can proceed file-by-file. The old names will be removed
in SDK 2.0 alongside the X.3 alias drop.

``MOTIONCOR_TASK`` was CoreService's historical name for the task-type
constant; plugins use ``MOTIONCOR``. The alias below preserves the
CoreService spelling.
"""
from magellon_sdk.models import (  # noqa: F401
    COMPLETED,
    CTF_TASK,
    CheckRequirementsResult,
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
    PluginInfo,
    PluginInfoSingleton,
    PluginStatus,
    PtolemyInput,
    PtolemyTaskData,
    RecuirementResultEnum,
    RequirementResult,
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

# CoreService's legacy name for the motioncor task-type constant.
MOTIONCOR_TASK = MOTIONCOR
