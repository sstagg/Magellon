from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from models.tasks.base_models import BaseJob, JobStatus


class JobSpecification(BaseModel):
    """Input model for creating a new job"""
    name: str
    description: Optional[str] = None
    job_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    priority: int = 0


class ImportJobSpecification(JobSpecification):
    """Specification for import jobs"""
    job_type: str = "import"
    source_directory: str
    target_directory: str
    importer_type: str  # "epu", "leginon", "serialem", etc.
    copy_images: bool = False
    if_do_subtasks: bool = True


class JobWithTasks(BaseJob):
    """Job model with embedded task information"""
    tasks: List[Dict[str, Any]] = Field(default_factory=list)


class JobSummary(BaseModel):
    """Summary model for job listings"""
    id: str
    name: str
    job_type: str
    status: JobStatus
    progress: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_tasks: int
    completed_tasks: int
    failed_tasks: int