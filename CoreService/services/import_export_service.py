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
    def create_archives_directory() -> str:
        """
        Ensure archives directory exists.

        Returns:
            str: Path to the archives directory
        """
        archives_dir = os.path.join(os.getcwd(), 'archives')
        os.makedirs(archives_dir, exist_ok=True)
        return archives_dir

    @staticmethod
    def import_files(
        files: List[UploadFile], 
        destination_dir: Optional[str] = None
    ) -> List[str]:
        """
        Import uploaded files to a specified or generated temporary directory.

        Args:
            files (List[UploadFile]): List of files to import
            destination_dir (str, optional): Directory to save files. 
                                             Creates a new temp dir if not provided.

        Returns:
            List[str]: Paths of saved files
        """
        if not destination_dir:
            destination_dir = ImportExportService.create_temp_directory()

        saved_files = []
        for uploaded_file in files:
            # Sanitize filename to prevent directory traversal
            safe_filename = uploaded_file.filename.replace('..', '').replace('/', '_')
            file_path = os.path.join(destination_dir, safe_filename)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
            saved_files.append(file_path)

        return saved_files

    @staticmethod
    def export_archive(
        source_paths: Union[str, List[str]], 
        archive_name: Optional[str] = None, 
        extension: str = '.mag'
    ) -> str:
        """
        Create a 7-Zip archive from specified files/directories.

        Args:
            source_paths (str or List[str]): Paths to files/directories to archive
            archive_name (str, optional): Name of the archive. 
                                          Uses UUID if not provided.
            extension (str, optional): Archive file extension

        Returns:
            str: Path to the created archive
        """
        # Ensure source_paths is a list
        if isinstance(source_paths, str):
            source_paths = [source_paths]

        # Create a unique directory with UUID
        temp_dir = ImportExportService.create_temp_directory()
        archives_dir = ImportExportService.create_archives_directory()

        try:
            # Copy files and directories to the temp directory
            for source in source_paths:
                source = os.path.abspath(source)
                dest = os.path.join(temp_dir, os.path.basename(source))
                
                if os.path.isdir(source):
                    shutil.copytree(source, dest)
                elif os.path.isfile(source):
                    shutil.copy2(source, dest)
                else:
                    print(f"Warning: {source} not found and will be skipped.")

            # Generate archive name if not provided
            if not archive_name:
                archive_name = str(uuid.uuid4())

            # Ensure archive name has the right extension
            if not archive_name.endswith(extension):
                archive_name += extension
            
            # Create 7-Zip archive
            archive_path = os.path.join(archives_dir, archive_name)

            with py7zr.SevenZipFile(archive_path, 'w') as archive:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        archive.write(file_path, arcname=arcname)
            
            # Remove temporary directory after archiving
            shutil.rmtree(temp_dir)
            
            return archive_path

        except Exception as e:
            # Cleanup in case of error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def extract_archive(
        archive_path: str, 
        extract_path: Optional[str] = None
    ) -> str:
        """
        Extract a 7-Zip archive to a specified or generated directory.

        Args:
            archive_path (str): Path to the archive file
            extract_path (str, optional): Directory to extract to. 
                                          Creates a new temp dir if not provided.

        Returns:
            str: Path to the extraction directory
        """
        if not extract_path:
            extract_path = ImportExportService.create_temp_directory()

        try:
            with py7zr.SevenZipFile(archive_path, mode='r') as z:
                z.extractall(path=extract_path)
            
            return extract_path

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def list_archives() -> List[str]:
        """
        List all available archives.

        Returns:
            List[str]: Names of available archives
        """
        archives_dir = ImportExportService.create_archives_directory()
        return [f for f in os.listdir(archives_dir) if f.endswith('.mag')]

    @staticmethod
    def delete_archive(archive_name: str) -> bool:
        """
        Delete a specific archive.

        Args:
            archive_name (str): Name of the archive to delete

        Returns:
            bool: True if deletion successful, False otherwise
        """
        archives_dir = ImportExportService.create_archives_directory()
        archive_path = os.path.join(archives_dir, archive_name)
        
        if os.path.exists(archive_path):
            os.remove(archive_path)
            return True
        return False

    @staticmethod
    def get_archive_path(archive_name: str) -> str:
        """
        Get the full path of a specific archive.

        Args:
            archive_name (str): Name of the archive

        Returns:
            str: Full path to the archive
        """
        archives_dir = ImportExportService.create_archives_directory()
        archive_path = os.path.join(archives_dir, archive_name)
        
        if not os.path.exists(archive_path):
            raise HTTPException(status_code=404, detail="Archive not found")
        
        return archive_path
