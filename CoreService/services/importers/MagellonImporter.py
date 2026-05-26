import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging
from sqlalchemy import text

from core.helper import dispatch_ctf_task, dispatch_motioncor_task, find_matching_file
from models.pydantic_models import ImportTaskDto
from models.sqlalchemy_models import Msession, Image, Project, Atlas
from services.atlas import create_atlas_images
from services.importers.BaseImporter import BaseImporter, TaskFailedException
from services.importers.source_strategies import MagellonSessionJsonStrategy
from core.exceptions import EntityNotFoundError, FileProcessingError
from sqlalchemy.orm import Session
from config import ( DEFECTS_SUB_URL, FFT_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, ATLAS_SUB_URL, CTF_SUB_URL, MAGELLON_HOME_DIR, FFT_SUFFIX, GAINS_SUB_URL)

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

    def process(self, db_session: Session) -> Dict[str, str]:
        try:
            # Create temporary directory for extraction
            # temp_dir = os.path.join(self.params.target_directory, 'import', str(uuid.uuid4()))
            # os.makedirs(temp_dir, exist_ok=True)

            # Extract archive
            # self.file_service.extract_archive(self.params.source_file, temp_dir)

            # Read and validate session.json

            session_data = MagellonSessionJsonStrategy().load(self.params.source_dir)

            # Process project data if exists

            if "project" in session_data and session_data["project"]:
                self.db_project = self.upsert_project_from_data(db_session, session_data["project"])

            # Process session data
            self.db_msession = self.upsert_session_from_data(
                db_session,
                session_data["msession"],
                self.db_project.oid if self.db_project else None,
            )

            session_dir=os.path.normpath( os.path.join(MAGELLON_HOME_DIR, self.db_msession.name.lower()))

            # self.create_magellon_atlas(db_session)
            # return

            if os.path.exists(session_dir) and getattr(self.params, "replace_existing", False):
                shutil.rmtree(session_dir)
            elif os.path.exists(session_dir):
                return {'status': 'failure',"message": f"this project already exists: {session_dir}"}

            # Create job record. Honour a pre-assigned oid if the caller
            # set one (see BaseImporter.pre_assigned_job_id) — the import
            # controller uses this so it can return the job_id to the
            # client before the background task runs.
            job = self.create_import_job_record(
                db_session,
                self.db_msession.oid,
                name=f"Import: {self.db_msession.name}",
                description=f"Import job for session: {self.db_msession.name}",
                status_id=1,  # Pending status
                type_id=1     # Import type
            )

            db_session.commit()
            self.db_job=job
            # Process all images and get list for file processing
            images_to_process = self.process_images(db_session,session_data["images"])
            # Create directory structure
            # session_dir = os.path.join(self.params.target_directory, self.db_msession.name)

            db_session.commit()
            self.file_service.target_directory = session_dir
            self.file_service.create_required_directories()

            source_home = os.path.join(self.params.source_dir, 'home')
            self.copy_source_subdirectory(source_home, session_dir, ORIGINAL_IMAGES_SUB_URL)
            self.copy_source_subdirectory(source_home, session_dir, GAINS_SUB_URL)
            self.copy_source_subdirectory(source_home, session_dir, DEFECTS_SUB_URL)
            # Copy frames directories
            source_frame_dir_path = os.path.join(self.params.source_dir, 'home', "frames")
            # if os.path.exists(source_frames):
            #     shutil.copytree( source_frames, os.path.join(session_dir, FRAMES_SUB_URL), dirs_exist_ok=True)

            # Process each image
            for image, file_path, task_oid in images_to_process:
                base_name = os.path.splitext(image.name)[0]

                # task_id MUST match the persisted ImageJobTask.oid —
                # plugin step events come back with this id and write
                # to job_event, which has FK(task_id → image_job_task.oid).
                task_dto = ImportTaskDto(
                    task_id=task_oid,
                    job_id=self.db_job.oid,
                    task_alias=f"lftj_{image.path}_{self.db_job.oid}",
                    file_name=f"{image.name}",

                    image_id=image.oid,
                    image_name=image.name,
                    image_path=file_path,

                    frame_name=image.frame_name,
                    frame_path=(
                        os.path.join(source_frame_dir_path, image.frame_name)
                        if image.frame_name else None
                    ),

                    # target_path=self.params.target_directory + "/frames/" + f"{image['frame_names']}{source_extension}",
                    # job_dto=db_job.,
                    status=1,
                    pixel_size=image.pixel_size,
                    acceleration_voltage=image.acceleration_voltage,
                    spherical_aberration=image.spherical_aberration*1000,
                    binning_x=image.binning_x
                )
                self.task_dto_list.append(task_dto)

            self.run_tasks(db_session )
                # self.file_service.process_image()
            # Mark any stage=0 tasks still at status=1 (images not CTF-eligible,
            # e.g. atlas/grid/hole images) as completed so the job reaches 100%.
            db_session.execute(
                text(
                    "UPDATE image_job_task SET status_id = 2 "
                    "WHERE job_id = :job_id AND stage = 0 AND status_id = 1"
                ),
                {"job_id": job.oid.bytes},
            )
            db_session.commit()

            try:
                self.create_magellon_atlas(db_session)
            except Exception as atlas_exc:
                logger.warning("Atlas creation skipped (non-fatal): %s", atlas_exc)

            return {
                'status': 'success',
                'message': 'Import completed successfully.',
                'session_name': self.db_msession.name,
                'job_id': str(job.oid)
            }

        except Exception as e:
            return {
                'status': 'failure',
                'message': 'Import encountered problem.',
                'session_name': getattr(self, 'db_msession', None) and self.db_msession.name or '',
                'error': str(e)
            }


    def run_tasks(self, db_session: Session):
        self._step_counts = {"png": 0, "fft": 0, "ctf": 0, "motioncor": 0}
        self._step_start_time = datetime.now()
        # Pre-count eligibility so the UI can show accurate per-step totals.
        # MotionCor: filter by frame file actually existing on disk so the
        # denominator matches what dispatch will succeed on. Metadata can
        # reference frames that weren't bundled in the export.
        self._step_totals = {
            "png": len(self.task_dto_list),
            "fft": len(self.task_dto_list),
            "ctf": sum(1 for t in self.task_dto_list if t.pixel_size and (t.pixel_size * 10 ** 10) <= 5),
            "motioncor": sum(1 for t in self.task_dto_list if self._has_motioncor_input(t)),
        }
        try:
            for task in self.task_dto_list:
                self.run_task(task)
        except Exception as e:
            logger.exception("Magellon import task execution failed: %s", e)
            raise

    def _emit_step_progress(self) -> None:
        try:
            from core.socketio_server import schedule_import_progress
            if not self.db_job:
                return
            elapsed_ms = int((datetime.now() - self._step_start_time).total_seconds() * 1000)
            schedule_import_progress(
                str(self.db_job.oid),
                {
                    "job_id": str(self.db_job.oid),
                    "event": "step_progress",
                    "step_counts": dict(self._step_counts),
                    "step_totals": dict(self._step_totals),
                    "elapsed_ms": elapsed_ms,
                },
            )
        except Exception:
            pass

    def run_task(self, task_dto: ImportTaskDto) -> Dict[str, str]:
        try:
            self.convert_image_to_png_task(task_dto.image_path, self.file_service.target_directory)
            self._step_counts["png"] += 1

            self.compute_fft_png_task(task_dto.image_path, self.file_service.target_directory)
            self._step_counts["fft"] += 1

            if self.compute_ctf_task(task_dto.image_path, task_dto):
                self._step_counts["ctf"] += 1

            if self.compute_motioncor_task(task_dto.image_path, task_dto):
                self._step_counts["motioncor"] += 1

            self._emit_step_progress()
            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            raise TaskFailedException(f"Task failed with error: {str(e)}")

    def _has_motioncor_input(self, task_dto: ImportTaskDto) -> bool:
        """True when the image has a frame_name AND a matching file exists
        on disk (same find_matching_file logic the dispatcher uses)."""
        if not task_dto.frame_name or not task_dto.frame_path:
            return False
        base_path = os.path.dirname(task_dto.frame_path)
        return find_matching_file(base_path, task_dto.frame_name) is not None

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

    def compute_ctf_task(self, abs_file_path: str, task_dto: ImportTaskDto) -> bool:
        try:
            if (task_dto.pixel_size * 10 ** 10) <= 5:
                dispatch_ctf_task(task_dto.task_id, abs_file_path, task_dto)
                return True
        except Exception as e:
            logger.error("CTF dispatch failed for %s: %s", abs_file_path, e)
        return False

    def compute_motioncor_task(self, abs_file_path: str, task_dto: ImportTaskDto) -> bool:
        """Dispatch a MotionCor task for this image. Returns True iff the
        message was pushed to the queue (image has a frame_name AND a
        matching frame file exists AND dispatch succeeded)."""
        if not self._has_motioncor_input(task_dto):
            return False
        try:
            settings = {
                'FmDose': 1.0,
                'PatchesX': 7,
                'PatchesY': 7,
                'Group': 4
            }
            source_gains_dir = os.path.join(self.params.source_dir, 'home', GAINS_SUB_URL)
            source_defects_dir = os.path.join(self.params.source_dir, 'home', DEFECTS_SUB_URL)

            # Search for gain files in the gains directory
            gain_files = []
            if os.path.exists(source_gains_dir):
                for file in os.listdir(source_gains_dir):
                    if file.endswith('_gain_multi_ref.tif'):
                        gain_files.append(os.path.join(source_gains_dir, file))

            if not gain_files:
                source_gains_file = self._find_gain_reference()
            else:
                # Use the most recent gain file (assuming date format in filename)
                source_gains_file = sorted(gain_files)[-1]

            if not source_gains_file:
                logger.warning("MotionCor skipped for %s: no gain reference found", abs_file_path)
                return False

            defects_path = None
            if os.path.exists(source_defects_dir):
                defect_files = [os.path.join(source_defects_dir, f) for f in os.listdir(source_defects_dir)]
                if defect_files:
                    defects_path = defect_files[0]
            if not defects_path:
                defects_path = self._find_defects_reference()

            return bool(dispatch_motioncor_task(
                task_id=task_dto.task_id,
                gain_path=source_gains_file,
                defects_path=defects_path,
                full_image_path=abs_file_path,
                task_dto=task_dto,
                motioncor_settings=settings,
            ))
        except Exception as e:
            logger.error("MotionCor dispatch failed for %s: %s", abs_file_path, e)
            return False

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
                raise EntityNotFoundError("Atlas images", self.params.session_name)

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
            raise FileProcessingError(f"Error creating atlas: {str(e)}")


    def _upsert_project(self, db_session: Session, project_data: Dict[str, Any]) -> Project:
        """Upsert project record"""
        return self.upsert_project_from_data(db_session, project_data)



    def _upsert_session(self, db_session: Session, session_data: Dict[str, Any], project_id: Optional[uuid.UUID]) -> Msession:
        """Upsert session record"""
        return self.upsert_session_from_data(db_session, session_data, project_id)



        # Process images recursively and create job tasks
    def process_images(self,db_session: Session,images_data: List[Dict[str, Any]], parent_id: Optional[uuid.UUID] = None) -> List[Tuple[Image, str, uuid.UUID]]:
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
                    task = self.create_image_job_task_record(
                        job_id=self.db_job.oid,
                        image_id=image.oid,
                        image_name=image.name,
                        image_path=os.path.normpath(original_file),
                        # frame_name=os.path.basename(frame_file) if frame_file else None,
                        # frame_path=frame_file
                    )
                    db_session.add(task)
                    results.append((image, original_file, task.oid))

                # Process children recursively
                if image_data.get("children"):
                    results.extend(self.process_images(db_session,image_data["children"], image_oid))

            return results
