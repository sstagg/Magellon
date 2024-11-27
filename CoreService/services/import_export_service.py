import os
import shutil
import uuid
import py7zr
from typing import List, Union, Optional, Tuple, Any
from fastapi import UploadFile, HTTPException

class ImportExportService:
    """
    Service class for handling file imports, exports, and archiving.
    Provides core functionality for file management operations.
    """

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
    def create_archive(base_dir: str, output_file_name: str) -> str:
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


