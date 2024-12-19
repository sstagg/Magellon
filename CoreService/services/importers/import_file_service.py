import shutil
import tarfile
import zipfile
from datetime import datetime
import os
import logging
from typing import Any, Union

from services.file_service import copy_file
from services.mrc_image_service import MrcImageService
from core.helper import create_directory, dispatch_ctf_task
from config import (
    FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL,
    ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, FFT_SUFFIX,
    ATLAS_SUB_URL, CTF_SUB_URL, FRAMES_SUFFIX, GAIN_SUB_URL
)
import uuid
import py7zr


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
                IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ATLAS_SUB_URL, CTF_SUB_URL,GAIN_SUB_URL
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
        # if hasattr(task, 'pixel_size') and (task.pixel_size * 10 ** 10) <= 5:
        #     dispatch_ctf_task(task.task_id, task.image_path, task)




    @staticmethod
    def create_temp_directory(parent_dir : str) -> tuple[Any, Union[str, Any]]:
        """
        Create a unique temporary directory using UUID.

        Returns:
            str: Path to the created temporary directory
        """
        # base_uuid = str(uuid.uuid4())
        temp_dir = os.path.join(parent_dir, 'export', str(uuid.uuid4()))
        os.makedirs(temp_dir, exist_ok=True)

        home_dir = os.path.join(temp_dir, 'home')
        os.makedirs(home_dir, exist_ok=True)
        return temp_dir , home_dir




    @staticmethod
    def copy_directory(source_dir: str, destination_dir: str) -> None:
        """
        Copies the entire directory hierarchy from source_dir to destination_dir.

        Args:
            source_dir (str): The path of the directory to copy.
            destination_dir (str): The path of the directory where the content will be copied.

        Raises:
            FileNotFoundError: If the source directory does not exist.
            FileExistsError: If the destination directory already exists.
        """
        try:
            # Check if the source directory exists
            if not os.path.exists(source_dir):
                raise FileNotFoundError(f"Source directory '{source_dir}' does not exist.")

            # If destination directory exists, remove it
            if os.path.exists(destination_dir):
                shutil.rmtree(destination_dir)

            # Copy the source directory to the destination
            shutil.copytree(source_dir, destination_dir)

            print(f"Directory successfully copied from '{source_dir}' to '{destination_dir}'.")

        except FileNotFoundError as e:
            print(f"Error: {e}")

        except PermissionError as e:
            print(f"Permission Error: {e}. Ensure you have the required permissions.")

        except OSError as e:
            print(f"OS Error: {e}. This might be due to filesystem restrictions.")

        except Exception as e:
            print(f"An unexpected error occurred: {e}")


    @staticmethod
    def create_7archive(base_dir: str, output_file_name: str) -> str:
        """
        Creates a 7zip archive of a directory with .mag extension.

        Args:
            base_dir (str): Path to the directory to archive.
            output_file_name (str): Name of the output archive file (without extension).

        Returns:
            str: Path to the created archive file.

        Raises:
            FileNotFoundError: If the source directory doesn't exist.
            PermissionError: If there are permission issues during archive creation.
            py7zr.Bad7zFile: If there is an error with the 7zip file.
            OSError: If there are filesystem restrictions.
        """
        try:
            # Validate input directory
            if not os.path.exists(base_dir):
                raise FileNotFoundError(f"Directory '{base_dir}' does not exist.")

            # Ensure output filename has .mag extension
            if not output_file_name.endswith('.mag'):
                output_file_name += '.mag'

            # Create full output path
            output_path = os.path.join(os.path.dirname(base_dir), output_file_name)

            # Remove existing archive if it exists
            if os.path.exists(output_path):
                os.remove(output_path)

            # Create 7zip archive with maximum compression
            with py7zr.SevenZipFile(output_path, 'w') as archive:
                archive.writeall(base_dir, os.path.basename(base_dir))

            logging.info(f"Successfully created archive at '{output_path}'")
            return output_path

        except FileNotFoundError as e:
            logging.error(f"Error: {e}")
            raise

        except PermissionError as e:
            logging.error(f"Permission Error: {e}. Ensure you have the required permissions.")
            raise

        except py7zr.Bad7zFile as e:
            logging.error(f"7zip Error: {e}. There was an error creating the archive.")
            raise

        except OSError as e:
            logging.error(f"OS Error: {e}. This might be due to filesystem restrictions.")
            raise

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            raise


    @staticmethod
    def create_archive(source_dir: str, output_file_name: str,archive_format :str='zip') -> str:
        return shutil.make_archive(output_file_name, archive_format , source_dir)

    @staticmethod
    def create_zip(source_dir, output_archive):
        with zipfile.ZipFile(output_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)


    def create_tar(source_dir, output_archive, compression='gz'):  # 'gz' for .tar.gz, 'bz2' for .tar.bz2
        mode = f"w:{compression}" if compression else "w"
        with tarfile.open(output_archive, mode) as tar:
            tar.add(source_dir, arcname='.')

    @staticmethod
    def extract_archive(archive_path, extract_to):
        if archive_path.endswith(".zip"):
            # Handle ZIP archives
            with zipfile.ZipFile(archive_path, 'r') as zipf:
                zipf.extractall(extract_to)
        elif archive_path.endswith(".tar.gz") or archive_path.endswith(".tgz"):
            # Handle TAR.GZ archives
            with tarfile.open(archive_path, 'r:gz') as tarf:
                tarf.extractall(extract_to)
        elif archive_path.endswith(".tar.bz2"):
            # Handle TAR.BZ2 archives
            with tarfile.open(archive_path, 'r:bz2') as tarf:
                tarf.extractall(extract_to)
        elif archive_path.endswith(".tar"):
            # Handle plain TAR archives
            with tarfile.open(archive_path, 'r') as tarf:
                tarf.extractall(extract_to)
        else:
            raise ValueError(f"Unsupported archive format: {archive_path}")