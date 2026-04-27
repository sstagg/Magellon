"""Task envelope and task-data DTOs shared across CoreService and plugins.

The shapes here used to live in ``core/model_dto.py`` inside each plugin
(and in ``models/plugins_models.py`` inside CoreService). They are
consolidated here so that plugin-contract fields only change in one
place.

Plugin-specific task-data subclasses (e.g. a plugin's own input schema)
should still live in the plugin — subclass :class:`CryoEmImageTaskData`
and pair it with a :class:`TaskDto` subclass as :class:`FftTask` /
:class:`CtfTask` below do.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TaskCategory(BaseModel):
    code: int
    name: str
    description: str

    def __hash__(self) -> int:
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TaskCategory):
            return False
        return self.code == other.code


class TaskStatus(BaseModel):
    code: int
    name: str
    description: str


class TaskOutcome(BaseModel):
    code: int
    message: str
    description: str
    output_data: Dict[str, Any] = {}


class TaskBase(BaseModel):
    id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    worker_instance_id: Optional[UUID] = None
    data: Dict[str, Any]
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = Field(default_factory=_now_utc)
    start_on: Optional[datetime] = None
    end_on: Optional[datetime] = None
    result: Optional[TaskOutcome] = None
    target_backend: Optional[str] = None
    """When set, the dispatcher routes this task only to a live plugin
    whose ``PluginManifest.backend_id`` matches. Unset (the default)
    keeps today's category-wide round-robin. Added in SDK 1.3."""

    @classmethod
    def calculate_data_hash(cls, data: Dict[str, Any]) -> str:
        data_str = str(data)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


class TaskMessage(TaskBase):
    """The wire envelope a dispatcher publishes. SDK 1.3+ canonical name.

    Wraps a category-shaped ``data`` payload with routing-time metadata
    (``job_id``, ``type``, ``status``, optional ``target_backend``).
    Pre-1.3 callers know it as ``TaskDto`` — the alias at the bottom
    of this module keeps that name working through 1.x.
    """

    job_id: Optional[UUID] = Field(default_factory=uuid4)

    @classmethod
    def create(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> "TaskMessage":
        return cls(
            id=pid,
            job_id=job_id,
            worker_instance_id=instance_id,
            created_date=_now_utc(),
            status=pstatus,
            type=ptype,
            data=data,
        )


class JobMessage(TaskBase):
    """Bundle of tasks under one logical user-visible unit. SDK 1.3+ name.

    Pre-1.3 callers know it as ``JobDto``."""

    tasks: List[TaskMessage] = []

    @classmethod
    def create(cls, pdata: Dict[str, Any], ptype: TaskCategory) -> "JobMessage":
        return cls(
            id=uuid4(),
            data=pdata,
            created_date=_now_utc(),
            status=TaskStatus(code=0, name="pending", description="Job is pending"),
            type=ptype,
        )


class CryoEmImageInput(BaseModel):
    """Base for category input shapes that operate on a single image.

    Renamed from ``CryoEmImageTaskData`` in SDK 1.3 to symmetrize with
    the existing ``*Output`` naming. The old name aliases the new one
    at module bottom, so existing plugins keep importing it unchanged."""

    image_id: Optional[UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    # Contravariant-input escape hatch: plugin-specific knobs that
    # the category contract doesn't know about. Every subclass
    # inherits this so CtfInput, FftInput, etc. all support
    # engine-specific extras without the category schema growing.
    # Opaque to the backend — round-trips untouched.
    engine_opts: Dict[str, Any] = Field(default_factory=dict)


class MrcToPngInput(CryoEmImageInput):
    image_target: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class FftInput(CryoEmImageInput):
    target_name: Optional[str] = None
    target_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class TopazPickInput(CryoEmImageInput):
    """Input for the Topaz particle-picking category.

    The MRC to pick is at ``input_file``. Engine knobs (model, NMS radius,
    score threshold, preprocess scale) ride on the inherited
    ``engine_opts`` dict so the canonical category contract stays narrow.
    Defaults match the Topaz tutorial: model=resnet16, radius=14,
    threshold=-3, scale=8.
    """

    input_file: str


class MicrographDenoiseInput(CryoEmImageInput):
    """Input for the Topaz-Denoise category — one MRC in, denoised MRC out.

    ``input_file`` is the source. ``output_file`` is where the plugin
    writes the denoised MRC; defaults to ``<input>_denoised.mrc`` when
    omitted. Engine knobs (model, patch_size) ride on ``engine_opts``.
    """

    input_file: str
    output_file: Optional[str] = None


class PtolemyInput(CryoEmImageInput):
    """Input for either ptolemy category — just the MRC to analyze.

    The same shape serves both square-detection (low-mag MRC) and
    hole-detection (med-mag MRC). The category chosen by the caller
    tells the plugin which pipeline to run; no type discriminator
    field is needed in the body.
    """

    input_file: str


class CtfInput(CryoEmImageInput):
    inputFile: str
    outputFile: str = "output.mrc"
    pixelSize: float = 1.0
    accelerationVoltage: float = 300.0
    sphericalAberration: float = 2.70
    amplitudeContrast: float = 0.07
    sizeOfAmplitudeSpectrum: int = 512
    minimumResolution: float = 30.0
    maximumResolution: float = 5.0
    minimumDefocus: float = 5000.0
    maximumDefocus: float = 50000.0
    defocusSearchStep: float = 100.0
    binning_x: int = 1


class MotionCorInput(CryoEmImageInput):
    InMrc: Optional[str] = None
    InTiff: Optional[str] = None
    InEer: Optional[str] = None
    inputFile: str
    # OutMrc is the canonical output field — mirrors MotionCor3 CLI's
    # ``-OutMrc`` flag and is the name the binary actually reads.
    # (Pre-1.0 we also had a parallel ``outputFile`` field that set
    # the same value; it was never sent to the binary. Dropped.)
    OutMrc: str = "output.mrc"
    Gain: str
    Dark: Optional[str] = None
    DefectFile: Optional[str] = None
    DefectMap: Optional[str] = None
    PatchesX: int = 1
    PatchesY: int = 1
    Iter: int = 5
    Tol: float = 0.5
    Bft: int = 100
    LogDir: str = "."
    Gpu: str = "0"
    FtBin: float = 2
    FmDose: Optional[float] = None
    PixSize: Optional[float] = None
    kV: int = 300
    Cs: int = 0
    AmpCont: float = 0.07
    ExtPhase: float = 0
    SumRangeMinDose: int = 3
    SumRangeMaxDose: int = 25
    Group: Optional[int] = None
    RotGain: int = 0
    FlipGain: int = 0
    InvGain: Optional[int] = None
    FmIntFile: Optional[str] = None
    EerSampling: int = 1


class FftTask(TaskMessage):
    data: FftInput


class CtfTask(TaskMessage):
    data: CtfInput


class MotioncorTask(TaskMessage):
    data: MotionCorInput


class TaskStatusEnum(Enum):
    PENDING = {"code": 0, "name": "pending", "description": "Task is pending"}
    IN_PROGRESS = {"code": 1, "name": "in_progress", "description": "Task is in progress"}
    COMPLETED = {"code": 2, "name": "completed", "description": "Task has been completed"}
    FAILED = {"code": 3, "name": "failed", "description": "Task has failed"}


# Task-type constants — plugin dispatchers switch on these codes.
FFT_TASK = TaskCategory(code=1, name="FFT", description="Fast Fourier Transform")
CTF_TASK = TaskCategory(code=2, name="CTF", description="Contrast Transfer Function")
PARTICLE_PICKING = TaskCategory(code=3, name="Particle Picking", description="Identifying particles in images")
TWO_D_CLASSIFICATION = TaskCategory(code=4, name="2D Classification", description="Classifying 2D images")
MOTIONCOR = TaskCategory(code=5, name="MotionCor", description="Motion correction for electron microscopy")
SQUARE_DETECTION = TaskCategory(code=6, name="SquareDetection", description="Low-mag square detection and pickability scoring")
HOLE_DETECTION = TaskCategory(code=7, name="HoleDetection", description="Medium-mag hole detection and pickability scoring")
TOPAZ_PARTICLE_PICKING = TaskCategory(code=8, name="TopazParticlePicking", description="High-mag particle picking via Topaz CNN")
MICROGRAPH_DENOISING = TaskCategory(code=9, name="MicrographDenoising", description="Topaz-Denoise UNet on a single MRC")

# Task-status constants.
PENDING = TaskStatus(code=0, name="pending", description="Task is pending")
IN_PROGRESS = TaskStatus(code=1, name="in_progress", description="Task is in progress")
COMPLETED = TaskStatus(code=2, name="completed", description="Task has been completed")
FAILED = TaskStatus(code=3, name="failed", description="Task has failed")


class ImageMetaData(BaseModel):
    key: str
    value: str
    is_persistent: Optional[bool] = None
    image_id: Optional[str] = None


class OutputFile(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    required: bool


class TaskResultMessage(BaseModel):
    """The wire envelope a plugin publishes when a task finishes.

    SDK 1.3+ canonical name; pre-1.3 callers know it as ``TaskResultDto``."""

    worker_instance_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    image_id: Optional[UUID] = None
    image_path: Optional[str] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    code: Optional[int] = None
    message: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = Field(default_factory=_now_utc)
    started_on: Optional[datetime] = None
    ended_on: Optional[datetime] = None
    output_data: Dict[str, Any] = {}
    # Optional so result_processor can emit results where no per-image
    # metadata is attached (e.g. aggregate outcomes).
    meta_data: Optional[List[ImageMetaData]] = None
    output_files: List[OutputFile] = []
    # Provenance (P4). The plugin that produced this result identifies
    # itself so operators can answer "which engine processed this
    # micrograph?" without grepping logs. Optional because (a) older
    # plugins won't populate them yet, and (b) aggregator results have
    # no single-plugin owner. Both should match the values exposed in
    # the plugin's manifest (PluginInfo.name + .version) so the audit
    # trail and the registry agree.
    plugin_id: Optional[str] = None
    plugin_version: Optional[str] = None


class DebugInfo(BaseModel):
    id: Optional[str] = None
    line1: Optional[str] = None
    line2: Optional[str] = None
    line3: Optional[str] = None
    line4: Optional[str] = None
    line5: Optional[str] = None
    line6: Optional[str] = None
    line7: Optional[str] = None
    line8: Optional[str] = None


__all__ = [
    # Envelope.
    "TaskBase",
    "TaskCategory",
    "TaskMessage",
    "JobMessage",
    "TaskOutcome",
    "TaskStatus",
    "TaskStatusEnum",
    # Per-category input shapes.
    "CryoEmImageInput",
    "MrcToPngInput",
    "FftInput",
    "CtfInput",
    "MotionCorInput",
    "TopazPickInput",
    "MicrographDenoiseInput",
    "PtolemyInput",
    # Concrete tasks.
    "FftTask",
    "CtfTask",
    "MotioncorTask",
    # Constants.
    "FFT_TASK",
    "CTF_TASK",
    "PARTICLE_PICKING",
    "TWO_D_CLASSIFICATION",
    "MOTIONCOR",
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "FAILED",
    # Result / debug.
    "ImageMetaData",
    "OutputFile",
    "TaskResultMessage",
    "DebugInfo",
]
