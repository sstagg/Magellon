"""
Domain models for job and task management.

Contains status constants and data classes for Job and Task entities.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List


class JobStatus:
    """Job status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus:
    """Task status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job:
    """Job model with task collection"""

    def __init__(
            self,
            job_id: str,
            job_type: str,
            name: str,
            description: Optional[str] = None,
            metadata: Dict[str, Any] = None,
            status: str = JobStatus.PENDING,
            progress: int = 0,
            created_at: str = None,
            updated_at: str = None,
            completed_at: str = None,
            tasks_total: int = 0,
            tasks_completed: int = 0,
            tasks_failed: int = 0,
            current_task: Optional[str] = None,
            cancel_requested: bool = False,
            error: Optional[str] = None
    ):
        self.job_id = job_id
        self.job_type = job_type
        self.name = name
        self.description = description or f"{job_type} job"
        self.metadata = metadata or {}
        self.status = status
        self.progress = progress
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()
        self.completed_at = completed_at
        self.tasks_total = tasks_total
        self.tasks_completed = tasks_completed
        self.tasks_failed = tasks_failed
        self.current_task = current_task
        self.cancel_requested = cancel_requested
        self.error = error
        self.tasks = []  # List of Task objects

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "name": self.name,
            "description": self.description,
            "metadata": self.metadata,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "current_task": self.current_task,
            "cancel_requested": self.cancel_requested,
            "error": self.error,
            "task_ids": [task.task_id for task in self.tasks]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create from dictionary representation"""
        job_data = data.copy()
        task_ids = job_data.pop("task_ids", [])
        return cls(**job_data)

    def update_progress(self) -> int:
        """Update progress based on task completion"""
        if self.tasks_total == 0:
            return 0

        completed_and_failed = self.tasks_completed + self.tasks_failed
        progress = min(int((completed_and_failed / self.tasks_total) * 100), 100)
        self.progress = progress
        return progress

    def update_status_from_tasks(self) -> None:
        """Update job status based on task statuses"""
        if self.tasks_total == 0:
            return

        completed_and_failed = self.tasks_completed + self.tasks_failed

        if self.cancel_requested:
            self.status = JobStatus.CANCELLED
            if not self.completed_at:
                self.completed_at = datetime.utcnow().isoformat()

        elif completed_and_failed >= self.tasks_total:
            if self.tasks_failed > 0:
                self.status = JobStatus.FAILED
                self.error = f"{self.tasks_failed} tasks failed"
            else:
                self.status = JobStatus.COMPLETED

            if not self.completed_at:
                self.completed_at = datetime.utcnow().isoformat()
        elif self.tasks_completed > 0 or self.tasks_failed > 0:
            self.status = JobStatus.RUNNING


class Task:
    """Task model for an individual unit of work"""

    def __init__(
            self,
            task_id: str,
            job_id: str,
            task_type: str,
            parameters: Dict[str, Any] = None,
            status: str = TaskStatus.PENDING,
            progress: int = 0,
            created_at: str = None,
            updated_at: str = None,
            completed_at: str = None,
            result: Dict[str, Any] = None,
            error: Optional[str] = None,
            cancel_requested: bool = False
    ):
        self.task_id = task_id
        self.job_id = job_id
        self.task_type = task_type
        self.parameters = parameters or {}
        self.status = status
        self.progress = progress
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()
        self.completed_at = completed_at
        self.result = result or {}
        self.error = error
        self.cancel_requested = cancel_requested

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "task_id": self.task_id,
            "job_id": self.job_id,
            "task_type": self.task_type,
            "parameters": self.parameters,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "cancel_requested": self.cancel_requested
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create from dictionary representation"""
        return cls(**data)
