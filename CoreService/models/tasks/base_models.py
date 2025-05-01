import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    """Task status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Base task types"""
    FFT = "fft"
    CTF = "ctf"
    MOTIONCOR = "motioncor"
    IMPORT = "import"
    EXPORT = "export"
    GENERIC = "generic"


class BaseTask(BaseModel):
    """Base model for all tasks"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class BaseJob(BaseModel):
    """Base model for all jobs"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    job_type: str
    status: JobStatus = JobStatus.PENDING
    progress: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    task_ids: List[str] = Field(default_factory=list)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    current_task: Optional[str] = None

    class Config:
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }