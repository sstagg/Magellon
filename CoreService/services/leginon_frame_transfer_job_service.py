import re
import time
from collections import deque
from datetime import datetime
import os
import json
import uuid
from typing import Dict
import concurrent.futures
import logging

import pymysql
from config import FFT_SUB_URL, IMAGE_SUB_URL, MAGELLON_GPFS_DIR, MAGELLON_HOME_DIR, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX, app_settings, ATLAS_SUB_URL, CTF_SUB_URL, FAO_SUB_URL, GAINS_SUB_URL, DEFECTS_SUB_URL

from core.helper import dispatch_ctf_task, dispatch_motioncor_task
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto, ImportTaskDto
from models.sqlalchemy_models import Image, Project, Msession, ImageJob, ImageJobTask, Atlas
from services.atlas import create_atlas_images
from services.file_service import copy_file, create_directory, check_file_exists
from core.helper import custom_replace
from services.mrc_image_service import MrcImageService
from sqlalchemy.orm import Session

MAX_RETRIES = 3
logger = logging.getLogger(__name__)


class TaskFailedException(Exception):
    pass


def _find_sidecar_file(frames_dir: str, directory_names: tuple[str, ...], filename_tokens: tuple[str, ...]):
    for directory_name in directory_names:
        sidecar_dir = os.path.join(frames_dir, directory_name)
        if os.path.isdir(sidecar_dir):
            candidates = sorted(
                os.path.join(sidecar_dir, name)
                for name in os.listdir(sidecar_dir)
                if os.path.isfile(os.path.join(sidecar_dir, name))
            )
            if candidates:
                return candidates[0]

    if os.path.isdir(frames_dir):
        candidates = sorted(
            os.path.join(frames_dir, name)
            for name in os.listdir(frames_dir)
            if os.path.isfile(os.path.join(frames_dir, name))
            and any(token in name.lower() for token in filename_tokens)
        )
        if candidates:
            return candidates[0]
    return None


def find_session_layout(data_dir: str, image_names, frame_names):
    """A Leginon session's data folder holds ``original/`` (images),
    ``frames/`` (movies) and ``gains/`` (gain reference). Returns
    ``(images_dir, frames_dir)``; ``frames_dir`` is None when none of the
    session's movies are there (images still import, without MotionCor)."""
    image_names = [n for n in image_names if n][:20]
    frame_names = [n for n in frame_names if n][:20]
    images_dir = os.path.join(data_dir, ORIGINAL_IMAGES_SUB_URL.strip("/"))
    if not any(os.path.isfile(os.path.join(images_dir, n)) for n in image_names):
        raise FileNotFoundError(
            f"Couldn't find this session's images (e.g. {image_names[0] if image_names else '?'}) "
            f"in {images_dir}. Check the data folder.")
    frames_dir = os.path.join(data_dir, FRAMES_SUB_URL.strip("/"))
    if not any(check_file_exists(frames_dir, n) for n in frame_names):
        frames_dir = None
    return images_dir, frames_dir


def update_levels(image_list: list[Image], parent_id=None, level=0):
    queue = deque([(image, level) for image in image_list if image.parent_id == parent_id])

    while queue:
        image, level = queue.popleft()
        image.level = level

        children = [child for child in image_list if child.parent_id == image.Oid]
        queue.extend([(child, level + 1) for child in children])


def create_directories(target_dir: str):
    create_directory(target_dir)
    create_directory(os.path.join(target_dir, ORIGINAL_IMAGES_SUB_URL))
    create_directory(os.path.join(target_dir, FRAMES_SUB_URL))
    create_directory(os.path.join(target_dir, FFT_SUB_URL))
    create_directory(os.path.join(target_dir, IMAGE_SUB_URL))
    create_directory(os.path.join(target_dir, THUMBNAILS_SUB_URL))
    create_directory(os.path.join(target_dir, ATLAS_SUB_URL))
    create_directory(os.path.join(target_dir, CTF_SUB_URL))
    create_directory(os.path.join(target_dir, FAO_SUB_URL))



def infer_image_levels(name):
    presets = {'sq', 'gr', 'ex', 'hl', 'fc'}
    return sum(1 for preset in presets if preset in name)


def infer_image_levels_reg(name):
    return len(re.findall(r'sq|gr|ex|hl|fc', name))


def get_image_levels(name, pattern):
    return len(re.findall(pattern, name))


def remove_v_b_substrings(input_string):
    # Define the regular expression pattern to match "_v01", "_v02", "-b", "-DW"
    pattern = r"(_[vV]\d{2})|(-[bB])|(-[dD][wW])"
    # Use re.sub() to remove the matched substrings
    return re.sub(pattern, '', input_string)


class LeginonFrameTransferJobService:

    def __init__(self):
        self.params: LeginonFrameTransferJobDto = None
        self.mrc_service = MrcImageService()
        self.leginon_db_connection: pymysql.Connection = None
        self.leginon_cursor: pymysql.cursors.Cursor = None
        self.gains_path: str = None
        self.defects_path: str = None
        self.images_dir: str = None  # set when importing from a data folder

    def setup(self, input_json: str):
        input_data = json.loads(input_json)
        self.params = LeginonFrameTransferJobDto(**input_data)

    def setup_data(self, input_data: LeginonFrameTransferJobDto):
        self.params = input_data

    def process(self, db_session: Session) -> Dict[str, str]:
        try:
            start_time = time.time()  # Start measuring the time
            result = self.create_job(db_session)
            end_time = time.time()  # Stop measuring the time

            execution_time = end_time - start_time
            return result

        except Exception as e:
            return {'status': 'failure', 'message': f'Job failed with error: {str(e)} Job ID: {self.params.job_id}'}

    def create_job(self, db_session: Session):
        logger.info("Creating job with parameters: %s", self.params)
        try:
            magellon_project = self._ensure_project(db_session)
            magellon_session_name = self.params.magellon_session_name or self.params.session_name
            magellon_session = self._ensure_session(db_session, magellon_session_name, magellon_project)

            self.open_leginon_connection()
            session_result, presets_pattern = self._fetch_leginon_session_data()
            if session_result is None:
                raise FileNotFoundError(f"There is no session '{self.params.session_name}' in the Leginon database.")
            leginon_image_list = self._fetch_leginon_images(self.params.session_name)

            if not leginon_image_list:
                return {'status': 'success', 'message': 'No images found in Leginon.'}

            self.images_dir = None
            if self.params.data_directory:
                # Find images and frames inside the chosen data folder by name.
                self.images_dir, frames_dir = find_session_layout(
                    self.params.data_directory,
                    [image["image_name"] for image in leginon_image_list],
                    [image.get("frame_names") for image in leginon_image_list])
                self.params.camera_directory = frames_dir
                logger.info("Leginon layout: images in %s, frames in %s", self.images_dir, frames_dir)
            if self.params.camera_directory or not self.params.data_directory:
                self._setup_gains_defects(magellon_session_name)

            job = self._create_image_job(db_session, session_result, magellon_session)
            db_image_list, db_job_item_list, image_dict = self._build_image_records(
                leginon_image_list, session_result, presets_pattern, job, magellon_session
            )
            self._link_parent_images(db_image_list, image_dict)
            self._check_image_files(db_image_list)

            db_session.bulk_save_objects(db_image_list)
            db_session.bulk_save_objects(db_job_item_list)
            db_session.commit()

            if getattr(self.params, 'if_do_subtasks', True):
                self.run_tasks(db_session, magellon_session)

            return {'status': 'success', 'message': 'Job completed successfully.', 'job_id': job.oid}

        except FileNotFoundError as e:
            logger.error("File not found: %s", e, exc_info=True)
            return {"error": str(e), "exception": str(e)}
        except OSError as e:
            logger.error("OS error: %s", e, exc_info=True)
            return {"error": str(e), "exception": str(e)}
        except Exception as e:
            logger.error("Unexpected error: %s", e, exc_info=True)
            return {"error": str(e), "exception": str(e)}

    def _ensure_project(self, db_session: Session):
        if self.params.magellon_project_name is None:
            return None
        project = db_session.query(Project).filter(
            Project.name == self.params.magellon_project_name).first()
        if not project:
            project = Project(name=self.params.magellon_project_name)
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
        return project

    def _ensure_session(self, db_session: Session, session_name: str, project):
        if self.params.magellon_session_name is None:
            return None
        session = db_session.query(Msession).filter(Msession.name == session_name).first()
        if not session:
            session = Msession(name=session_name, project_id=project.oid)
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)
        return session

    def _setup_gains_defects(self, session_name: str):
        camera_directory = (self.params.camera_directory or '').replace('\\', '/')
        if self.params.data_directory:
            frames_dir = self.params.data_directory  # gains/ sits beside frames/
        elif camera_directory:
            camera_directory = os.path.normpath(camera_directory)
            camera_leaf = os.path.basename(camera_directory).lower()
            camera_parent = os.path.dirname(camera_directory)
            parent_leaf = os.path.basename(camera_parent).lower()
            if camera_leaf == 'rawdata' or (camera_leaf == 'frames' and parent_leaf == 'home'):
                frames_dir = camera_parent
            else:
                frames_dir = camera_directory
        else:
            gpfs_root = os.environ.get('MAGELLON_GPFS_PATH', MAGELLON_GPFS_DIR)
            frames_dir = os.path.join(gpfs_root, session_name, 'home')

        gains_dir_names = (GAINS_SUB_URL.rstrip('/\\'), 'gain')
        defects_dir_names = (DEFECTS_SUB_URL.rstrip('/\\'), 'defect')

        def save_uploaded_file(upload, canonical_directory):
            sidecar_dir = os.path.join(
                MAGELLON_HOME_DIR,
                session_name,
                canonical_directory.rstrip('/\\'),
            )
            os.makedirs(sidecar_dir, exist_ok=True)
            filename = os.path.basename(upload.filename.replace('\\', '/'))
            destination = os.path.join(sidecar_dir, filename)
            with open(destination, 'wb') as output_file:
                output_file.write(upload.file.read())
            return destination

        # Browser uploads belong in the writable Magellon home mount, not the source tree.
        if getattr(self.params, 'gains_file', None) is not None:
            self.gains_path = save_uploaded_file(
                self.params.gains_file, GAINS_SUB_URL
            )

        if getattr(self.params, 'defects_file', None) is not None:
            self.defects_path = save_uploaded_file(
                self.params.defects_file, DEFECTS_SUB_URL
            )

        # Fall back to existing files on GPFS
        if self.gains_path is None:
            self.gains_path = _find_sidecar_file(
                frames_dir, gains_dir_names, ('gain',)
            )
            if self.gains_path is None:
                raise FileNotFoundError(
                    f"No gain file found for session '{session_name}' under '{frames_dir}'. "
                    "Provide one in the frontend, a gain/gains folder, or as a named file in the session root."
                )

        if self.defects_path is None:
            self.defects_path = _find_sidecar_file(
                frames_dir, defects_dir_names, ('defect',)
            )

    def _fetch_leginon_session_data(self):
        session_name = self.params.session_name
        self.leginon_cursor.execute("SELECT * FROM SessionData WHERE name = %s", (session_name,))
        session_result = self.leginon_cursor.fetchone()

        presets_query = """
            SELECT GROUP_CONCAT(DISTINCT p.name ORDER BY LENGTH(p.name) DESC SEPARATOR '|') AS regex_pattern
            FROM PresetData p
            LEFT JOIN SessionData s ON p.`REF|SessionData|session` = s.DEF_id
            WHERE s.DEF_id = %s;
        """
        self.leginon_cursor.execute(presets_query, (session_result["DEF_id"],))
        presets_result = self.leginon_cursor.fetchone()

        return session_result, presets_result["regex_pattern"]

    def _fetch_leginon_images(self, session_name: str):
        query = """
            SELECT DISTINCT
                ai.DEF_id AS image_id,
                ai.filename,
                ai.`MRC|image` AS image_name,
                ai.label,
                SQRT(ai.pixels) AS dimx,
                t.`delta row` AS delta_row,
                t.`delta column` AS delta_column,
                sem.magnification AS mag,
                sem.defocus,
                sem.`SUBD|stage position|a` AS stage_alpha_tilt,
                sem.`SUBD|stage position|x` AS stage_x,
                sem.`SUBD|stage position|y` AS stage_y,
                cem.`exposure time` AS camera_exposure_time,
                cem.`save frames` AS save_frames,
                cem.`frames name` AS frame_names,
                cem.`SUBD|binning|x` AS bining_x,
                cem.`SUBD|binning|y` AS bining_y,
                pd.dose AS preset_dose,
                pd.`exposure time` AS preset_exposure_time,
                pd.dose * POWER(10, -20) * cem.`exposure time` / pd.`exposure time` AS calculated_dose,
                psc.pixelsize AS pixelsize,
                sem.`high tension` / 1000 AS acceleration_voltage,
                psc.pixelsize * cem.`SUBD|binning|x` AS result_pixelSize,
                TemInstrumentData.cs AS spherical_aberration
            FROM AcquisitionImageData ai
            LEFT OUTER JOIN ScopeEMData sem ON ai.`REF|ScopeEMData|scope` = sem.DEF_id
            LEFT OUTER JOIN CameraEMData cem ON ai.`REF|CameraEMData|camera` = cem.DEF_id
            LEFT OUTER JOIN PresetData pd ON ai.`REF|PresetData|preset` = pd.DEF_id
            LEFT OUTER JOIN AcquisitionImageTargetData t ON ai.`REF|AcquisitionImageTargetData|target` = t.DEF_id
            LEFT OUTER JOIN InstrumentData TemInstrumentData ON pd.`REF|InstrumentData|tem` = TemInstrumentData.DEF_id
            LEFT OUTER JOIN InstrumentData CameraInstrumentData ON pd.`REF|InstrumentData|ccdcamera` = CameraInstrumentData.DEF_id
            LEFT OUTER JOIN PixelSizeCalibrationData psc ON
                psc.`REF|InstrumentData|tem` = pd.`REF|InstrumentData|tem`
                AND psc.`REF|InstrumentData|ccdcamera` = pd.`REF|InstrumentData|ccdcamera`
                AND psc.magnification = sem.magnification
                AND psc.DEF_id = (
                    SELECT MAX(psc_inner.DEF_id)
                    FROM PixelSizeCalibrationData psc_inner
                    WHERE psc_inner.`REF|InstrumentData|tem` = pd.`REF|InstrumentData|tem`
                        AND psc_inner.`REF|InstrumentData|ccdcamera` = pd.`REF|InstrumentData|ccdcamera`
                        AND psc_inner.magnification = sem.magnification
                )
            WHERE ai.filename LIKE %s
        """
        self.leginon_cursor.execute(query, (session_name + "%",))
        return self.leginon_cursor.fetchall()

    def _create_image_job(self, db_session: Session, session_result, magellon_session):
        session_name = self.params.session_name
        job = ImageJob(
            # Must match the job_id already handed back to the frontend in
            # the POST response — /export/job/{job_id}/summary looks up
            # ImageJob.oid by that value, and a mismatch (e.g. letting this
            # default-generate its own) means the frontend polls a job_id
            # that will never resolve to a row, so progress silently never
            # appears. Mirrors BaseImporter._create_image_job's pattern.
            oid=self.params.job_id or uuid.uuid4(),
            name=f"Leginon Import: {self.params.magellon_session_name or session_name}",
            description=f"Leginon Import for session: {session_name} in directory: {session_result['image path']}",
            created_date=datetime.now(),
            output_directory=self.params.camera_directory,
            msession_id=magellon_session.oid,
        )
        db_session.add(job)
        db_session.flush()
        return job

    def _check_image_files(self, db_image_list):
        """Stop before queuing any work when the images aren't where the import
        looks for them (usually a Replace Pattern that doesn't match): every
        task would otherwise run without its image, leaving the session with
        no pictures, FFTs or CTF."""
        paths = [image.path for image in db_image_list if image.path]
        missing = [path for path in paths if not os.path.exists(path)]
        if paths and len(missing) == len(paths):
            raise FileNotFoundError(
                f"None of the {len(paths)} images were found, e.g. {missing[0]}. "
                "Check the Replace Type/Pattern/With settings: the pattern must match "
                "the start of this path."
            )
        if missing:
            logger.warning("%d of %d images not found, e.g. %s", len(missing), len(paths), missing[0])

    def _get_default(self, field, fallback):
        return getattr(self.params.default_data, field, fallback) if self.params.default_data else fallback

    def _safe_value(self, value, field, fallback):
        if value is not None and value > 0:
            return value
        return self._get_default(field, fallback)

    def _build_image_records(self, leginon_image_list, session_result, presets_pattern, job, magellon_session):
        db_image_list = []
        db_job_item_list = []
        image_dict = {}
        gpfs_root = os.environ.get('MAGELLON_GPFS_PATH', MAGELLON_GPFS_DIR)

        for image in leginon_image_list:
            filename = image["filename"]

            db_image = Image(
                oid=uuid.uuid4(),
                name=filename,
                magnification=image["mag"],
                defocus=image["defocus"],
                dose=image["calculated_dose"],
                pixel_size=self._safe_value(image["pixelsize"], 'pixel_size', 0.739),
                binning_x=image["bining_x"],
                stage_x=image["stage_x"],
                stage_y=image["stage_y"],
                stage_alpha_tilt=image["stage_alpha_tilt"],
                atlas_dimxy=image["dimx"],
                atlas_delta_row=image["delta_row"],
                atlas_delta_column=image["delta_column"],
                binning_y=image["bining_y"],
                level=0,  # computed after creation via compute_level()
                previous_id=image["image_id"],
                acceleration_voltage=self._safe_value(image["acceleration_voltage"], 'acceleration_voltage', 300),
                spherical_aberration=self._safe_value(
                    (image["spherical_aberration"] * 1000) if image["spherical_aberration"] is not None and image["spherical_aberration"] > 0 else None,
                    'spherical_aberration', 2.7
                ),
                session_id=magellon_session.oid,
            )
            db_image.level = db_image.compute_level(presets_pattern)
            logger.info(f"Created Image for {filename}: spherical_aberration={db_image.spherical_aberration}")
            db_image_list.append(db_image)
            image_dict[filename] = db_image.oid

            frame_name = image.get("frame_names") if self.params.camera_directory else None
            source_frame_path = (os.path.join(self.params.camera_directory, frame_name)
                                 if frame_name else None)
            if self.images_dir:
                source_image_path = os.path.join(self.images_dir, image["image_name"])
            else:
                source_image_path = os.path.join(
                    gpfs_root, session_result["name"], 'home', ORIGINAL_IMAGES_SUB_URL, image["image_name"]
                )

            if not self.images_dir and self.params.replace_type in ("regex", "standard"):
                source_frame_path = custom_replace(
                    source_frame_path, self.params.replace_type,
                    self.params.replace_pattern, self.params.replace_with)
                source_image_path = custom_replace(
                    source_image_path, self.params.replace_type,
                    self.params.replace_pattern, self.params.replace_with)

            # Same gap EPUImporter had: db_image is never constructed with
            # path=, so without this Image.path stays NULL for every
            # Leginon import — breaking anything that resolves an image's
            # file location from the DB instead of the in-flight task DTO
            # (e.g. particle-picking's manual dispatch/batch endpoints).
            db_image.path = source_image_path

            task_oid = uuid.uuid4()
            db_job_task = ImageJobTask(
                oid=task_oid,
                job_id=job.oid,
                frame_name=frame_name or None,
                frame_path=source_frame_path if frame_name else None,
                image_path=source_image_path,
                status_id=1,
                stage=0,
                image_id=db_image.oid,
            )
            db_job_item_list.append(db_job_task)

            # task_id MUST equal db_job_task.oid (FK target on
            # job_event.task_id), and job_id MUST be the actual ImageJob
            # oid — not db_job_task.oid as it was historically.
            task_dto = LeginonFrameTransferTaskDto(
                task_id=task_oid,
                task_alias=f"lftj_{filename}_{task_oid}",
                file_name=filename,
                image_id=db_image.oid,
                image_name=image["image_name"],
                frame_name=frame_name,
                image_path=source_image_path,
                job_id=job.oid,
                frame_path=source_frame_path,
                job_dto=self.params,
                status=1,
                pixel_size=self._safe_value(image["pixelsize"], 'pixel_size', 0.739),
                acceleration_voltage=self._safe_value(image["acceleration_voltage"], 'acceleration_voltage', 300),
                spherical_aberration=self._safe_value(
                    (image["spherical_aberration"] * 1000) if image["spherical_aberration"] is not None and image["spherical_aberration"] > 0 else None,
                    'spherical_aberration', 2.7
                ),
                flip_gain=self._get_default('flip_gain', 0),
                rot_gain=self._get_default('rot_gain', 0),
            )
            logger.info(f"Created task_dto for {filename}: spherical_aberration={task_dto.spherical_aberration}")
            self.params.task_list.append(task_dto)

        return db_image_list, db_job_item_list, image_dict

    def _link_parent_images(self, db_image_list, image_dict):
        for db_image in db_image_list:
            parent_name = db_image.derive_parent_name()
            if parent_name in image_dict:
                db_image.parent_id = image_dict[parent_name]

    def run_tasks(self, db_session: Session,magellon_session :Msession):
        try:
            create_directories(self.params.target_directory)
            # Iterate over each task in the task list and run it synchronously
            for task in self.params.task_list:
                self.run_task(task,magellon_session)
            self.create_atlas_pics(self.params.session_name, db_session,magellon_session)
        except Exception as e:
            print("An unexpected error occurred:", str(e))
        finally:
            self.close_connections()



    def run_task(self, task_dto: LeginonFrameTransferTaskDto,magellon_session :Msession) -> Dict[str, str]:
        try:
            # 1
            self.transfer_frame(task_dto)
            # 2
            if task_dto.job_dto.copy_images:
                target_image_path = task_dto.job_dto.target_directory + "/" + ORIGINAL_IMAGES_SUB_URL + task_dto.image_name
                copy_file(task_dto.image_path, target_image_path)
                task_dto.image_path = target_image_path

            # Generate FFT using the REST API
            self.convert_image_to_png_task(task_dto.image_path, task_dto.job_dto.target_directory)
            self.compute_fft_png_task(task_dto.image_path, task_dto.job_dto.target_directory)
            ctf = self.compute_ctf_task(task_dto.image_path, task_dto)

            if task_dto.frame_name:
                self.compute_motioncor_task(task_dto.image_path, task_dto)
            elif "on the way" not in (ctf or {}).get("message", ""):
                # Nothing was sent to a plugin for this image (an atlas/grid
                # overview: no movie, and CTF skipped for its pixel size), so
                # nothing will ever report it; it's done once its pictures are.
                self._finish_local_task(task_dto)

            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            raise TaskFailedException(f"Task failed with error: {str(e)}")
            # return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}

    def _finish_local_task(self, task_dto) -> None:
        from database import session_local
        from services.job_manager import job_manager
        db = session_local()
        try:
            db.query(ImageJobTask).filter(ImageJobTask.oid == task_dto.task_id).update(
                {ImageJobTask.status_id: 2}, synchronize_session=False)
            db.commit()
        finally:
            db.close()
        try:
            job_manager.record_task_finished(str(task_dto.job_id), str(task_dto.task_id))
        except LookupError:
            pass

    def transfer_frame(self, task_dto):
        try:
            # copy frame if exists
            if task_dto.frame_name:
                frame_path = check_file_exists(self.params.camera_directory, task_dto.frame_name)

                if frame_path:
                    _, file_extension = os.path.splitext(frame_path)
                    target_path = os.path.join(task_dto.job_dto.target_directory, FRAMES_SUB_URL,
                                               task_dto.file_name + FRAMES_SUFFIX + file_extension)
                    copy_file(frame_path, target_path)
        except Exception as e:
            print(f"An error occurred during frame transfer: {e}")

    def open_leginon_connection(self):
        if self.leginon_db_connection is None:
            self.leginon_db_connection = pymysql.connect(
                host=self.params.leginon_mysql_host,
                port=self.params.leginon_mysql_port,
                user=self.params.leginon_mysql_user,
                password=self.params.leginon_mysql_pass,
                database=self.params.leginon_mysql_db,
                cursorclass=pymysql.cursors.DictCursor
            )
            self.leginon_cursor = self.leginon_db_connection.cursor()
            # self.leginon_cursor = self.leginon_db_connection.cursor()

    def close_connections(self):
        if self.leginon_cursor is not None:
            self.leginon_cursor.close()
            self.leginon_cursor = None
        if self.leginon_db_connection is not None:
            self.leginon_db_connection.close()
            self.leginon_db_connection = None

    def convert_image_to_png_task(self, abs_file_path, out_dir):
        try:
            # generates png and thumbnails
            self.mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
            return {"message": "MRC file successfully converted to PNG!"}
        except Exception as e:
            return {"error": str(e)}

    def compute_fft_png_task(self, abs_file_path: str, out_dir: str):
        try:
            fft_path = os.path.join(out_dir, FFT_SUB_URL,
                                    os.path.splitext(os.path.basename(abs_file_path))[0] + FFT_SUFFIX)
            # self.create_image_directory(fft_path)
            # self.compute_fft(img=mic, abs_out_file_name=fft_path)
            self.mrc_service.compute_mrc_fft(mrc_abs_path=abs_file_path, abs_out_file_name=fft_path)
            return {"message": "MRC file successfully converted to fft PNG!"}

        except Exception as e:
            return {"error": str(e)}

    def compute_ctf_task(self, abs_file_path: str, task_dto: LeginonFrameTransferTaskDto):
        try:
            # Validate CTF prerequisites
            pixel_size = task_dto.pixel_size
            spherical_aberration = task_dto.spherical_aberration
            acceleration_voltage = task_dto.acceleration_voltage
            
            logger.info(f"compute_ctf_task: Input values - pixel_size={pixel_size}, spherical_aberration={spherical_aberration}, acceleration_voltage={acceleration_voltage}")
            
            # Validate pixel size (should be <= 5 Angstroms for CTF)
            if pixel_size is None or (pixel_size * 10 ** 10) > 5:
                logger.warning(f"Skipping CTF: pixel size {pixel_size} exceeds 5 Angstroms or is None")
                return {"message": f"Skipping CTF computation (pixel size {pixel_size} too large or invalid)"}
            
            # Validate spherical aberration (should be non-zero and in reasonable range: 1-4 mm typically)
            if spherical_aberration is None or spherical_aberration <= 0 or spherical_aberration > 10:
                logger.warning(f"Skipping CTF: spherical aberration {spherical_aberration} is invalid (should be 1-4 mm)")
                return {"message": f"Skipping CTF computation (invalid spherical aberration {spherical_aberration})"}
            
            # Validate acceleration voltage (should be 100-400 kV typically)
            if acceleration_voltage is None or acceleration_voltage < 100 or acceleration_voltage > 400:
                logger.warning(f"Skipping CTF: acceleration voltage {acceleration_voltage} is out of range (should be 100-400 kV)")
                return {"message": f"Skipping CTF computation (invalid acceleration voltage {acceleration_voltage})"}
            
            dispatch_ctf_task(task_dto.task_id, abs_file_path, task_dto)
            return {"message": "Converting to ctf on the way! " + abs_file_path}

        except Exception as e:
            logger.error(f"Error in compute_ctf_task: {str(e)}", exc_info=True)
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

                # Use gains/defects paths prepared in `create_job` (saved to GPFS)
                gain_path = getattr(self, 'gains_path', None)
                defects_path = getattr(self, 'defects_path', None)

                if not gain_path:
                    raise FileNotFoundError(f"Gains file not configured for session '{task_dto.job_dto.session_name}'. Ensure a gains file was uploaded or placed under GPFS for the session.")

                dispatch_motioncor_task(
                    task_id=task_dto.task_id,
                    gain_path=gain_path,
                    full_image_path=abs_file_path,
                    task_dto=task_dto,
                    defects_path=defects_path,
                    motioncor_settings=settings
                )

                return {"message": f"Converting to motioncor on the way! {abs_file_path}"}

        except Exception as e:
            return {"error": str(e)}

    def create_atlas_pics(self, session_name: str, db_session: Session,magellon_session :Msession):
        try:
            # Execute the first query to get session_id
            query = "SELECT SessionData.DEF_id FROM SessionData WHERE SessionData.name = %s"
            self.leginon_cursor.execute(query, (session_name,))
            session_result = self.leginon_cursor.fetchone()
            leginon_session_id = session_result["DEF_id"]

        except Exception as e:
            print(f"Error fetching session_id: {e}")
            return {"error": f"Error fetching session_id: {e}"}

        query1 = "SELECT * FROM ImageTargetListData WHERE `REF|SessionData|session` = %s AND mosaic = %s"
        mosaic_value = 1  # Execute the first query with parameters
        self.leginon_cursor.execute(query1, (leginon_session_id, mosaic_value))

        label_values = [row['label'] for row in
                        self.leginon_cursor.fetchall()]  # Define the SQL query for the second query

        query2 = """
            SELECT a.DEF_id, SQRT(a.pixels) as dimx, SQRT(a.pixels) as dimy, a.filename,
                   t.`delta row`, t.`delta column`
            FROM AcquisitionImageData a
            LEFT JOIN AcquisitionImageTargetData t ON a.`REF|AcquisitionImageTargetData|target` = t.DEF_id
            WHERE a.`REF|SessionData|session` = %s AND a.label = %s
        """
        label = "Grid"
        # Execute the second query with parameters
        self.leginon_cursor.execute(query2, (leginon_session_id, label))
        # Fetch all the results from the second query
        second_query_results = self.leginon_cursor.fetchall()
        # Create a dictionary to store grouped objects by label

        label_objects = {}

        for row in second_query_results:
            filename_parts = row['filename'].split("_")
            combined_parts = "_".join(filename_parts[1:-1])
            label_match = None
            if combined_parts in label_values:
                label_match = combined_parts

            obj = {
                "id": row['DEF_id'],
                "dimx": row['dimx'],
                "dimy": row['dimy'],
                "filename": row['filename'],
                "delta_row": row['delta row'],
                "delta_column": row['delta column']
            }
            if label_match in label_objects:
                label_objects[label_match].append(obj)
            else:
                label_objects[""] = [obj]

        # images = create_atlas_images(session_id, label_objects)
        # Leginon is queried by its session name; the pictures go to the
        # Magellon session's folder.
        images = create_atlas_images(magellon_session.name if magellon_session else session_name, label_objects)
        atlases_to_insert = []
        for image in images:
            file_name = os.path.basename(image['imageFilePath'])
            file_name_without_extension = os.path.splitext(file_name)[0]
            atlas = Atlas(oid=str(uuid.uuid4()), name=file_name_without_extension, meta=image['imageMap'] , session_id=magellon_session.oid)
            atlases_to_insert.append(atlas)
        # db_session.add_all(atlases_to_insert)
        db_session.bulk_save_objects(atlases_to_insert)
        db_session.commit()

        return {"images": images}


def generate_delete_sql(session_name):
    sql_code = """
        SET FOREIGN_KEY_CHECKS = 0;
        SET @session_id = (SELECT Oid FROM msession WHERE name = %s);
        DELETE FROM image WHERE session_id = @session_id;
        DELETE FROM image_job_task WHERE job_id IN (SELECT oid FROM image_job WHERE msession_id = @session_id);
        DELETE FROM image_job WHERE msession_id = @session_id;
        DELETE FROM atlas WHERE session_id = @session_id;
        DELETE FROM msession WHERE oid = @session_id;
        SET FOREIGN_KEY_CHECKS = 1;
        """

    sql_commands = []
    # Disable foreign key checks
    sql_commands.append("SET FOREIGN_KEY_CHECKS = 0;")
    # Get the session ID based on the session name
    sql_commands.append("SET @session_id = (SELECT Oid FROM msession WHERE name = '{}');".format(session_name))
    # Delete records from image table
    sql_commands.append("DELETE FROM image WHERE session_id = @session_id;")
    # Delete records from frametransferjobitem table
    sql_commands.append(
        "DELETE FROM image_job_task WHERE job_id IN (SELECT Oid FROM image_job WHERE msession_id = @session_id);")
    # Delete records from frametransferjob table
    sql_commands.append("DELETE FROM image_job WHERE msession_id = @session_id;")
    # Delete records from atlas table
    sql_commands.append("DELETE FROM atlas WHERE session_id = @session_id;")
    # Delete records from msession table
    sql_commands.append("DELETE FROM msession WHERE Oid = @session_id;")
    # Re-enable foreign key checks
    sql_commands.append("SET FOREIGN_KEY_CHECKS = 1;")

    return sql_commands
