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
from services.mrc_image_service import MrcImageService

logger = logging.getLogger(__name__)



class ImportError(Exception):
    """Base exception for all import-related errors"""
    pass

class TaskError(ImportError):
    """Exception for task processing errors"""
    pass

class DatabaseError(ImportError):
    """Exception for database operation errors"""
    pass

class FileError(ImportError):
    """Exception for file operation errors"""
    pass


class BaseImporter(ABC):
    """
    Abstract base class for all importers. Defines the core structure and pipeline
    for importing microscopy data into the system.
    """

    def __init__(self):
        self.params: Optional[ImportJobBase] = None
        self.db_session: Optional[Session] = None
        self.project: Optional[Project] = None
        self.msession: Optional[Msession] = None
        self.job: Optional[ImageJob] = None
        self.mrc_service = MrcImageService()
        self.image_dict: Dict[str, uuid.UUID] = {}
        self.image_list: List[Image] = []
        self.job_task_list: List[ImageJobTask] = []

    def setup(self, input_data: ImportJobBase) -> None:
        """Initialize the importer with basic parameters"""
        self.params = input_data

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
            self.db_session = db_session
            self.setup_data()

            # Database initialization
            self._init_database_records()

            # Data processing
            imported_data = self.import_data()
            self.process_imported_data()

            # File processing
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
            if self.params.magellon_project_name:
                self.project = self._get_or_create_project()

            if self.params.magellon_session_name or self.params.session_name:
                self.msession = self._get_or_create_session()

            self._create_job_record()
        except Exception as e:
            raise DatabaseError(f"Database initialization failed: {str(e)}")



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



    def _create_job_record(self) -> None:
        """Create the main job record"""
        self.job = ImageJob(
            oid=uuid.uuid4(),
            name=f"Import: {self.params.session_name}",
            description=f"Import job for session: {self.params.session_name}",
            created_date=datetime.now(),
            msession_id=self.msession.oid if self.msession else None,
            status_id=1
        )
        self.db_session.add(self.job)
        self.db_session.commit()
        self.db_session.refresh(self.job)

    def run_job(self):
        """Process all files according to the pipeline"""
        self._create_directories()

        for task in self.get_image_tasks():
            try:
                self.run_task(task)
            except Exception as e:
                logger.error(f"Failed to process task {task.task_id}: {str(e)}")



    def create_image_record(self, image_data: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> Image:
        """Create an Image record from provided data"""
        properties = {
            "oid": uuid.uuid4(),
            "created_date": datetime.now(),
            "session_id": session_id
        }

        # Map all existing properties
        field_mapping = {
            "name", "path", "magnification", "defocus", "dose", "pixel_size",
            "binning_x", "binning_y", "stage_x", "stage_y", "stage_alpha_tilt",
            "atlas_dimxy", "atlas_delta_row", "atlas_delta_column", "level",
            "previous_id", "acceleration_voltage", "spherical_aberration",
            "parent_id", "dimension_x", "dimension_y", "exposure_time",
            "frame_count"
        }

        properties.update({
            field: image_data[field]
            for field in field_mapping
            if field in image_data
        })

        return Image(**properties)



    def create_job_task(self, job_id: uuid.UUID, image_id: uuid.UUID,
                        frame_data: Dict[str, str], image_paths: Dict[str, str]) -> ImageJobTask:
        """Create a job task record"""
        properties = {
            "oid": uuid.uuid4(),
            "job_id": job_id,
            "image_id": image_id,
            "status_id": 1,
            "stage": 0
        }

        if frame_data:
            properties.update({
                key: value for key, value in frame_data.items()
                if key in ["frame_name", "frame_path"]
            })

        if image_paths:
            properties.update({
                key: value for key, value in image_paths.items()
                if key in ["image_name", "image_path"]
            })

        return ImageJobTask(**properties)


    def _process_files(self) -> None:
        """Process all files"""
        try:
            self._create_directories()
            for task in self.get_image_tasks():
                self._process_task(task)
        except Exception as e:
            raise FileError(f"File processing failed: {str(e)}")

    def _create_directories(self) -> None:
        """Create required directories"""
        try:
            for subdir in [
                "", ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, FFT_SUB_URL,
                IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ATLAS_SUB_URL, CTF_SUB_URL
            ]:
                path = os.path.join(self.params.target_directory, subdir)
                create_directory(path)
        except Exception as e:
            raise FileError(f"Failed to create directories: {str(e)}")

    def _process_task(self, task: Any) -> None:
        """Process a single task"""
        try:
            self._transfer_frame(task)
            if getattr(task.job_dto, 'copy_images', False):
                self._copy_image(task)
            self._process_image(task)
        except Exception as e:
            raise TaskError(f"Task processing failed: {str(e)}")

    def _transfer_frame(self, task: Any) -> None:
        """Transfer frame file if it exists"""
        if hasattr(task, 'frame_name') and task.frame_name:
            source = os.path.join(self.params.camera_directory, task.frame_name)
            if os.path.exists(source):
                target = os.path.join(
                    task.job_dto.target_directory,
                    FRAMES_SUB_URL,
                    f"{task.file_name}{FRAMES_SUFFIX}{os.path.splitext(task.frame_name)[1]}"
                )
                copy_file(source, target)

    def _copy_image(self, task: Any) -> None:
        """Copy image file"""
        target = os.path.join(
            task.job_dto.target_directory,
            ORIGINAL_IMAGES_SUB_URL,
            task.image_name
        )
        copy_file(task.image_path, target)
        task.image_path = target

    def _process_image(self, task: Any) -> None:
        """Process image file"""
        self.mrc_service.convert_mrc_to_png(
            abs_file_path=task.image_path,
            out_dir=task.job_dto.target_directory
        )

        fft_path = os.path.join(
            task.job_dto.target_directory,
            FFT_SUB_URL,
            f"{os.path.splitext(os.path.basename(task.image_path))[0]}{FFT_SUFFIX}"
        )
        self.mrc_service.compute_mrc_fft(
            mrc_abs_path=task.image_path,
            abs_out_file_name=fft_path
        )

        if hasattr(task, 'pixel_size') and (task.pixel_size * 10 ** 10) <= 5:
            dispatch_ctf_task(task.task_id, task.image_path, task)
