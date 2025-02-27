from datetime import datetime
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session


from database import get_db
from models.sqlalchemy_models import Project, Msession, ImageJob, ImageJobTask, Image
import logging

from services.importers.import_database_service import ImportDatabaseService
from services.importers.import_file_service import ImportFileService, TaskError, FileError
from services.mrc_image_service import MrcImageService

logger = logging.getLogger(__name__)


class ImportError(Exception):
    """Base exception for all import-related errors"""
    pass


class DatabaseError(ImportError):
    """Exception for database operation errors"""
    pass

class FileError(ImportError):
    """Exception for file operation errors"""
    pass

class TaskFailedException(Exception):
    pass

class BaseImporter(ABC):
    """
       Abstract base class for all importers

       This class provides common functionality for all import processes, including:
       - Database operations (project, session, job management)
       - Directory structure creation
       - File processing (convert to PNG, compute FFT, dispatch CTF and motion correction)
       - Task management

       Concrete importers should override the abstract methods to implement their specific logic.
       """

    def __init__(self):
        self.params: Optional[BaseModel] = None
        self.db_project: Optional[Project] = None
        self.db_msession: Optional[Msession] = None
        self.db_job: Optional[ImageJob] = None

        self.db_service: Optional[ImportDatabaseService] = None

        self.file_service: Optional[ImportFileService] = None

        self.image_dict: Dict[str, uuid.UUID] = {}
        self.db_image_list: List[Image] = []
        self.db_job_task_list: List[ImageJobTask] = []
        self.task_dto_list: Optional[List] = []

        self.mrc_service = MrcImageService()

    def setup(self,input_data: BaseModel,  db_session: Session = Depends(get_db)) -> None:
        """Initialize the importer with basic parameters"""
        self.params = input_data
        self.file_service = ImportFileService(target_directory= None, camera_directory= None  )
        self.db_service = ImportDatabaseService(db_session)

    @abstractmethod
    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        """
        Main entry point for the import process

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Dict with status and result information
        """
        pass



    def _init_database_records(self) -> None:
        """Initialize all necessary database records"""
        try:
            self.db_project, self.db_msession, self.db_job = self.db_service.initialize_import_records(self.params)
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {str(e)}")


    def _process_files(self) -> None:
        """Process all files using the file service"""
        try:
            self.file_service.create_required_directories()
            for task in self.params.task_list:
                self.file_service.process_task(
                    task,
                    copy_images=getattr(task.job_dto, 'copy_images', False)
                )
        except (FileError, TaskError) as e:
            raise ImportError(str(e))
