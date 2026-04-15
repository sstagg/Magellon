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
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel


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
    sesson_id: Optional[UUID] = None
    sesson_name: Optional[str] = None
    worker_instance_id: Optional[UUID] = None
    data: Dict[str, Any]
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = datetime.now()
    start_on: Optional[datetime] = None
    end_on: Optional[datetime] = None
    result: Optional[TaskOutcome] = None

    @classmethod
    def calculate_data_hash(cls, data: Dict[str, Any]) -> str:
        data_str = str(data)
        return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


class TaskDto(TaskBase):
    job_id: Optional[UUID] = uuid4()

    @classmethod
    def create(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> "TaskDto":
        return cls(
            id=pid,
            job_id=job_id,
            worker_instance_id=instance_id,
            created_date=datetime.now(),
            status=pstatus,
            type=ptype,
            data=data,
        )


class JobDto(TaskBase):
    tasks: List[TaskDto] = []

    @classmethod
    def create(cls, pdata: Dict[str, Any], ptype: TaskCategory) -> "JobDto":
        return cls(
            uuid=uuid4(),
            data=pdata,
            created_date=datetime.now(),
            status=TaskStatus(code=0, name="pending", description="Job is pending"),
            type=ptype,
        )


class CryoEmImageTaskData(BaseModel):
    image_id: Optional[UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None


class MrcToPngTaskData(CryoEmImageTaskData):
    image_target: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class FftTaskData(CryoEmImageTaskData):
    target_name: Optional[str] = None
    target_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class CtfTaskData(CryoEmImageTaskData):
    inputFile: str
    outputFile: str = "ouput.mrc"
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


class CryoEmMotionCorTaskData(CryoEmImageTaskData):
    InMrc: Optional[str] = None
    InTiff: Optional[str] = None
    InEer: Optional[str] = None
    inputFile: str
    OutMrc: str = "output.mrc"
    outputFile: str = "output.mrc"
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
    PixSize: Optional[float] = False
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


class FftTask(TaskDto):
    data: FftTaskData


class CtfTask(TaskDto):
    data: CtfTaskData


class MotioncorTask(TaskDto):
    data: CryoEmMotionCorTaskData


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


class TaskResultDto(BaseModel):
    worker_instance_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    task_id: UUID = None
    image_id: UUID = None
    image_path: Optional[str] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    code: Optional[int] = None
    message: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None
    created_date: Optional[datetime] = datetime.now()
    started_on: Optional[datetime] = None
    ended_on: Optional[datetime] = None
    output_data: Dict[str, Any] = {}
    # Optional so result_processor can emit results where no per-image
    # metadata is attached (e.g. aggregate outcomes).
    meta_data: Optional[List[ImageMetaData]] = None
    output_files: List[OutputFile] = []


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
    "TaskDto",
    "JobDto",
    "TaskOutcome",
    "TaskStatus",
    "TaskStatusEnum",
    # Task-data shapes.
    "CryoEmImageTaskData",
    "MrcToPngTaskData",
    "FftTaskData",
    "CtfTaskData",
    "CryoEmMotionCorTaskData",
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
    "TaskResultDto",
    "DebugInfo",
]
