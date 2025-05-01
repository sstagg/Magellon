from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from models.tasks.base_models import BaseTask, TaskType, TaskStatus


class TaskSpecification(BaseModel):
    """Input model for creating a new task"""
    job_id: str
    task_type: TaskType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)
    priority: int = 0


class TaskResult(BaseModel):
    """Model for task execution results"""
    task_id: str
    job_id: str
    status: TaskStatus
    progress: int = 100
    error: Optional[str] = None
    output: Dict[str, Any] = Field(default_factory=dict)
    execution_time: float  # in seconds


class FileInfo(BaseModel):
    """Information about a file used in tasks"""
    path: str
    name: str
    size: Optional[int] = None
    mime_type: Optional[str] = None
    exists: bool = True


class TaskProgress(BaseModel):
    """Model for progress updates during task execution"""
    task_id: str
    job_id: str
    progress: int
    current_operation: Optional[str] = None
    message: Optional[str] = None
    timestamp: float  # Unix timestamp