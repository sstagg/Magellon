import json
import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging
from sqlalchemy import text

from core.helper import dispatch_ctf_task, dispatch_motioncor_task
from models.pydantic_models import ImportTaskDto
from models.sqlalchemy_models import Msession, ImageJob, Image, ImageJobTask, Project, Atlas
from services.atlas import create_atlas_images
from services.importers.BaseImporter import BaseImporter, TaskFailedException, FileError
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from config import (FFT_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, ATLAS_SUB_URL, 
                   CTF_SUB_URL, MAGELLON_HOME_DIR, FFT_SUFFIX, GAINS_SUB_URL)

logger = logging.getLogger(__name__)


def extract_grid_label(filename: str) -> str:
    """
    Extracts the grid name from a file name.
    The grid name is assumed to be a substring starting with an underscore and
    containing letters/numbers, followed by another underscore.

    Parameters:
        filename (str): The file name to process.

    Returns:
        str: The extracted grid name, or 'empty' if no grid name is found.
    """
    # Regular expression to match the grid name pattern (e.g., _g4d_)
    match = re.search(r'_([a-zA-Z0-9]+)_', filename)

    # Return the grid name or 'empty' if not found
    return match.group(1) if match else "empty"


class MagellonImporter2(BaseImporter):
    """
    Importer for Magellon archive data.
    
    This importer reads a Magellon archive directory, which includes a session.json file
    containing metadata and a 'home' directory with image data.
    """

    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        """
        Process Magellon import

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Dict with status and result information
        """
        try:
            # Validate session.json exists
            json_path = os.path.join(self.params.source_dir, 'session.json')
            if not os.path.exists(json_path):
                raise HTTPException(status_code=400, detail="Invalid archive structure: session.json not found")

            # Load session data
            with open(json_path, 'r') as f:
                session_data = json.load(f)

            # Process project data
            project_data = session_data.get("project")
            if project_data:
                self.db_project = self._upsert_project(db_session, project_data)

            # Process session data
            session_info = session_data.get("msession")
            if not session_info:
                raise ValueError("Missing session information in session.json")
                
            self.db_msession = self._upsert_session(db_session, session_info, 
                                                  self.db_project.oid if self.db_project else None)

            # Determine target directory
            session_dir = os.path.normpath(os.path.join(MAGELLON_HOME_DIR, self.db_msession.name.lower()))
            
            # Check if session already exists
            if os.path.exists(session_dir):
                return {'status': 'failure', "message": f"This session already exists: {session_dir}"}

            # Create job record
            self.db_job = self.create_job_record(
                db_session,
                self.db_msession.oid,
                f"Import: {self.db_msession.name}",
                f"Import job for session: {self.db_msession.name}"
            )

            db_session.commit()

            # Process images
            images_data = session_data.get("images", [])
            if not images_data:
                logger.warning("No image data found in session.json")
                
            # Create images and job tasks in database
            images_to_process = self.process_images(db_session, images_data)
            db_session.commit()
            
            # Set target directory and create directory structure
            self.file_service.target_directory = session_dir
            self.create_directories(session_dir)

            # Copy original directories from source
            self._copy_source_directories(session_dir)

            # Process each image
            task_list = self._create_task_dtos(images_to_process)
            self.task_dto_list = task_list
            
            # Run processing tasks
            self.run_tasks()
                
            # Create atlas images
            self.create_magellon_atlas(db_session)

            return {
                'status': 'success',
                'message': 'Import completed successfully.',
                'session_name': self.db_msession.name,
                'job_id': str(self.db_job.oid)
            }

        except Exception as e:
            logger.error(f"Magellon import failed: {str(e)}", exc_info=True)
            return {
                'status': 'failure',
                'message': 'Import encountered problem.',
                'session_name': self.db_msession.name if hasattr(self, 'db_msession') else None,
                'error': str(e)
            }

    def _extract_grid_label(self, filename: str) -> str:
        """
        Overridden method to extract grid label from filename
        Uses the imported extract_grid_label function
        """
        return extract_grid_label(filename)

    def _copy_source_directories(self, target_dir: str) -> None:
        """
        Copy required directories from source to target
        
        Args:
            target_dir: Target directory path
        """
        try:
            # Copy original images
            source_original = os.path.join(self.params.source_dir, 'home', ORIGINAL_IMAGES_SUB_URL)
            if os.path.exists(source_original):
                shutil.copytree(source_original, os.path.join(target_dir, ORIGINAL_IMAGES_SUB_URL), dirs_exist_ok=True)

            # Copy gain files
            source_gains = os.path.join(self.params.source_dir, 'home', GAINS_SUB_URL)
            if os.path.exists(source_gains):
                shutil.copytree(source_gains, os.path.join(target_dir, GAINS_SUB_URL), dirs_exist_ok=True)

        except Exception as e:
            logger.error(f"Error copying source directories: {str(e)}")
            raise FileError(f"Failed to copy source directories: {str(e)}")

    def _create_task_dtos(self, images_to_process: List[Tuple[Image, str]]) -> List[ImportTaskDto]:
        """
        Create task DTOs for image processing
        
        Args:
            images_to_process: List of (Image, file_path) tuples
            
        Returns:
            List of ImportTaskDto objects
        """
        task_list = []
        source_frame_dir_path = os.path.join(self.params.source_dir, 'home', "frames")
        
        for image, file_path in images_to_process:
            task_dto = ImportTaskDto(
                task_id=uuid.uuid4(),
                job_id=self.db_job.oid,
                task_alias=f"magellon_{image.name}_{self.db_job.oid}",
                file_name=image.name,
                image_id=image.oid,
                image_name=image.name,
                image_path=file_path,
                frame_name=image.frame_name,
                frame_path=os.path.join(source_frame_dir_path, image.frame_name) if image.frame_name else None,
                status=1,
                pixel_size=image.pixel_size,
                acceleration_voltage=image.acceleration_voltage,
                spherical_aberration=image.spherical_aberration,
                binning_x=image.binning_x
            )
            task_list.append(task_dto)
            
        return task_list

    def _upsert_project(self, db_session: Session, project_data: Dict[str, Any]) -> Project:
        """
        Create or update project record from project data
        
        Args:
            db_session: SQLAlchemy database session
            project_data: Project data dictionary
            
        Returns:
            Project instance
        """
        project = db_session.query(Project).filter(
            Project.name == project_data["name"]
        ).first()

        if project:
            # Update existing project
            for key, value in project_data.items():
                if hasattr(project, key) and key != 'oid':
                    setattr(project, key, value)
        else:
            # Create new project
            project = Project(
                oid=uuid.UUID(project_data["oid"]) if "oid" in project_data else uuid.uuid4(),
                name=project_data["name"],
                description=project_data.get("description"),
                start_on=datetime.fromisoformat(project_data["start_on"]) if project_data.get("start_on") else None,
                end_on=datetime.fromisoformat(project_data["end_on"]) if project_data.get("end_on") else None,
                owner_id=uuid.UUID(project_data["owner_id"]) if project_data.get("owner_id") else None,
                last_accessed_date=datetime.now()
            )
            db_session.add(project)

        db_session.flush()
        return project

    def _upsert_session(self, db_session: Session, session_data: Dict[str, Any], project_id: Optional[uuid.UUID]) -> Msession:
        """
        Create or update session record from session data
        
        Args:
            db_session: SQLAlchemy database session
            session_data: Session data dictionary
            project_id: Optional project ID
            
        Returns:
            Msession instance
        """
        session = db_session.query(Msession).filter(
            Msession.name == session_data["name"]
        ).first()

        if session:
            # Update existing session
            for key, value in session_data.items():
                if hasattr(session, key) and key != 'oid':
                    setattr(session, key, value)
        else:
            # Create new session
            session = Msession(
                oid=uuid.UUID(session_data["oid"]) if "oid" in session_data else uuid.uuid4(),
                name=session_data["name"],
                project_id=project_id,
                description=session_data.get("description"),
                start_on=datetime.fromisoformat(session_data["start_on"]) if session_data.get("start_on") else None,
                end_on=datetime.fromisoformat(session_data["end_on"]) if session_data.get("end_on") else None,
                last_accessed_date=datetime.now()
            )
            db_session.add(session)

        db_session.flush()
        return session

    def process_images(self, db_session: Session, images_data: List[Dict[str, Any]], 
                      parent_id: Optional[uuid.UUID] = None) -> List[Tuple[Image, str]]:
        """
        Process images recursively and create job tasks
        
        Args:
            db_session: SQLAlchemy database session
            images_data: List of image data dictionaries
            parent_id: Optional parent image ID for hierarchical images
            
        Returns:
            List of (Image, file_path) tuples
        """
        results = []
        for image_data in images_data:
            # Convert string UUID to UUID object or generate new one
            image_oid = uuid.UUID(image_data["oid"]) if "oid" in image_data else uuid.uuid4()

            # Check if image exists
            existing_image = db_session.query(Image).filter(
                Image.name == image_data["name"],
                Image.session_id == self.db_msession.oid
            ).first()

            if existing_image:
                image = existing_image
                # Update existing image
                for key, value in image_data.items():
                    if hasattr(image, key) and key not in ['oid', 'name', 'session_id']:
                        setattr(image, key, value)
            else:
                # Create new image record
                image = Image(
                    oid=image_oid,
                    name=image_data["name"],
                    frame_name=image_data.get("frame_name"),
                    path=image_data.get("path"),
                    parent_id=parent_id,
                    session_id=self.db_msession.oid,
                    magnification=image_data.get("magnification"),
                    dose=image_data.get("dose"),
                    defocus=image_data.get("defocus"),
                    pixel_size=image_data.get("pixel_size"),
                    dimension_x=image_data.get("dimension_x"),
                    dimension_y=image_data.get("dimension_y"),
                    binning_x=image_data.get("binning_x"),
                    binning_y=image_data.get("binning_y"),
                    exposure_time=image_data.get("exposure_time"),
                    stage_x=image_data.get("stage_x"),
                    stage_y=image_data.get("stage_y"),
                    atlas_delta_row=image_data.get("atlas_delta_row"),
                    atlas_delta_column=image_data.get("atlas_delta_column"),
                    atlas_dimxy=image_data.get("atlas_dimxy"),
                    acceleration_voltage=image_data.get("acceleration_voltage"),
                    spherical_aberration=image_data.get("spherical_aberration"),
                    stage_alpha_tilt=image_data.get("stage_alpha_tilt"),
                    last_accessed_date=datetime.now()
                )
                db_session.add(image)

            # Get original file path
            original_file = os.path.normpath(os.path.join(
                self.params.source_dir, 'home', ORIGINAL_IMAGES_SUB_URL, f"{image.name}.mrc"
            ))

            # Create job task record if file exists
            if os.path.exists(original_file):
                task = ImageJobTask(
                    oid=uuid.uuid4(),
                    job_id=self.db_job.oid,
                    image_id=image.oid,
                    status_id=1,  # Pending
                    stage=0,
                    image_name=image.name,
                    image_path=os.path.normpath(original_file)
                )
                db_session.add(task)
                results.append((image, original_file))

            # Process children recursively
            if image_data.get("children"):
                results.extend(self.process_images(db_session, image_data["children"], image_oid))

        return results

    def create_magellon_atlas(self, db_session: Session) -> Dict[str, Any]:
        """
        Create atlas images from image data
        
        Args:
            db_session: SQLAlchemy database session
            
        Returns:
            Dict with atlas image information
        """
        try:
            if not self.db_msession:
                logger.warning("No session available for atlas creation")
                return {"message": "No session available for atlas creation"}
                
            # Use raw SQL for optimal performance with binary UUID
            try:
                session_id_binary = self.db_msession.oid.bytes
            except AttributeError:
                return {"error": "Invalid session ID"}
                
            # Query to get all atlas-related images
            query = text("""
                SELECT 
                    i.oid as id,
                    i.atlas_dimxy as dimx,
                    i.atlas_dimxy as dimy,
                    i.name as filename,
                    i.atlas_delta_row as delta_row,
                    i.atlas_delta_column as delta_column
                FROM image i
                WHERE i.session_id = :session_id 
                AND i.atlas_delta_row IS NOT NULL 
                AND i.atlas_delta_column IS NOT NULL
                AND i.parent_id IS NULL
                AND i.GCRecord IS NULL
                order by i.name
            """)

            result = db_session.execute(query, {"session_id": session_id_binary})
            atlas_images = result.fetchall()

            if not atlas_images:
                logger.warning("No atlas images found for this session")
                return {"message": "No atlas images found"}

            # Group images by grid label
            label_objects = {}
            for row in atlas_images:
                prefix = self._extract_grid_label(row.filename)

                obj = {
                    "id": str(row.id),
                    "dimx": float(row.dimx) if row.dimx else 0,
                    "dimy": float(row.dimy) if row.dimy else 0,
                    "filename": row.filename,
                    "delta_row": float(row.delta_row) if row.delta_row else 0,
                    "delta_column": float(row.delta_column) if row.delta_column else 0
                }

                if prefix in label_objects:
                    label_objects[prefix].append(obj)
                else:
                    label_objects[prefix] = [obj]

            # Create atlas images
            images = create_atlas_images(self.db_msession.name, label_objects)

            # Create atlas records
            atlases_to_insert = []
            for image in images:
                file_name = os.path.basename(image['imageFilePath'])
                file_name_without_extension = os.path.splitext(file_name)[0]
                atlas = Atlas(
                    oid=uuid.uuid4(),
                    name=file_name_without_extension,
                    meta=image['imageMap'],
                    session_id=self.db_msession.oid
                )
                atlases_to_insert.append(atlas)

            db_session.bulk_save_objects(atlases_to_insert)
            db_session.commit()

            return {"images": images, "count": len(atlases_to_insert)}

        except Exception as e:
            logger.error(f"Error creating atlas images: {str(e)}", exc_info=True)
            db_session.rollback()
            raise
