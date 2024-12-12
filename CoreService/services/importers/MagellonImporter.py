import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.sqlalchemy_models import Msession, Image, ImageMetaData, Project
from services.mrc_image_service import MrcImageService
from .BaseImporter import BaseImporter, TaskFailedException
from models.pydantic_models import MagellonImportTaskDto
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

    def import_data(self):
        """Import data from session.json file"""
        try:
            json_path = os.path.join(self.params.source_directory, "session.json")
            if not os.path.exists(json_path):
                raise FileNotFoundError(f"session.json not found in {self.params.source_directory}")

            with open(json_path, 'r') as f:
                self.session_data = json.load(f)

            if not self.session_data or 'msession' not in self.session_data:
                raise ValueError("Invalid session.json format: missing required data")

        except Exception as e:
            logger.error(f"Error importing data: {str(e)}")
            raise

    def process_imported_data(self):
        """Process the imported session data and create database records"""
        try:
            # Create project if needed
            project_data = self.session_data['msession']
            if project_data.get('project_id'):
                self.magellon_project = self.db_session.query(Project).filter(
                    Project.oid == uuid.UUID(project_data['project_id'])
                ).first()

                if not self.magellon_project:
                    self.magellon_project = Project(
                        oid=uuid.UUID(project_data['project_id']),
                        name=project_data.get('name', 'Imported Project')
                    )
                    self.db_session.add(self.magellon_project)

            # Create session
            msession_data = self.session_data['msession']
            self.magellon_session = Msession(
                oid=uuid.UUID(msession_data['oid']),
                name=msession_data['name'],
                project_id=self.magellon_project.oid if self.magellon_project else None,
                description=msession_data.get('description'),
                start_on=datetime.fromisoformat(msession_data['start_on']) if msession_data.get('start_on') else None,
                end_on=datetime.fromisoformat(msession_data['end_on']) if msession_data.get('end_on') else None
            )
            self.db_session.add(self.magellon_session)

            # Process images
            self._process_images(self.session_data['images'])

            self.db_session.commit()

        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error processing imported data: {str(e)}")
            raise

    def _process_images(self, images_data: List[Dict[str, Any]], parent_id: uuid.UUID = None):
        """Recursively process image data and create database records"""
        for image_data in images_data:
            # Create image record
            image = Image(
                oid=uuid.UUID(image_data['oid']),
                name=image_data['name'],
                path=image_data['path'],
                parent_id=parent_id,
                session_id=self.magellon_session.oid,
                magnification=image_data.get('magnification'),
                dose=image_data.get('dose'),
                defocus=image_data.get('defocus'),
                pixel_size=image_data.get('pixel_size'),
                dimension_x=image_data.get('dimension_x'),
                dimension_y=image_data.get('dimension_y'),
                binning_x=image_data.get('binning_x'),
                binning_y=image_data.get('binning_y'),
                exposure_time=image_data.get('exposure_time'),
                stage_x=image_data.get('stage_x'),
                stage_y=image_data.get('stage_y')
            )
            self.db_session.add(image)

            # Create task for image processing
            task = MagellonImportTaskDto(
                task_id=uuid.uuid4(),
                file_name=image.name,
                image_id=image.oid,
                image_name=image.name,
                image_path=os.path.join(self.params.source_directory, 'images', f"{image.name}.mrc"),
                frame_path=os.path.join(self.params.source_directory, 'frames', f"{image.name}_frames.mrc"),
                job_dto=self.params,
                status=1,
                pixel_size=image.pixel_size
            )
            self.image_tasks.append(task)

            # Process metadata
            for metadata in image_data.get('metadata', []):
                meta = ImageMetaData(
                    oid=uuid.UUID(metadata['oid']),
                    name=metadata['name'],
                    image_id=image.oid,
                    data=metadata.get('data'),
                    data_json=metadata.get('data_json'),
                    category_id=uuid.UUID(metadata['category_id']) if metadata.get('category_id') else None
                )
                self.db_session.add(meta)

            # Process children recursively
            if image_data.get('children'):
                self._process_images(image_data['children'], image.oid)

    def create_directories(self):
        """Create necessary directory structure"""
        session_dir = os.path.join(self.params.target_directory, self.magellon_session.name)
        create_directory(session_dir)

        directories = [
            ORIGINAL_IMAGES_SUB_URL,
            FRAMES_SUB_URL,
            FFT_SUB_URL,
            IMAGE_SUB_URL,
            THUMBNAILS_SUB_URL,
            ATLAS_SUB_URL,
            CTF_SUB_URL
        ]

        for directory in directories:
            create_directory(os.path.join(session_dir, directory))

    def copy_files(self):
        """Copy image and frame files to target directory"""
        try:
            source_images = os.path.join(self.params.source_directory, 'images')
            source_frames = os.path.join(self.params.source_directory, 'frames')

            target_images = os.path.join(
                self.params.target_directory,
                self.magellon_session.name,
                ORIGINAL_IMAGES_SUB_URL
            )
            target_frames = os.path.join(
                self.params.target_directory,
                self.magellon_session.name,
                FRAMES_SUB_URL
            )

            if os.path.exists(source_images):
                for file in os.listdir(source_images):
                    shutil.copy2(
                        os.path.join(source_images, file),
                        os.path.join(target_images, file)
                    )

            if os.path.exists(source_frames):
                for file in os.listdir(source_frames):
                    shutil.copy2(
                        os.path.join(source_frames, file),
                        os.path.join(target_frames, file)
                    )

        except Exception as e:
            logger.error(f"Error copying files: {str(e)}")
            raise

    def get_image_tasks(self):
        """Return list of image tasks for processing"""
        return self.image_tasks

    def post_processing(self):
        """Override post_processing to include file copying"""
        try:
            self.create_directories()
            self.copy_files()
            super().post_processing()  # Call parent's post_processing for image processing
        except Exception as e:
            logger.error(f"Error in post processing: {str(e)}")
            raise