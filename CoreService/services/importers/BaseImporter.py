from datetime import datetime
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List

from fastapi import Depends
from sqlalchemy.orm import Session

from core.helper import create_directory, dispatch_ctf_task
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, ATLAS_SUB_URL, CTF_SUB_URL, FRAMES_SUFFIX

from database import get_db
from models.pydantic_models import ImportJobBase
from models.sqlalchemy_models import Project, Msession, ImageJob, ImageJobTask, Image
import logging

from services.file_service import copy_file
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

class BaseImporter(ABC):
    """Abstract base class for all importers"""

    def __init__(self):
        self.params: Optional[ImportJobBase] = None
        self.db_service: Optional[ImportDatabaseService] = None
        self.file_service: Optional[ImportFileService] = None
        self.project: Optional[Project] = None
        self.msession: Optional[Msession] = None
        self.job: Optional[ImageJob] = None
        self.image_dict: Dict[str, uuid.UUID] = {}
        self.image_list: List[Image] = []
        self.job_task_list: List[ImageJobTask] = []

    def setup(self, input_data: ImportJobBase) -> None:
        """Initialize the importer with basic parameters"""
        self.params = input_data
        self.file_service = ImportFileService(
            target_directory=input_data.target_directory,
            camera_directory=input_data.camera_directory
        )

    @abstractmethod
    def setup_data(self) -> None:
        """Initialize importer with type-specific parameters"""
        pass

    @abstractmethod
    def import_data(self) -> Dict[str, Any]:
        """Import data from source system"""
        pass

    @abstractmethod
    def process_imported_data(self) -> None:
        """Process the imported data"""
        pass

    @abstractmethod
    def get_image_tasks(self) -> List[Any]:
        """Get list of image processing tasks"""
        pass

    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        """Main processing pipeline"""
        try:
            self.db_service = ImportDatabaseService(db_session)

            # Initialize data and database records
            self.setup_data()
            self._init_database_records()

            # Process data
            imported_data = self.import_data()
            self.process_imported_data()

            # Process files if required
            if getattr(self.params, 'if_do_subtasks', True):
                self._process_files()

            return {
                'status': 'success',
                'message': 'Import completed successfully.',
                'job_id': self.params.job_id
            }
        except ImportError as e:
            logger.error(f"Import failed: {str(e)}")
            return {'status': 'failure', 'message': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return {'status': 'failure', 'message': f'Unexpected error: {str(e)}'}

    def _init_database_records(self) -> None:
        """Initialize all necessary database records"""
        try:
            self.project, self.msession, self.job = self.db_service.initialize_import_records(self.params)
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {str(e)}")

    def _process_files(self) -> None:
        """Process all files using the file service"""
        try:
            self.file_service.create_required_directories()
            for task in self.get_image_tasks():
                self.file_service.process_task(
                    task,
                    copy_images=getattr(task.job_dto, 'copy_images', False)
                )
        except (FileError, TaskError) as e:
            raise ImportError(str(e))
