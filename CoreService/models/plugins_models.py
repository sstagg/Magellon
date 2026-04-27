"""Compatibility shim — plugin-contract DTOs live in ``magellon_sdk.models``.

Every shape this module used to declare is re-exported from the SDK so
existing CoreService call sites (``from models.plugins_models import
TaskMessage, …``) keep working without edits.

``MOTIONCOR_TASK`` is CoreService's historical name for the task-type
constant; plugins use ``MOTIONCOR``. The alias below preserves the
CoreService spelling.
"""
from magellon_sdk.models import (  # noqa: F401
    COMPLETED,
    CTF_TASK,
    CheckRequirementsResult,
    CryoEmImageInput,
    CtfInput,
    CtfTask,
    DebugInfo,
    FAILED,
    FFT_TASK,
    FftInput,
    FftTask,
    IN_PROGRESS,
    ImageMetaData,
    JobMessage,
    MICROGRAPH_DENOISING,
    MOTIONCOR,
    MicrographDenoiseInput,
    MotionCorInput,
    MotioncorTask,
    MrcToPngInput,
    OutputFile,
    PARTICLE_PICKING,
    PENDING,
    PluginInfo,
    PluginInfoSingleton,
    PluginStatus,
    PtolemyInput,
    RecuirementResultEnum,
    RequirementResult,
    TWO_D_CLASSIFICATION,
    TaskBase,
    TaskCategory,
    TaskMessage,
    TaskOutcome,
    TaskResultMessage,
    TaskStatus,
    TaskStatusEnum,
    TopazPickInput,
)

# CoreService's legacy name for the motioncor task-type constant.
MOTIONCOR_TASK = MOTIONCOR
