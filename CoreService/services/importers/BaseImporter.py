from datetime import datetime
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List, Tuple

from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX, app_settings, ATLAS_SUB_URL, CTF_SUB_URL, FAO_SUB_URL, MAGELLON_HOME_DIR, GAINS_SUB_URL

from database import get_db
from models.sqlalchemy_models import Project, Msession, ImageJob, ImageJobTask, Image, Atlas

import logging

from core.helper import dispatch_ctf_task, dispatch_motioncor_task, custom_replace, create_directory

from services.importers.import_database_service import ImportDatabaseService
from services.importers.import_file_service import ImportFileService, TaskError, FileError
from services.mrc_image_service import MrcImageService
from services.file_service import copy_file, check_file_exists

from services.job_manager import JobManager, JobStatus

logger = logging.getLogger(__name__)

# Exception for cancellation
class CancellationRequested(Exception):
    """Raised when job cancellation is detected"""
    pass

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

        # Add job manager
        self.job_manager = JobManager()
        self.job_id = None


    def setup(self,input_data: BaseModel,  db_session: Session = Depends(get_db)) -> None:
        """Initialize the importer with basic parameters"""
        self.params = input_data
        self.file_service = ImportFileService(target_directory= None, camera_directory= None  )
        self.db_service = ImportDatabaseService(db_session)

        # Set job ID if provided
        if hasattr(self.params, 'job_id') and self.params.job_id:
            self.job_id = str(self.params.job_id)
            

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

    def upsert_project(self, db_session: Session, project_name: str) -> Optional[Project]:
        """
        Create or update project record

        Args:
            db_session: SQLAlchemy database session
            project_name: Name of the project

        Returns:
            Project instance or None if project_name is None
        """
        if not project_name:
            return None

        project = db_session.query(Project).filter(  Project.name == project_name ).first()

        if not project:
            project = Project(
                oid=uuid.uuid4(),
                name=project_name,
                last_accessed_date=datetime.now()
            )
            db_session.add(project)
            db_session.flush()

        return project

    def upsert_session(self, db_session: Session, session_name: str, project_id: Optional[uuid.UUID] = None) -> Msession:
        """
        Create or update session record

        Args:
            db_session: SQLAlchemy database session
            session_name: Name of the session
            project_id: Optional project ID to associate with session

        Returns:
            Msession instance
        """
        if not session_name:
            raise ValueError("Session name must be provided")

        session = db_session.query(Msession).filter(
            Msession.name == session_name
        ).first()

        if not session:
            session = Msession(
                oid=uuid.uuid4(),
                name=session_name,
                project_id=project_id,
                last_accessed_date=datetime.now()
            )
            db_session.add(session)
            db_session.flush()

        return session

    def create_job_record(self, db_session: Session, session_id: uuid.UUID, job_name: str,
                          description: str = None, output_directory: str = None) -> ImageJob:
        """
        Create job record for the import process

        Args:
            db_session: SQLAlchemy database session
            session_id: Session ID to associate with this job
            job_name: Name of the job
            description: Optional job description
            output_directory: Optional output directory

        Returns:
            ImageJob instance
        """
        if not session_id:
            raise ValueError("Session ID must be provided")

        job = ImageJob(
            oid=uuid.uuid4(),
            name=job_name,
            description=description or f"Import job: {job_name}",
            created_date=datetime.now(),
            msession_id=session_id,
            output_directory=output_directory,
            status_id=1,  # Pending status
            type_id=1     # Import type
        )
        db_session.add(job)
        db_session.flush()
        return job


    def initialize_db_records(self, db_session: Session, project_name: str, session_name: str,
                              job_type: str = "Import") -> Tuple[Optional[Project], Msession, ImageJob]:
        """
        Initialize database records needed for import

        Creates or retrieves project and session records, and creates a new job record.

        Args:
            db_session: SQLAlchemy database session
            project_name: Name of the project
            session_name: Name of the session
            job_type: Type of job (prefix for job name)

        Returns:
            Tuple of (Project, Msession, ImageJob)
        """
        try:
            self.db_project = self.upsert_project(db_session, project_name)
            project_id = self.db_project.oid if self.db_project else None

            self.db_msession = self.upsert_session(db_session, session_name, project_id)

            job_name = f"{job_type} Import: {session_name}"
            description = f"{job_type} Import for session: {session_name}"

            target_dir = None
            if hasattr(self.params, 'target_directory') and self.params.target_directory:
                target_dir = self.params.target_directory
            elif hasattr(self.params, 'camera_directory') and self.params.camera_directory:
                target_dir = self.params.camera_directory

            self.db_job = self.create_job_record(
                db_session,
                self.db_msession.oid,
                job_name,
                description,
                target_dir
            )

            return self.db_project, self.db_msession, self.db_job

        except Exception as e:
            db_session.rollback()
            raise DatabaseError(f"Failed to initialize database records: {str(e)}")



    def create_directories(self, target_dir: str = None) -> None:
        """
        Create necessary directory structure for import

        Args:
            target_dir: Target directory path, if None uses target_directory from params
        """
        if not target_dir:
            if hasattr(self.params, 'target_directory') and self.params.target_directory:
                target_dir = self.params.target_directory
            else:
                # Default to session directory in MAGELLON_HOME_DIR
                session_name = self.get_session_name()
                if session_name:
                    target_dir = os.path.join(MAGELLON_HOME_DIR, session_name.lower())
                else:
                    raise ValueError("No target directory specified")

        create_directory(target_dir)
        create_directory(os.path.join(target_dir, ORIGINAL_IMAGES_SUB_URL))
        create_directory(os.path.join(target_dir, FRAMES_SUB_URL))
        create_directory(os.path.join(target_dir, FFT_SUB_URL))
        create_directory(os.path.join(target_dir, IMAGE_SUB_URL))
        create_directory(os.path.join(target_dir, THUMBNAILS_SUB_URL))
        create_directory(os.path.join(target_dir, ATLAS_SUB_URL))
        create_directory(os.path.join(target_dir, CTF_SUB_URL))
        create_directory(os.path.join(target_dir, GAINS_SUB_URL))
        create_directory(os.path.join(target_dir, FAO_SUB_URL))

    def get_session_name(self) -> Optional[str]:
        """
        Get session name from params

        Returns:
            Session name or None if not found
        """
        if hasattr(self.params, 'magellon_session_name') and self.params.magellon_session_name:
            return self.params.magellon_session_name
        if hasattr(self.params, 'session_name') and self.params.session_name:
            return self.params.session_name
        return None

    def transfer_frame(self, task_dto: Any) -> None:
        """
        Transfer frame file to target directory

        Args:
            task_dto: Task data transfer object
        """
        try:
            # Handle different DTO structures
            if hasattr(task_dto, 'frame_name') and task_dto.frame_name and hasattr(task_dto, 'frame_path') and task_dto.frame_path:
                # Source frame path is directly specified
                frame_path = task_dto.frame_path
                if not os.path.exists(frame_path):
                    logger.warning(f"Frame path does not exist: {frame_path}")
                    return
            elif hasattr(task_dto, 'frame_name') and task_dto.frame_name and hasattr(self.params, 'camera_directory'):
                # Need to find frame in camera directory
                frame_path = check_file_exists(self.params.camera_directory, task_dto.frame_name)
                if not frame_path:
                    logger.warning(f"Frame file not found: {task_dto.frame_name}")
                    return
            else:
                # No frame to transfer
                return

            # Get target path
            target_directory = self.get_target_directory()
            _, file_extension = os.path.splitext(frame_path)

            if hasattr(task_dto, 'file_name'):
                target_path = os.path.join(
                    target_directory,
                    FRAMES_SUB_URL,
                    f"{task_dto.file_name}{FRAMES_SUFFIX}{file_extension}"
                )
            else:
                # Use frame name as base name if file_name not available
                target_path = os.path.join(
                    target_directory,
                    FRAMES_SUB_URL,
                    f"{os.path.splitext(os.path.basename(frame_path))[0]}{file_extension}"
                )

            # Copy the file
            copy_file(frame_path, target_path)

        except Exception as e:
            logger.error(f"Error transferring frame: {str(e)}")
            raise FileError(f"Failed to transfer frame: {str(e)}")

    def copy_image(self, task_dto: Any) -> None:
        """
        Copy original image to target directory

        Args:
            task_dto: Task data transfer object
        """
        try:
            # Check if image path exists
            if not hasattr(task_dto, 'image_path') or not task_dto.image_path:
                logger.warning("No image path specified for copying")
                return

            if not os.path.exists(task_dto.image_path):
                logger.warning(f"Image path does not exist: {task_dto.image_path}")
                return

            # Get target path
            target_directory = self.get_target_directory()

            # Determine file name and extension
            if hasattr(task_dto, 'image_name') and task_dto.image_name:
                base_name = task_dto.image_name
            else:
                base_name = os.path.splitext(os.path.basename(task_dto.image_path))[0]

            # Get file extension from source
            _, file_extension = os.path.splitext(task_dto.image_path)

            target_path = os.path.join(
                target_directory,
                ORIGINAL_IMAGES_SUB_URL,
                f"{base_name}{file_extension}"
            )

            # Copy the file
            copy_file(task_dto.image_path, target_path)

            # Update task DTO with new path
            task_dto.image_path = target_path

        except Exception as e:
            logger.error(f"Error copying image: {str(e)}")
            raise FileError(f"Failed to copy image: {str(e)}")

    def convert_image_to_png(self, abs_file_path: str, out_dir: str = None) -> dict:
        """
        Convert image to PNG format

        Args:
            abs_file_path: Absolute path to source image
            out_dir: Output directory, if None uses target_directory

        Returns:
            Dict with status message
        """
        try:
            if not out_dir:
                out_dir = self.get_target_directory()

            # Determine file type by extension
            _, ext = os.path.splitext(abs_file_path)
            ext = ext.lower()

            if ext in ['.mrc', '.mrcs']:
                # MRC file
                self.mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
                return {"message": "MRC file successfully converted to PNG"}
            elif ext in ['.tif', '.tiff']:
                # TIFF file
                self.mrc_service.convert_tiff_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
                return {"message": "TIFF file successfully converted to PNG"}
            else:
                raise ValueError(f"Unsupported file format: {ext}")

        except Exception as e:
            logger.error(f"Error converting image to PNG: {str(e)}")
            return {"error": str(e)}

    def compute_fft(self, abs_file_path: str, out_dir: str = None) -> dict:
        """
        Compute FFT for an image

        Args:
            abs_file_path: Absolute path to source image
            out_dir: Output directory, if None uses target_directory

        Returns:
            Dict with status message
        """
        try:
            if not out_dir:
                out_dir = self.get_target_directory()

            # Create FFT output path
            fft_path = os.path.join(
                out_dir,
                FFT_SUB_URL,
                f"{os.path.splitext(os.path.basename(abs_file_path))[0]}{FFT_SUFFIX}"
            )

            # Determine file type by extension
            _, ext = os.path.splitext(abs_file_path)
            ext = ext.lower()

            if ext in ['.mrc', '.mrcs']:
                # MRC file
                self.mrc_service.compute_mrc_fft(mrc_abs_path=abs_file_path, abs_out_file_name=fft_path)
                return {"message": "MRC file FFT computed successfully"}
            elif ext in ['.tif', '.tiff']:
                # TIFF file
                self.mrc_service.compute_tiff_fft(tiff_abs_path=abs_file_path, abs_out_file_name=fft_path)
                return {"message": "TIFF file FFT computed successfully"}
            else:
                raise ValueError(f"Unsupported file format for FFT: {ext}")

        except Exception as e:
            logger.error(f"Error computing FFT: {str(e)}")
            return {"error": str(e)}

    def compute_ctf(self, abs_file_path: str, task_dto: Any) -> dict:
        """
        Dispatch CTF computation task

        Args:
            abs_file_path: Absolute path to source image
            task_dto: Task data transfer object

        Returns:
            Dict with status message
        """
        try:
            # Check pixel size threshold
            pixel_size = getattr(task_dto, 'pixel_size', None)
            if not pixel_size:
                logger.warning("No pixel size available for CTF computation")
                return {"message": "Skipping CTF computation (no pixel size)"}

            if pixel_size * 10**10 > 5:
                logger.info(f"Pixel size {pixel_size} too large for CTF computation")
                return {"message": "Skipping CTF computation (pixel size too large)"}

            # Dispatch CTF task
            task_id = getattr(task_dto, 'task_id', uuid.uuid4())
            dispatch_ctf_task(task_id, abs_file_path, task_dto)
            return {"message": f"CTF computation dispatched for {abs_file_path}"}

        except Exception as e:
            logger.error(f"Error dispatching CTF computation: {str(e)}")
            return {"error": str(e)}

    def compute_motioncor(self, abs_file_path: str, task_dto: Any, gain_path: str = None) -> dict:
        """
        Dispatch motion correction task

        Args:
            abs_file_path: Absolute path to source image
            task_dto: Task data transfer object
            gain_path: Optional path to gain reference file

        Returns:
            Dict with status message
        """
        try:
            # Check if frame exists
            frame_name = getattr(task_dto, 'frame_name', None)
            if not frame_name:
                logger.info("No frame available for motion correction")
                return {"message": "Skipping motion correction (no frame)"}

            # Setup motioncor settings
            settings = {
                'FmDose': 1.0,
                'PatchesX': 7,
                'PatchesY': 7,
                'Group': 4
            }

            # Find gain reference if not provided
            if not gain_path:
                gain_path = self._find_gain_reference()

            # if not gain_path:
            #     logger.warning("No gain reference found for motion correction")
            #     return {"message": "Skipping motion correction (no gain reference)"}

            # Ensure file extension for full_image_path
            if not abs_file_path.endswith('.tif'):
                full_image_path = f"{abs_file_path}.tif"
            else:
                full_image_path = abs_file_path

            # Dispatch motion correction task
            task_id = getattr(task_dto, 'task_id', uuid.uuid4())
            dispatch_motioncor_task(
                task_id=task_id,
                gain_path=gain_path,
                full_image_path=full_image_path,
                task_dto=task_dto,
                motioncor_settings=settings
            )

            return {"message": f"Motion correction dispatched for {abs_file_path}"}

        except Exception as e:
            logger.error(f"Error dispatching motion correction: {str(e)}")
            return {"error": str(e)}

    def _find_gain_reference(self) -> Optional[str]:
        """
        Find appropriate gain reference file

        Returns:
            Path to gain reference file or None if not found
        """
        target_dir = self.get_target_directory()
        gains_dir = os.path.join(target_dir, GAINS_SUB_URL)

        if os.path.exists(gains_dir):
            gain_files = [f for f in os.listdir(gains_dir) if f.endswith('_gain_multi_ref.tif')]
            if gain_files:
                return os.path.join(gains_dir, sorted(gain_files)[-1])

        return None

    def get_target_directory(self) -> str:
        """
        Get target directory for file operations

        Returns:
            Target directory path

        Raises:
            ValueError: If no target directory is available
        """
        if hasattr(self.params, 'target_directory') and self.params.target_directory:
            return self.params.target_directory

        # Try to use session directory in MAGELLON_HOME_DIR
        session_name = self.get_session_name()
        if session_name:
            return os.path.join(MAGELLON_HOME_DIR, session_name.lower())

        raise ValueError("No target directory specified")

    def process_task(self, task_dto: Any) -> Dict[str, str]:
        """
        Process a single import task

        This method handles the standard file processing operations:
        1. Transfer frame file
        2. Copy original image (optional)
        3. Convert to PNG
        4. Compute FFT
        5. Dispatch CTF computation
        6. Dispatch motion correction

        Args:
            task_dto: Task data transfer object

        Returns:
            Dict with status and message
        """
        try:
            # 1. Transfer frame if it exists
            self.transfer_frame(task_dto)

            # 2. Copy original image if specified
            if hasattr(self.params, 'copy_images') and self.params.copy_images:
                self.copy_image(task_dto)

            # Get current image path
            image_path = getattr(task_dto, 'image_path', None)
            if not image_path or not os.path.exists(image_path):
                raise FileError(f"Image file not found: {image_path}")

            # 3. Convert to PNG
            self.convert_image_to_png(image_path)

            # 4. Compute FFT
            self.compute_fft(image_path)

            # 5. Compute CTF if needed
            self.compute_ctf(image_path, task_dto)

            # 6. Compute motion correction if frame exists
            if hasattr(task_dto, 'frame_name') and task_dto.frame_name:
                self.compute_motioncor(image_path, task_dto)

            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            logger.error(f"Task processing failed: {str(e)}", exc_info=True)
            raise TaskFailedException(f"Failed to process task: {str(e)}")

    def run_tasks(self, task_list: List[Any] = None) -> None:
        """
        Run all processing tasks

        Args:
            task_list: List of task DTOs, if None uses self.task_dto_list
        """
        try:
            tasks = task_list or self.task_dto_list
            if not tasks:
                logger.warning("No tasks to process")
                return

            for task in tasks:
                self.process_task(task)

        except Exception as e:
            logger.error(f"Error running tasks: {str(e)}", exc_info=True)
            raise

    def create_atlas_images(self, db_session: Session, session_id: uuid.UUID = None) -> Dict[str, Any]:
        """
        Create atlas images for a session

        Args:
            db_session: SQLAlchemy database session
            session_id: Session ID, if None uses self.db_msession.oid

        Returns:
            Dict with atlas image information
        """
        try:
            if not session_id and hasattr(self, 'db_msession') and self.db_msession:
                session_id = self.db_msession.oid

            if not session_id:
                logger.warning("No session ID for atlas creation")
                return {"message": "Skipping atlas creation (no session)"}

            # Query to get all atlas-related images for the session
            query = db_session.query(Image).filter(
                Image.session_id == session_id,
                Image.atlas_delta_row.isnot(None),
                Image.atlas_delta_column.isnot(None),
                Image.parent_id.is_(None),
                Image.GCRecord.is_(None)
            ).order_by(Image.name).all()

            if not query:
                logger.warning("No atlas images found for this session")
                return {"message": "No atlas images found"}

            # Group images by grid label
            label_objects = {}
            for image in query:
                # Get grid label (can be customized in subclasses)
                grid_label = self._extract_grid_label(image.name)

                obj = {
                    "id": str(image.oid),
                    "dimx": float(image.atlas_dimxy) if image.atlas_dimxy else 0,
                    "dimy": float(image.atlas_dimxy) if image.atlas_dimxy else 0,
                    "filename": image.name,
                    "delta_row": float(image.atlas_delta_row) if image.atlas_delta_row else 0,
                    "delta_column": float(image.atlas_delta_column) if image.atlas_delta_column else 0
                }

                if grid_label in label_objects:
                    label_objects[grid_label].append(obj)
                else:
                    label_objects[grid_label] = [obj]

            # Get session name
            session = db_session.query(Msession).filter(Msession.oid == session_id).first()
            session_name = session.name if session else "unknown"

            # Create atlas images
            images = self.create_atlas_images(session_name, label_objects)

            # Create atlas records
            atlas_records = []
            for image in images:
                file_name = os.path.basename(image['imageFilePath'])
                file_name_without_extension = os.path.splitext(file_name)[0]
                atlas = Atlas(
                    oid=uuid.uuid4(),
                    name=file_name_without_extension,
                    meta=image['imageMap'],
                    session_id=session_id
                )
                atlas_records.append(atlas)

            db_session.bulk_save_objects(atlas_records)
            db_session.commit()

            return {"images": images, "count": len(atlas_records)}

        except Exception as e:
            logger.error(f"Error creating atlas images: {str(e)}", exc_info=True)
            db_session.rollback()
            raise

    def _extract_grid_label(self, filename: str) -> str:
        """
        Extract grid label from a filename

        Args:
            filename: Image filename

        Returns:
            Grid label string
        """
        # Default implementation - can be overridden in subclasses
        import re
        match = re.search(r'_([a-zA-Z0-9]+)_', filename)
        return match.group(1) if match else "default"


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
