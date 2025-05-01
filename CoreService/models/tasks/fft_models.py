from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from models.tasks.base_models import BaseTask, TaskType
from models.tasks.task_models import FileInfo


class FFTTaskParameters(BaseModel):
    """Parameters specific to FFT computation tasks"""
    input_file: FileInfo
    output_file: FileInfo
    pixel_size: float
    binning: int = 1
    additional_options: Dict[str, Any] = Field(default_factory=dict)


class FFTTask(BaseTask):
    """Fast Fourier Transform task model"""
    task_type: TaskType = TaskType.FFT
    parameters: FFTTaskParameters

    class Config:
        validate_assignment = True


class FFTTaskResult(BaseModel):
    """Result of an FFT computation task"""
    input_file: FileInfo
    output_file: FileInfo
    execution_time: float
    success: bool
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)