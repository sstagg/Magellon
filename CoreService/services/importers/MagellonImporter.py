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
from services.importers.BaseImporter import BaseImporter, TaskFailedException
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from config import ( FFT_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, ATLAS_SUB_URL, CTF_SUB_URL, MAGELLON_HOME_DIR, FFT_SUFFIX, GAINS_SUB_URL)

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


class MagellonImporter(BaseImporter):

    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        try:
            # Create temporary directory for extraction
            # temp_dir = os.path.join(self.params.target_directory, 'import', str(uuid.uuid4()))
            # os.makedirs(temp_dir, exist_ok=True)

            # Extract archive
            # self.file_service.extract_archive(self.params.source_file, temp_dir)

            # Read and validate session.json

            json_path = os.path.join(self.params.source_dir, 'session.json')
            if not os.path.exists(json_path):
                raise HTTPException( status_code=400, detail="Invalid archive structure: session.json not found"   )

            with open(json_path, 'r') as f:
                session_data = json.load(f)

            # Process project data if exists

            if "project" in session_data and session_data["project"]:
                self.db_project = self._upsert_project(db_session, session_data["project"])

            # Process session data
            self.db_msession = self._upsert_session(db_session, session_data["msession"], self.db_project.oid if self.db_project else None)

            session_dir=os.path.normpath( os.path.join(MAGELLON_HOME_DIR, self.db_msession.name.lower()))

            # self.create_magellon_atlas(db_session)
            # return

            if os.path.exists(session_dir):
                return {'status': 'failure',"message": f"this project already exists: {session_dir}"}

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
            # Process all images and get list for file processing
            images_to_process = self.process_images(db_session,session_data["images"])
            # Create directory structure
            # session_dir = os.path.join(self.params.target_directory, self.db_msession.name)

            db_session.commit()
            self.file_service.target_directory = session_dir
            self.file_service.create_required_directories()

            # Copy original directories
            source_original = os.path.join(self.params.source_dir, 'home', ORIGINAL_IMAGES_SUB_URL)
            if os.path.exists(source_original):
                shutil.copytree(source_original,os.path.join(session_dir, ORIGINAL_IMAGES_SUB_URL), dirs_exist_ok=True)

            # Copy gains directories
            source_gains = os.path.join(self.params.source_dir, 'home', GAINS_SUB_URL)
            if os.path.exists(source_gains):
                shutil.copytree(source_gains, os.path.join(session_dir, GAINS_SUB_URL), dirs_exist_ok=True)


            # Copy frames directories
            source_frame_dir_path = os.path.join(self.params.source_dir, 'home', "frames")
            # if os.path.exists(source_frames):
            #     shutil.copytree( source_frames, os.path.join(session_dir, FRAMES_SUB_URL), dirs_exist_ok=True)

            # Process each image
            for image, file_path in images_to_process:
                base_name = os.path.splitext(image.name)[0]

                task_dto = ImportTaskDto(
                    task_id=uuid.uuid4(),
                    job_id=self.db_job.oid,
                    task_alias=f"lftj_{image.path}_{self.db_job.oid}",
                    file_name=f"{image.name}",

                    image_id=image.oid,
                    image_name=image.name,
                    image_path=file_path,

                    frame_name=image.frame_name,
                    frame_path= os.path.join(source_frame_dir_path, image.frame_name+".tif") ,

                    # target_path=self.params.target_directory + "/frames/" + f"{image['frame_names']}{source_extension}",
                    # job_dto=db_job.,
                    status=1,
                    pixel_size=image.pixel_size,
                    acceleration_voltage=image.acceleration_voltage,
                    spherical_aberration=image.spherical_aberration
                )
                self.task_dto_list.append(task_dto)

            self.run_tasks(db_session )
                # self.file_service.process_image()
            self.create_magellon_atlas(db_session)
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
                'status': 'failure',
                'message': 'Import encountered problem.',
                'session_name': self.db_msession.name,
                'error': str(e)
            }


    def run_tasks(self, db_session: Session):
        try:
            # Iterate over each task in the task list and run it synchronously
            for task in self.task_dto_list:
                self.run_task(task)
            # self.create_atlas_pics(self.params.session_name, db_session,magellon_session)
        except Exception as e:
            print("An unexpected error occurred:", str(e))



    def run_task(self, task_dto: ImportTaskDto) -> Dict[str, str]:
        try:
            # 1
            # self.transfer_frame(task_dto)
            # 2
            # target_image_path = os.path.join(self.file_service.target_directory + "/" + ORIGINAL_IMAGES_SUB_URL + task_dto.image_name)
            # copy_file(task_dto.image_path, target_image_path)
            # task_dto.image_path = target_image_path

            # Generate FFT using the REST API

            self.convert_image_to_png_task(task_dto.image_path, self.file_service.target_directory )
            self.compute_fft_png_task(task_dto.image_path, self.file_service.target_directory )
            self.compute_ctf_task(task_dto.image_path, task_dto)

            if task_dto.frame_name:
                self.compute_motioncor_task(task_dto.image_path, task_dto)

            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            raise TaskFailedException(f"Task failed with error: {str(e)}")

    def convert_image_to_png_task(self, abs_file_path, out_dir):
        try:
            # generates png and thumbnails
            self.file_service.mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
            return {"message": "MRC file successfully converted to PNG!"}
        except Exception as e:
            return {"error": str(e)}

    def compute_fft_png_task(self, abs_file_path: str, out_dir: str):
        try:
            fft_path = os.path.join(out_dir, FFT_SUB_URL,
                                    os.path.splitext(os.path.basename(abs_file_path))[0] + FFT_SUFFIX)
            # self.create_image_directory(fft_path)
            # self.compute_fft(img=mic, abs_out_file_name=fft_path)
            self.file_service.mrc_service.compute_mrc_fft(mrc_abs_path=abs_file_path, abs_out_file_name=fft_path)
            return {"message": "MRC file successfully converted to fft PNG!"}

        except Exception as e:
            return {"error": str(e)}

    def compute_ctf_task(self, abs_file_path: str, task_dto: ImportTaskDto):
        try:
            if (task_dto.pixel_size * 10 ** 10) <= 5:
                dispatch_ctf_task(task_dto.task_id, abs_file_path, task_dto)
                return {"message": "Converting to ctf on the way! " + abs_file_path}

        except Exception as e:
            return {"error": str(e)}

    def compute_motioncor_task(self, abs_file_path: str, task_dto: ImportTaskDto):
        try:
            if task_dto.frame_name:
                settings = {
                    'FmDose': 1.0,
                    'PatchesX': 7,
                    'PatchesY': 7,
                    'Group': 4
                }
                source_gains_dir = os.path.join(self.params.source_dir, 'home', GAINS_SUB_URL)

                # Search for gain files in the gains directory
                gain_files = []
                if os.path.exists(source_gains_dir):
                    for file in os.listdir(source_gains_dir):
                        if file.endswith('_gain_multi_ref.tif'):
                            gain_files.append(os.path.join(source_gains_dir, file))

                if not gain_files:
                    source_gains_file = "/gpfs/24dec03a/home/gains/20241202_53597_gain_multi_ref.tif"

                # Use the most recent gain file (assuming date format in filename)
                source_gains_file = sorted(gain_files)[-1]

                dispatch_motioncor_task(
                    task_id = task_dto.task_id,
                    gain_path=source_gains_file,
                    full_image_path= abs_file_path+".tif",
                    task_dto= task_dto,
                    motioncor_settings= settings
                )
                return {"message": "Converting to motioncor on the way! " + abs_file_path}

        except Exception as e:
            return {"error": str(e)}

    def create_magellon_atlas(self, db_session: Session ):
        """
        Create atlas images for a Magellon session using the Image table.
        """
        try:
            # Get the session ID from Msession table
            try:
                session_id_binary = self.db_msession.oid.bytes
            except AttributeError:
                return {"error": "Invalid session ID"}
            # Query to get all atlas-related images for the session
            # This query gets images where parent_id is null (top-level images)
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
                raise HTTPException(status_code=404, detail="No atlas images found for this session")

            # Group images by their grid label prefix use extract_grid_label(row.filename) to get the grid label
            label_objects = {}

            for row in atlas_images:
                # Get the prefix of the filename (everything before the first underscore)
                # filename_parts = row.filename.split('_')
                prefix = extract_grid_label(row.filename) # Using first part as the group identifier

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

            # Create atlas images using the existing create_atlas_images function
            images = create_atlas_images(self.db_msession.name, label_objects)

            # Insert the atlas records into the database
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

            return {"images": images}

        except Exception as e:
            db_session.rollback()
            raise HTTPException(status_code=500, detail=str(e))


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
                        frame_name=image_data["frame_name"],
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
                original_file = os.path.normpath(os.path.join(self.params.source_dir, 'home', ORIGINAL_IMAGES_SUB_URL, f"{image.name}.mrc"))
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
                        image_path=os.path.normpath(original_file),
                        # frame_name=os.path.basename(frame_file) if frame_file else None,
                        # frame_path=frame_file
                    )
                    db_session.add(task)
                    results.append((image, original_file))

                # Process children recursively
                if image_data.get("children"):
                    results.extend(self.process_images(db_session,image_data["children"], image_oid))

            return results
