from datetime import datetime
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List

from fastapi import Depends
from sqlalchemy.orm import Session

from core.helper import create_directory, dispatch_ctf_task
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, ATLAS_SUB_URL, CTF_SUB_URL
from database import get_db
from models.pydantic_models import ImportJobBase
from models.sqlalchemy_models import Project, Msession, ImageJob
import logging

from services.mrc_image_service import MrcImageService

logger = logging.getLogger(__name__)


class TaskFailedException(Exception):
    pass

class ImportException(Exception):
    """Base exception for import operations"""
    pass

class DatabaseOperationException(ImportException):
    """Exception for database-related operations"""
    pass

class FileOperationException(ImportException):
    """Exception for file system operations"""
    pass


class BaseImporter(ABC):
    """
    Abstract base class for all importers. Defines the core structure and pipeline
    for importing microscopy data into the system.
    """

    def __init__(self):
        self.params: Optional[ImportJobBase] = None
        self.db_session: Optional[Session] = None
        self.job: Optional[ImageJob] = None
        self.project: Optional[Project] = None
        self.msession: Optional[Msession] = None
        self.mrc_service = MrcImageService()


    def setup(self, input_data: ImportJobBase):
        """Initialize the importer with basic parameters"""
        self.params = input_data

    @abstractmethod
    def setup_data(self, input_data: Any):
        """
        Initialize importer with type-specific parameters.
        Each importer implementation should define its own parameter type.
        """
        pass



    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, Any]:
        """
        Main processing pipeline that orchestrates the import process.
        """
        try:
            self.db_session = db_session

            # Database pipeline
            self._create_project_and_session()
            self._create_job_record()

            # Data pipeline
            imported_data = self.import_data()
            self.process_imported_data()

            # File processing pipeline
            if self.params.if_do_subtasks:
                self._process_files()

            return {
                'status': 'success',
                'message': 'Import completed successfully.',
                'job_id': self.params.job_id
            }

        except DatabaseOperationException as e:
            logger.error(f"Database operation failed: {str(e)}")
            return {'status': 'failure', 'message': f'Database operation failed: {str(e)}'}
        except FileOperationException as e:
            logger.error(f"File operation failed: {str(e)}")
            return {'status': 'failure', 'message': f'File operation failed: {str(e)}'}
        except Exception as e:
            logger.error(f"Import failed: {str(e)}")
            return {'status': 'failure', 'message': f'Import failed: {str(e)}'}
    def _create_project_and_session(self):
        """Create or get project and session records"""
        try:
            if self.params.magellon_project_name:
                self.project = self._get_or_create_project()

            if self.params.magellon_session_name or self.params.session_name:
                self.msession = self._get_or_create_session()

        except Exception as e:
            raise DatabaseOperationException(f"Failed to create project/session: {str(e)}")

    def _get_or_create_project(self) -> Project:
        """Get existing project or create new one"""
        project = self.db_session.query(Project).filter(
            Project.name == self.params.magellon_project_name
        ).first()

        if not project:
            project = Project(
                oid=uuid.uuid4(),
                name=self.params.magellon_project_name,
                created_date=datetime.now()
            )
            self.db_session.add(project)
            self.db_session.commit()
            self.db_session.refresh(project)

        return project

    def _get_or_create_session(self) -> Msession:
        """Get existing session or create new one"""
        session_name = self.params.magellon_session_name or self.params.session_name

        session = self.db_session.query(Msession).filter(
            Msession.name == session_name
        ).first()

        if not session:
            session = Msession(
                oid=uuid.uuid4(),
                name=session_name,
                project_id=self.project.oid if self.project else None,
                created_date=datetime.now()
            )
            self.db_session.add(session)
            self.db_session.commit()
            self.db_session.refresh(session)

        return session


    def _create_job_record(self):
        """Create the main job record"""
        try:
            self.job = ImageJob(
                oid=uuid.uuid4(),
                name=f"Import: {self.params.session_name}",
                description=f"Import job for session: {self.params.session_name}",
                created_date=datetime.now(),
                msession_id=self.msession.oid if self.msession else None,
                status_id=1  # Initial status
            )
            self.db_session.add(self.job)
            self.db_session.commit()
            self.db_session.refresh(self.job)

        except Exception as e:
            raise DatabaseOperationException(f"Failed to create job record: {str(e)}")

    def _process_files(self):
        """Process all files according to the pipeline"""
        self._create_directories()

        for task in self.get_image_tasks():
            try:
                self._process_single_file(task)
            except Exception as e:
                logger.error(f"Failed to process task {task.task_id}: {str(e)}")

    def _create_directories(self):
        """Create necessary directory structure"""
        try:
            directories = [
                self.params.target_directory,
                os.path.join(self.params.target_directory, ORIGINAL_IMAGES_SUB_URL),
                os.path.join(self.params.target_directory, FRAMES_SUB_URL),
                os.path.join(self.params.target_directory, FFT_SUB_URL),
                os.path.join(self.params.target_directory, IMAGE_SUB_URL),
                os.path.join(self.params.target_directory, THUMBNAILS_SUB_URL),
                os.path.join(self.params.target_directory, ATLAS_SUB_URL),
                os.path.join(self.params.target_directory, CTF_SUB_URL)
            ]

            for directory in directories:
                create_directory(directory)

        except Exception as e:
            raise FileOperationException(f"Failed to create directories: {str(e)}")



    def _process_single_file(self, task):
        """Process a single file through all required steps"""
        try:
            self._convert_to_png(task)
            self._compute_fft(task)
            self._compute_ctf(task)
        except Exception as e:
            logger.error(f"Failed to process file {task.image_path}: {str(e)}")
            raise FileOperationException(f"File processing failed: {str(e)}")

    def _convert_to_png(self, task):
        """Convert image to PNG format"""
        self.mrc_service.convert_mrc_to_png(
            abs_file_path=task.image_path,
            out_dir=self.params.target_directory
        )

    def _compute_fft(self, task):
        """Compute FFT for the image"""
        fft_path = os.path.join(
            self.params.target_directory,
            FFT_SUB_URL,
            f"{os.path.splitext(os.path.basename(task.image_path))[0]}{FFT_SUFFIX}"
        )
        self.mrc_service.compute_mrc_fft(
            mrc_abs_path=task.image_path,
            abs_out_file_name=fft_path
        )

    def _compute_ctf(self, task):
        """Compute CTF if pixel size is appropriate"""
        if hasattr(task, 'pixel_size') and (task.pixel_size * 10 ** 10) <= 5:
            dispatch_ctf_task(task.task_id, task.image_path, task)

    @abstractmethod
    def import_data(self) -> Dict[str, Any]:
        """Import data from source system"""
        pass

    @abstractmethod
    def process_imported_data(self):
        """Process the imported data"""
        pass

    @abstractmethod
    def get_image_tasks(self) -> List[Any]:
        """Get list of image processing tasks"""
        pass