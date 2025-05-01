from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid

class EventType(str, Enum):
    """Event type constants for the system"""
    # Job events
    JOB_CREATED = "job.created"
    JOB_STARTED = "job.started"
    JOB_UPDATED = "job.updated"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"

    # Task events
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"

    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_INFO = "system.info"


class Event(BaseModel):
    """Base model for all system events"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        validate_assignment = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }


class JobEvent(Event):
    """Model for job-related events"""
    source: str = "job_manager"
    job_id: str


class TaskEvent(Event):
    """Model for task-related events"""
    source: str = "task_processor"
    task_id: str
    job_id: str


class SystemEvent(Event):
    """Model for system-related events"""
    source: str = "system"
    level: str = "info"  # "info", "warning", "error"
    message: str