# tasks/fft_computation.py
from typing import Dict, Any
from .base import Task, TaskResult, TaskConfig
from pydantic import validator
import os
from services.mrc_image_service import MrcImageService

class FFTComputationConfig(TaskConfig):
    """Configuration for FFT computation task"""
    input_file: str
    output_file: str

    @validator('input_file')
    def input_file_exists(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Input file {v} does not exist")
        return v

    @validator('output_file')
    def output_file_valid(cls, v):
        # Ensure output directory exists
        os.makedirs(os.path.dirname(v), exist_ok=True)
        return v

class FFTComputationTask(Task):
    """Task for computing FFT of MRC files"""

    def __init__(self, config: FFTComputationConfig):
        super().__init__(config)
        self.mrc_service = MrcImageService()

    async def validate(self) -> bool:
        try:
            # Check that input file exists and is readable
            if not os.path.exists(self.config.input_file):
                return False

            # Ensure output directory exists or can be created
            os.makedirs(os.path.dirname(self.config.output_file), exist_ok=True)

            return True
        except Exception:
            return False

    async def execute(self, context: Dict[str, Any] = None) -> TaskResult:
        try:
            # Determine file type by extension
            _, ext = os.path.splitext(self.config.input_file)
            ext = ext.lower()

            # Compute FFT based on file type
            if ext in ['.mrc', '.mrcs']:
                # MRC file
                result = self.mrc_service.compute_mrc_fft(
                    mrc_abs_path=self.config.input_file,
                    abs_out_file_name=self.config.output_file
                )
            elif ext in ['.tif', '.tiff']:
                # TIFF file
                result = self.mrc_service.compute_tiff_fft(
                    tiff_abs_path=self.config.input_file,
                    abs_out_file_name=self.config.output_file
                )
            else:
                return TaskResult(
                    success=False,
                    message=f"Unsupported file format: {ext}",
                    error=f"Cannot compute FFT for {ext} files"
                )

            # Check if the computation was successful
            if not os.path.exists(self.config.output_file):
                return TaskResult(
                    success=False,
                    message="FFT computation failed",
                    error="Output file was not created"
                )

            return TaskResult(
                success=True,
                message="FFT computed successfully",
                data={"fft_path": self.config.output_file}
            )

        except Exception as e:
            return TaskResult(
                success=False,
                message=f"FFT computation failed: {str(e)}",
                error=str(e)
            )

# Register the task type
from .registry import task_registry
task_registry.register("compute_fft", FFTComputationTask)