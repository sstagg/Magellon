from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from models.tasks.base_models import BaseTask, TaskType
from models.tasks.task_models import FileInfo


class CTFTaskParameters(BaseModel):
    """Parameters specific to CTF computation tasks"""
    input_file: FileInfo
    output_file: FileInfo
    pixel_size: float
    acceleration_voltage: float = 300.0
    spherical_aberration: float = 2.7
    amplitude_contrast: float = 0.07
    size_of_amplitude_spectrum: int = 512
    minimum_resolution: float = 30.0
    maximum_resolution: float = 5.0
    minimum_defocus: float = 5000.0
    maximum_defocus: float = 50000.0
    defocus_search_step: float = 100.0
    binning: int = 1
    is_astigmatism_present: bool = False
    slower_exhaustive_search: bool = False
    restraint_on_astigmatism: bool = False
    find_additional_phase_shift: bool = False
    set_expert_options: bool = False
    additional_options: Dict[str, Any] = Field(default_factory=dict)


class CTFTask(BaseTask):
    """Contrast Transfer Function task model"""
    task_type: TaskType = TaskType.CTF
    parameters: CTFTaskParameters

    class Config:
        validate_assignment = True


class CTFResult(BaseModel):
    """Result of a CTF computation task"""
    input_file: FileInfo
    output_file: FileInfo
    defocus: float  # in angstroms
    astigmatism: float = 0.0
    astigmatism_angle: float = 0.0
    cross_correlation: float
    resolution_limit: float  # in angstroms
    execution_time: float
    success: bool
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)