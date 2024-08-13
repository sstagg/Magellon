import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import uuid4, UUID

from pydantic import BaseModel


class TaskCategory(BaseModel):
    code: int
    name: str
    description: str


class TaskOutcome(BaseModel):
    code: int
    message: str
    description: str
    output_data: Dict[str, Any] = {}  # Additional output data


class TaskStatus(BaseModel):
    code: int
    name: str
    description: str


class TaskBase(BaseModel):
    id: Optional[UUID] = None  #str(uuid.uuid4())
    sesson_id: Optional[UUID] = None  #str(uuid.uuid4())
    sesson_name: Optional[str] = None
    worker_instance_id: Optional[UUID] = None  # Instance ID of the worker
    data: Dict[str, Any]  # Assuming data is a dictionary; adjust the type accordingly
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None  # Adjust the type based on your needs
    created_date: Optional[datetime] = datetime.now()  # Created date and time
    start_on: Optional[datetime] = None  # Start time of task execution
    end_on: Optional[datetime] = None  # End time of task execution
    result: Optional[TaskOutcome] = None

    # class Config:
    #     allow_mutation = False  # Make the model immutable to prevent accidental changes

    @classmethod
    def calculate_data_hash(cls, data: Dict[str, Any]) -> str:
        # Calculate the hash of the data using SHA-256
        data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()


class TaskDto(TaskBase):
    job_id: Optional[UUID] = (uuid.uuid4())

    @classmethod
    def create(cls, pid: UUID, job_id: UUID, ptype: TaskCategory, pstatus: TaskStatus, instance_id: UUID,
               data: Dict[str, Any]):
        task = cls(
            id=pid,  #str(uuid4()),
            job_id=job_id,
            worker_instance_id=instance_id,
            created_date=datetime.now(),
            status=pstatus,
            type=ptype,
            data=data)
        # Create a new instance of TaskDto with the provided data
        return task


class JobDto(TaskBase):
    tasks: List[TaskDto] = []  # List of associated tasks

    @classmethod
    def create(cls, pdata: Dict[str, Any], ptype: TaskCategory):
        # Create a new instance of JobModel with the provided data
        job = cls(
            uuid=uuid4(),
            data=pdata,
            created_date=datetime.now(),
            status=TaskStatus(code=0, name="pending", description="Job is pending"),
            type=ptype
        )
        return job


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


class FftTask(TaskDto):
    data: FftTaskData


class CtfTask(TaskDto):
    data: CtfTaskData


class TaskStatusEnum(Enum):
    # Enums for TaskStatus
    PENDING = {"code": 0, "name": "pending", "description": "Task is pending"}
    IN_PROGRESS = {"code": 1, "name": "in_progress", "description": "Task is in progress"}
    COMPLETED = {"code": 2, "name": "completed", "description": "Task has been completed"}
    FAILED = {"code": 3, "name": "failed", "description": "Task has failed"}


class PluginInfo(BaseModel):
    id: Optional[str] = str(uuid.uuid4())
    instance_id: Optional[str] = str(uuid.uuid4())
    name: Optional[str] = None
    developer: Optional[str] = None
    description: Optional[str] = None
    copyright: Optional[str] = None
    version: Optional[str] = None
    created_date: Optional[datetime] = datetime.utcnow()
    last_updated: Optional[datetime] = datetime.utcnow()
    # port_number: Optional[int] = Field(..., ge=0, le=65535)


class PluginInfoSingleton:
    _instance = None

    @classmethod
    def get_instance(cls, **kwargs):
        if cls._instance is None:
            cls._instance = PluginInfo(**kwargs)
        return cls._instance


class CheckRequirementsResult(Enum):
    SUCCESS = 100
    FAILURE_PYTHON_VERSION_ERROR = 201
    FAILURE_OS_ERROR = 202
    FAILURE_REQUIREMENTS = 203


class RecuirementResultEnum(Enum):
    SUCCESS = 10
    WARNING = 20
    FAILURE = 30


class RequirementResult(BaseModel):
    code: Optional[int] = None
    error_type: Optional[CheckRequirementsResult] = None
    result: RecuirementResultEnum = RecuirementResultEnum.FAILURE
    condition: Optional[str] = None
    message: Optional[str] = None
    instructions: Optional[str] = None


# Enums for TaskType
FFT_TASK = TaskCategory(code=1, name="FFT", description="Fast Fourier Transform")
CTF_TASK = TaskCategory(code=2, name="CTF", description="Contrast Transfer Function")
PARTICLE_PICKING = TaskCategory(code=3, name="Particle Picking", description="Identifying particles in images")
TWO_D_CLASSIFICATION = TaskCategory(code=4, name="2D Classification", description="Classifying 2D images")
MOTIONCOR = TaskCategory(code=5, name="MotionCor", description="Motion correction for electron microscopy")

# Enums for TaskStatus
PENDING = TaskStatus(code=0, name="pending", description="Task is pending")
IN_PROGRESS = TaskStatus(code=1, name="in_progress", description="Task is in progress")
COMPLETED = TaskStatus(code=2, name="completed", description="Task has been completed")
FAILED = TaskStatus(code=3, name="failed", description="Task has failed")


# isastigmatismPresent: bool=False
# slowerExhaustiveSearch: bool =False
# restraintOnAstogmatism: bool =False
# FindAdditionalPhaseShift: bool = False
# setExpertOptions:bool =False


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
    worker_instance_id: Optional[UUID] = None  # Instance ID of the worker
    job_id: Optional[UUID] = None
    task_id: UUID = None  # str(uuid.uuid4())
    image_id: UUID = None
    image_path: Optional[str] = None
    session_id: Optional[UUID] = None
    session_name: Optional[str] = None
    code: Optional[int] = None
    message: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    type: Optional[TaskCategory] = None  # Adjust the type based on your needs
    created_date: Optional[datetime] = datetime.now()  # Created date and time
    started_on: Optional[datetime] = None  # Start time of task execution
    ended_on: Optional[datetime] = None  # End time of task execution
    output_data: Dict[str, Any] = {}  # Additional output data
    meta_data: List[ImageMetaData]
    output_files: List[OutputFile]


class DebugInfo(BaseModel):
    id: Optional[str] = str(uuid.uuid4())
    line1: Optional[str] = None
    line2: Optional[str] = None
    line3: Optional[str] = None
    line4: Optional[str] = None
    line5: Optional[str] = None
    line6: Optional[str] = None
    line7: Optional[str] = None
    line8: Optional[str] = None
