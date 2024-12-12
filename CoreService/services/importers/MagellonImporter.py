import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models.sqlalchemy_models import Msession, Image, ImageMetaData, Project
from services.mrc_image_service import MrcImageService
from .BaseImporter import BaseImporter, TaskFailedException

from config import (
    FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL,
    ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, FFT_SUFFIX,
    ATLAS_SUB_URL, CTF_SUB_URL
)
from core.helper import create_directory
import logging

logger = logging.getLogger(__name__)

class MagellonImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.image_tasks = []
        self.mrc_service = MrcImageService()
        self.session_data = None
        self.magellon_session = None
        self.magellon_project = None
        self.source_images_dir = None
        self.source_frames_dir = None

    def validate_directory_structure(self):
        """Validate required directory structure and files exist"""
        if not os.path.exists(self.params.source_directory):
            raise FileNotFoundError(f"Source directory not found: {self.params.source_directory}")

        json_path = os.path.join(self.params.source_directory, "session.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"session.json not found in {self.params.source_directory}")

        self.source_images_dir = os.path.join(self.params.source_directory, 'images')
        self.source_frames_dir = os.path.join(self.params.source_directory, 'frames')

        if not os.path.exists(self.source_images_dir):
            raise FileNotFoundError(f"Images directory not found: {self.source_images_dir}")

    def upsert_project(self, project_data: Dict) -> Project:
        """Upsert project record"""
        if not project_data.get('project_id'):
            return None

        project_id = uuid.UUID(project_data['project_id'])
        stmt = select(Project).where(Project.oid == project_id)
        project = self.db_session.execute(stmt).scalar_one_or_none()

        if not project:
            project = Project(
                oid=project_id,
                name=project_data.get('name', 'Imported Project'),
                description=project_data.get('description'),
                start_on=datetime.now()
            )
            self.db_session.add(project)
            self.db_session.flush()
        else:
            # Update existing project if needed
            project.name = project_data.get('name', project.name)
            project.description = project_data.get('description', project.description)

        return project

    def upsert_session(self, session_data: Dict) -> Msession:
        """Upsert session record"""
        session_id = uuid.UUID(session_data['oid'])
        stmt = select(Msession).where(Msession.oid == session_id)
        session = self.db_session.execute(stmt).scalar_one_or_none()

        session_values = {
            'oid': session_id,
            'name': session_data['name'],
            'project_id': self.magellon_project.oid if self.magellon_project else None,
            'description': session_data.get('description'),
            'start_on': datetime.fromisoformat(session_data['start_on']) if session_data.get('start_on') else None,
            'end_on': datetime.fromisoformat(session_data['end_on']) if session_data.get('end_on') else None,
            'last_accessed_date': datetime.now()
        }

        if not session:
            session = Msession(**session_values)
            self.db_session.add(session)
        else:
            # Update existing session
            for key, value in session_values.items():
                setattr(session, key, value)

        self.db_session.flush()
        return session

    def upsert_image(self, image_data: Dict, parent_id: Optional[uuid.UUID] = None) -> Image:
        """Upsert image record"""
        image_id = uuid.UUID(image_data['oid'])
        stmt = select(Image).where(Image.oid == image_id)
        image = self.db_session.execute(stmt).scalar_one_or_none()

        image_values = {
            'oid': image_id,
            'name': image_data['name'],
            'path': os.path.join(self.source_images_dir, f"{image_data['name']}.mrc"),
            'parent_id': parent_id,
            'session_id': self.magellon_session.oid,
            'magnification': image_data.get('magnification'),
            'dose': image_data.get('dose'),
            'defocus': image_data.get('defocus'),
            'pixel_size': image_data.get('pixel_size'),
            'dimension_x': image_data.get('dimension_x'),
            'dimension_y': image_data.get('dimension_y'),
            'binning_x': image_data.get('binning_x'),
            'binning_y': image_data.get('binning_y'),
            'exposure_time': image_data.get('exposure_time'),
            'stage_x': image_data.get('stage_x'),
            'stage_y': image_data.get('stage_y'),
            'last_accessed_date': datetime.now()
        }

        if not image:
            image = Image(**image_values)
            self.db_session.add(image)
        else:
            # Update existing image
            for key, value in image_values.items():
                setattr(image, key, value)

        self.db_session.flush()
        return image

    def upsert_metadata(self, metadata: Dict, image_id: uuid.UUID):
        """Upsert metadata record"""
        meta_id = uuid.UUID(metadata['oid'])
        stmt = select(ImageMetaData).where(ImageMetaData.oid == meta_id)
        meta = self.db_session.execute(stmt).scalar_one_or_none()

        meta_values = {
            'oid': meta_id,
            'name': metadata['name'],
            'image_id': image_id,
            'data': metadata.get('data'),
            'data_json': metadata.get('data_json'),
            'category_id': uuid.UUID(metadata['category_id']) if metadata.get('category_id') else None
        }

        if not meta:
            meta = ImageMetaData(**meta_values)
            self.db_session.add(meta)
        else:
            # Update existing metadata
            for key, value in meta_values.items():
                setattr(meta, key, value)

    def process_imported_data(self):
        """Process the imported session data and create/update database records"""
        try:
            # Upsert project if needed
            project_data = self.session_data['msession']
            self.magellon_project = self.upsert_project(project_data)

            # Upsert session
            self.magellon_session = self.upsert_session(self.session_data['msession'])

            # Process images recursively
            self._process_images(self.session_data['images'])

            self.db_session.commit()

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error processing imported data: {str(e)}")
            raise

    def _process_images(self, images_data: List[Dict[str, Any]], parent_id: Optional[uuid.UUID] = None):
        """Recursively process image data and create/update database records"""
        for image_data in images_data:
            # Upsert image
            image = self.upsert_image(image_data, parent_id)

            # Create image processing task
            self._create_image_task(image)

            # Process metadata
            for metadata in image_data.get('metadata', []):
                self.upsert_metadata(metadata, image.oid)

            # Process children recursively
            if image_data.get('children'):
                self._process_images(image_data['children'], image.oid)

    def _create_image_task(self, image: Image):
        """Create task for image processing"""
        frame_path = os.path.join(self.source_frames_dir, f"{image.name}_frames.mrc")
        frame_path = frame_path if os.path.exists(frame_path) else None

        task = MagellonImportTaskDto(
            task_id=uuid.uuid4(),
            file_name=image.name,
            image_id=image.oid,
            image_name=image.name,
            image_path=image.path,
            frame_path=frame_path,
            job_dto=self.params,
            status=1,
            pixel_size=image.pixel_size
        )
        self.image_tasks.append(task)

    # Rest of the class implementation remains the same...