from datetime import datetime
import os
import logging
from typing import Any

from services.file_service import copy_file
from services.mrc_image_service import MrcImageService
from core.helper import create_directory, dispatch_ctf_task
from config import (
    FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, 
    ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, FFT_SUFFIX, 
    ATLAS_SUB_URL, CTF_SUB_URL, FRAMES_SUFFIX
)

logger = logging.getLogger(__name__)

class FileError(Exception):
    """Exception for file operation errors"""
    pass

class TaskError(Exception):
    """Exception for task processing errors"""
    pass

class ImportFileService:
    """Service class for handling all file operations related to imports"""
    
    def __init__(self, target_directory: str, camera_directory: str):
        self.target_directory = target_directory
        self.camera_directory = camera_directory
        self.mrc_service = MrcImageService()

    def create_required_directories(self) -> None:
        """Create all required directories for import process"""
        try:
            subdirs = [
                "", ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, FFT_SUB_URL,
                IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ATLAS_SUB_URL, CTF_SUB_URL
            ]
            for subdir in subdirs:
                path = os.path.join(self.target_directory, subdir)
                create_directory(path)
        except Exception as e:
            raise FileError(f"Failed to create directories: {str(e)}")

    def process_task(self, task: Any, copy_images: bool = False) -> None:
        """Process a single task including frame transfer, image copy, and image processing"""
        try:
            self.transfer_frame(task)
            if copy_images:
                self.copy_image(task)
            self.process_image(task)
        except Exception as e:
            raise TaskError(f"Task processing failed: {str(e)}")

    def transfer_frame(self, task: Any) -> None:
        """Transfer frame file if it exists"""
        if hasattr(task, 'frame_name') and task.frame_name:
            source = os.path.join(self.camera_directory, task.frame_name)
            if os.path.exists(source):
                target = os.path.join(
                    self.target_directory,
                    FRAMES_SUB_URL,
                    f"{task.file_name}{FRAMES_SUFFIX}{os.path.splitext(task.frame_name)[1]}"
                )
                copy_file(source, target)

    def copy_image(self, task: Any) -> None:
        """Copy image file to target directory"""
        target = os.path.join(
            self.target_directory,
            ORIGINAL_IMAGES_SUB_URL,
            task.image_name
        )
        copy_file(task.image_path, target)
        task.image_path = target

    def process_image(self, task: Any) -> None:
        """Process image file including conversion to PNG and FFT computation"""
        self.mrc_service.convert_mrc_to_png(
            abs_file_path=task.image_path,
            out_dir=self.target_directory
        )

        fft_path = os.path.join(
            self.target_directory,
            FFT_SUB_URL,
            f"{os.path.splitext(os.path.basename(task.image_path))[0]}{FFT_SUFFIX}"
        )
        self.mrc_service.compute_mrc_fft(
            mrc_abs_path=task.image_path,
            abs_out_file_name=fft_path
        )

        # Dispatch CTF task if needed
        if hasattr(task, 'pixel_size') and (task.pixel_size * 10 ** 10) <= 5:
            dispatch_ctf_task(task.task_id, task.image_path, task)
