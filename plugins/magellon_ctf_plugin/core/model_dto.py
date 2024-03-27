import hashlib
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional
from uuid import uuid4, UUID

from pydantic import BaseModel, Field


class TaskType(BaseModel):
    code: int
    name: str
    description: str


class TaskResult(BaseModel):
    code: int
    message: str
    description: str
    output_data: Dict[str, Any] = {}  # Additional output data


class TaskStatus(BaseModel):
    code: int
    name: str
    description: str


class TaskBaseDto(BaseModel):
    id: Optional[str] = str(uuid.uuid4())
    worker_instance_id: Optional[UUID] = None  # Instance ID of the worker
    data: Dict[str, Any]  # Assuming data is a dictionary; adjust the type accordingly
    status: Optional[TaskStatus] = None
    type: Optional[TaskType] = None  # Adjust the type based on your needs
    created_date: Optional[datetime] = datetime.now()  # Created date and time
    start_on: Optional[datetime] = None  # Start time of task execution
    end_on: Optional[datetime] = None  # End time of task execution
    result: Optional[TaskResult] = None

    # class Config:
    #     allow_mutation = False  # Make the model immutable to prevent accidental changes

    @classmethod
    def calculate_data_hash(cls, data: Dict[str, Any]) -> str:
        # Calculate the hash of the data using SHA-256
        data_str = str(data)
        return hashlib.sha256(data_str.encode('utf-8')).hexdigest()


class TaskDto(TaskBaseDto):
    job_id: Optional[UUID] = (uuid.uuid4())

    @classmethod
    def create(cls, data: Dict[str, Any], ptype: TaskType, pstatus: TaskStatus, instance_id: UUID, job_id: UUID):
        # Create a new instance of TaskDto with the provided data
        task = cls(
            id=str(uuid4()),
            data=data,
            created_date=datetime.now(),
            status=pstatus,
            type=ptype,
            worker_instance_id=instance_id,
            job_id=job_id
        )
        return task


class JobDto(TaskBaseDto):
    tasks: List[TaskDto] = []  # List of associated tasks

    @classmethod
    def create(cls, pdata: Dict[str, Any], ptype: TaskType):
        # Create a new instance of JobModel with the provided data
        job = cls(
            uuid=uuid4(),
            data=pdata,
            created_date=datetime.now(),
            status=TaskStatus(code=0, name="pending", description="Job is pending"),
            type=ptype
        )
        return job


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


# Enums for TaskType
FFT_TASK = TaskType(code=1, name="FFT", description="Fast Fourier Transform")
CTF_TASK = TaskType(code=2, name="CTF", description="Contrast Transfer Function")
PARTICLE_PICKING = TaskType(code=3, name="Particle Picking", description="Identifying particles in images")
TWO_D_CLASSIFICATION = TaskType(code=4, name="2D Classification", description="Classifying 2D images")
MOTIONCOR = TaskType(code=5, name="MotionCor", description="Motion correction for electron microscopy")

# Enums for TaskStatus
PENDING = TaskStatus(code=0, name="pending", description="Task is pending")
IN_PROGRESS = TaskStatus(code=1, name="in_progress", description="Task is in progress")
COMPLETED = TaskStatus(code=2, name="completed", description="Task has been completed")
FAILED = TaskStatus(code=3, name="failed", description="Task has failed")


class TaskStatusEnum(Enum):
    # Enums for TaskStatus
    PENDING = {"code": 0, "name": "pending", "description": "Task is pending"}
    IN_PROGRESS = {"code": 1, "name": "in_progress", "description": "Task is in progress"}
    COMPLETED = {"code": 2, "name": "completed", "description": "Task has been completed"}
    FAILED = {"code": 3, "name": "failed", "description": "Task has failed"}


class CryoEmImageTaskData(BaseModel):
    image_id: Optional[UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None


class CryoEmMrcToPngTaskData(CryoEmImageTaskData):
    image_target: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class CryoEmFftTaskDetailDto(CryoEmImageTaskData):
    target_name: Optional[str] = None
    target_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None


class CryoEmCtfTaskData(BaseModel):
    image_id: Optional[UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    image_target: Optional[str] = None
    description: Optional[str] = None
    copyright: Optional[str] = None
    version: Optional[str] = None


class RecuirementResultEnum(Enum):
    SUCCESS = 10
    WARNING = 20
    FAILURE = 30


class RecuirementResult(BaseModel):
    code: Optional[int] = None
    error_type: Optional[CheckRequirementsResult] = None
    result: RecuirementResultEnum = RecuirementResultEnum.FAILURE
    condition: Optional[str] = None
    message: Optional[str] = None
    instructions: Optional[str] = None
