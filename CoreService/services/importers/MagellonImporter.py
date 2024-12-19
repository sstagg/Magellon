import json
import os
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging

from models.sqlalchemy_models import Msession, ImageJob, Image, ImageJobTask, Project
from services.importers.BaseImporter import BaseImporter
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from config import (
    IMAGE_SUB_URL, THUMBNAILS_SUB_URL, FFT_SUB_URL,
    ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, ATLAS_SUB_URL, CTF_SUB_URL, MAGELLON_HOME_DIR)


logger = logging.getLogger(__name__)


class MagellonImporter(BaseImporter):



    def run_job(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        try:
            # Create temporary directory for extraction
            # temp_dir = os.path.join(self.params.target_directory, 'import', str(uuid.uuid4()))
            # os.makedirs(temp_dir, exist_ok=True)

            # Extract archive
            # self.file_service.extract_archive(self.params.source_file, temp_dir)

            # Read and validate session.json

            json_path = os.path.join(self.params.source_file, 'session.json')
            if not os.path.exists(json_path):
                raise HTTPException( status_code=400, detail="Invalid archive structure: session.json not found"   )

            with open(json_path, 'r') as f:
                session_data = json.load(f)

            # Process project data if exists

            if "project" in session_data and session_data["project"]:
                self.db_project = self._upsert_project(db_session, session_data["project"])

            # Process session data
            self.db_msession = self._upsert_session(db_session, session_data["msession"], self.db_project.oid if self.db_project else None)

            session_dir= os.path.join(MAGELLON_HOME_DIR, self.db_msession.name)
            if os.path.exists(session_dir):
                return {"message": "this project already exists"}


            # Process all images and get list for file processing
            images_to_process = self.process_images(session_data["images"])

            # Create job record
            job = ImageJob(
                oid=uuid.uuid4(),
                name=f"Import: {self.db_msession.name}",
                description=f"Import job for session: {self.db_msession.name}",
                created_date=datetime.now(),
                msession_id=self.db_msession.oid,
                status_id=1,  # Pending status
                type_id=1     # Import type
            )


            db_session.add(job)
            db_session.flush()

            db_session.commit()
            self.db_job=job

            # Create directory structure
            # session_dir = os.path.join(self.params.target_directory, self.db_msession.name)


            self.file_service.target_directory = session_dir
            self.file_service.create_required_directories()

            # Copy original directories
            source_original = os.path.join(self.params.source_file, 'home', ORIGINAL_IMAGES_SUB_URL)

            if os.path.exists(source_original):
                shutil.copytree(source_original,os.path.join(session_dir, ORIGINAL_IMAGES_SUB_URL), dirs_exist_ok=True)
            # Copy frames directories
            source_frames = os.path.join(self.params.source_file, 'home', FRAMES_SUB_URL)
            if os.path.exists(source_frames):
                shutil.copytree( source_frames, os.path.join(session_dir, FRAMES_SUB_URL), dirs_exist_ok=True)

            # Process each image
            for image, file_path in images_to_process:
                base_name = os.path.splitext(image.name)[0]

                # self.file_service.process_image()

            # Clean up temporary directory
            # shutil.rmtree(temp_dir)

            return {
                'status': 'success',
                'message': 'Import completed successfully.',
                'session_name': self.db_msession.name,
                'job_id': str(job.oid)
            }

        except Exception as e:
            # Clean up temporary directory in case of error
            # if 'temp_dir' in locals() and os.path.exists(temp_dir):
            #     shutil.rmtree(temp_dir)
            # raise HTTPException(status_code=500, detail=str(e))
            return {
                'status': 'faliure',
                'message': 'Import completed encountered problem.',
                'session_name': self.db_msession.name
            }


    def _upsert_project(self, db_session: Session, project_data: Dict[str, Any]) -> Project:
        """Upsert project record"""
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
        """Upsert session record"""
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



        # Process images recursively and create job tasks
    def process_images(self,db_session: Session,images_data: List[Dict[str, Any]], parent_id: Optional[uuid.UUID] = None) -> List[Tuple[Image, str]]:
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
                        last_accessed_date=datetime.now()
                    )
                    db_session.add(image)

                # Get original file path
                original_file = os.path.join(self.params.source_file, 'home', ORIGINAL_IMAGES_SUB_URL, f"{image.name}.mrc")
                # if not os.path.exists(original_file):
                #     original_file = os.path.join(self.params.source_file, 'home', ORIGINAL_IMAGES_SUB_URL, f"{image.name}.tiff")
                #
                # # Get frame file if exists
                # frame_file = None
                # frame_path = os.path.join(self.params.source_file, 'home', FRAMES_SUB_URL)
                # if os.path.exists(frame_path):
                #     frame_files = [f for f in os.listdir(frame_path) if f.startswith(image.name)]
                #     if frame_files:
                #         frame_file = os.path.join(frame_path, frame_files[0])

                # Create job task record
                if os.path.exists(original_file):
                    task = ImageJobTask(
                        oid=uuid.uuid4(),
                        job_id=self.db_job.oid,
                        image_id=image.oid,
                        status_id=1,  # Pending
                        stage=0,
                        image_name=image.name,
                        image_path=original_file,
                        # frame_name=os.path.basename(frame_file) if frame_file else None,
                        # frame_path=frame_file
                    )
                    db_session.add(task)
                    results.append((image, original_file))

                # Process children recursively
                if image_data.get("children"):
                    results.extend(self.process_images(image_data["children"], image_oid))

            return results
