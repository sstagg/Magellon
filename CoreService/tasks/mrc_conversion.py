# tasks/mrc_conversion.py
from typing import Dict, Any
from .base import Task, TaskResult, TaskConfig
from pydantic import Field, validator
import os
from services.mrc_image_service import MrcImageService

class MrcConversionConfig(TaskConfig):
    """Configuration for MRC conversion task"""
    input_file: str
    output_dir: str
    make_thumbnail: bool = True
    thumbnail_size: int = 256

    @validator('input_file')
    def input_file_exists(cls, v):
        if not os.path.exists(v):
            raise ValueError(f"Input file {v} does not exist")
        return v

    @validator('output_dir')
    def output_dir_valid(cls, v):
        os.makedirs(v, exist_ok=True)
        return v

class MrcConversionTask(Task):
    """Task for converting MRC files to PNG"""

    def __init__(self, config: MrcConversionConfig):
        super().__init__(config)
        self.mrc_service = MrcImageService()

    async def validate(self) -> bool:
        try:
            # Check that input file exists and is readable
            if not os.path.exists(self.config.input_file):
                return False

            # Ensure output directory exists or can be created
            os.makedirs(self.config.output_dir, exist_ok=True)

            return True
        except Exception:
            return False

    async def execute(self, context: Dict[str, Any] = None) -> TaskResult:
        try:
            # Convert MRC to PNG
            result = self.mrc_service.convert_mrc_to_png(
                abs_file_path=self.config.input_file,
                out_dir=self.config.output_dir,
                make_thumbnail=self.config.make_thumbnail,
                thumbnail_size=self.config.thumbnail_size
            )

            # Construct the output PNG path
            base_name = os.path.splitext(os.path.basename(self.config.input_file))[0]
            png_path = os.path.join(self.config.output_dir, "images", f"{base_name}.png")

            # Check if the conversion was successful
            if not os.path.exists(png_path):
                return TaskResult(
                    success=False,
                    message="MRC to PNG conversion failed",
                    error="Output file was not created"
                )

            # If thumbnail was requested, add its path to result data
            data = {"png_path": png_path}
            if self.config.make_thumbnail:
                thumb_path = os.path.join(self.config.output_dir, "thumbnails", f"{base_name}.png")
                data["thumbnail_path"] = thumb_path

            return TaskResult(
                success=True,
                message="MRC file successfully converted to PNG",
                data=data
            )

        except Exception as e:
            return TaskResult(
                success=False,
                message=f"MRC to PNG conversion failed: {str(e)}",
                error=str(e)
            )

# Register the task type
from .registry import task_registry
task_registry.register("mrc_to_png", MrcConversionTask)