from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from models.tasks.base_models import BaseTask, TaskType
from models.tasks.task_models import FileInfo


class MotionCorTaskParameters(BaseModel):
    """Parameters specific to motion correction tasks"""
    input_file: FileInfo
    output_file: FileInfo
    gain_file: Optional[FileInfo] = None
    dark_file: Optional[FileInfo] = None
    defect_file: Optional[FileInfo] = None
    pixel_size: float
    dose_per_frame: float
    acceleration_voltage: float = 300.0
    patches_x: int = 5
    patches_y: int = 5
    iterations: int = 10
    tolerance: float = 0.5
    b_factor: int = 100
    ft_bin: float = 1.0
    binning: int = 1
    group: Optional[int] = None
    use_gpu: bool = True
    gpu_ids: List[int] = Field(default_factory=lambda: [0])
    additional_options: Dict[str, Any] = Field(default_factory=dict)


class MotionCorTask(BaseTask):
    """Motion correction task model"""
    task_type: TaskType = TaskType.MOTIONCOR
    parameters: MotionCorTaskParameters

    class Config:
        validate_assignment = True


class MotionCorResult(BaseModel):
    """Result of a motion correction task"""
    input_file: FileInfo
    output_file: FileInfo
    alignment_file: Optional[FileInfo] = None
    total_motion: float  # in angstroms
    early_motion: float  # in angstroms
    late_motion: float  # in angstroms
    frame_shifts: List[Dict[str, float]] = Field(default_factory=list)
    execution_time: float
    success: bool
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)