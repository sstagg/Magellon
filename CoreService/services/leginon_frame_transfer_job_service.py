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
from fastapi import Depends, HTTPException

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX, app_settings, ATLAS_SUB_URL, CTF_SUB_URL, FAO_SUB_URL

from core.helper import dispatch_ctf_task, dispatch_motioncor_task
from database import get_db
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto, ImportTaskDto
# from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto
from models.sqlalchemy_models import Image, Project, Msession, ImageJob, ImageJobTask, Atlas
from services.atlas import create_atlas_images
from services.file_service import copy_file, create_directory, check_file_exists
from services.helper import custom_replace, get_parent_name
from services.mrc_image_service import MrcImageService
from sqlalchemy.orm import Session

MAX_RETRIES = 3
logger = logging.getLogger(__name__)


class TaskFailedException(Exception):
    pass


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

    def setup(self, input_json: str):
        input_data = json.loads(input_json)
        self.params = LeginonFrameTransferJobDto(**input_data)

    def setup_data(self, input_data: LeginonFrameTransferJobDto):
        self.params = input_data

    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        try:
            start_time = time.time()  # Start measuring the time
            result = self.create_job(db_session)
            end_time = time.time()  # Stop measuring the time

            execution_time = end_time - start_time
            return result

        except Exception as e:
            return {'status': 'failure', 'message': f'Job failed with error: {str(e)} Job ID: {self.params.job_id}'}

    def create_job(self, db_session: Session):
        try:

            magellon_project: Project = None
            magellon_session: Msession = None
            if self.params.magellon_project_name is not None:
                magellon_project = db_session.query(Project).filter(
                    Project.name == self.params.magellon_project_name).first()
                if not magellon_project:
                    magellon_project = Project(name=self.params.magellon_project_name)
                    db_session.add(magellon_project)
                    db_session.commit()
                    db_session.refresh(magellon_project)

            magellon_session_name = self.params.magellon_session_name or self.params.session_name

            if self.params.magellon_session_name is not None:
                magellon_session = db_session.query(Msession).filter(
                    Msession.name == magellon_session_name).first()
                if not magellon_session:
                    magellon_session = Msession(name=magellon_session_name, project_id=magellon_project.oid)
                    db_session.add(magellon_session)
                    db_session.commit()
                    db_session.refresh(magellon_session)

            self.open_leginon_connection()

            # get the session object from the database
            session_name = self.params.session_name
            query = "SELECT * FROM SessionData WHERE name = %s"
            self.leginon_cursor.execute(query, (session_name,))
            # Fetch all the results
            session_result = self.leginon_cursor.fetchone()


            # self.create_atlas_pics(self.params.session_name, db_session,magellon_session)
            # return

            # create directories
            presets_query = """
            SELECT GROUP_CONCAT(DISTINCT p.name ORDER BY LENGTH(p.name) DESC SEPARATOR '|')  AS regex_pattern FROM PresetData p
            LEFT JOIN SessionData s ON  p.`REF|SessionData|session` = s.DEF_id
            WHERE s.DEF_id = %s;
            """
            self.leginon_cursor.execute(presets_query, (session_result["DEF_id"],))
            presets_result = self.leginon_cursor.fetchone()
            print(presets_result)

            # get all the images in the leginon database
            # SQL query
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
                    sem.`high tension`  / 1000 AS acceleration_voltage,
                    psc.pixelsize * cem.`SUBD|binning|x` AS result_pixelSize,
                    TemInstrumentData.cs AS spherical_aberration
                FROM AcquisitionImageData ai
                LEFT OUTER JOIN ScopeEMData sem ON ai.`REF|ScopeEMData|scope` = sem.DEF_id
                LEFT OUTER JOIN CameraEMData cem ON ai.`REF|CameraEMData|camera` = cem.DEF_id
                LEFT OUTER JOIN PresetData pd ON ai.`REF|PresetData|preset` = pd.DEF_id
                LEFT OUTER JOIN AcquisitionImageTargetData t   ON ai.`REF|AcquisitionImageTargetData|target` = t.DEF_id
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
            leginon_image_list = self.leginon_cursor.fetchall()


            if len(leginon_image_list) > 0:
                # image_dict = {image["filename"]: image for image in leginon_image_list}
                image_dict = {}
                # Create a new job
                job = ImageJob(
                    # Oid=uuid.uuid4(),
                    name="Leginon Import: " + session_name,
                    description="Leginon Import for session: " +
                                session_name + "in directory: " +
                                session_result["image path"],
                    created_date=datetime.now(),  #path=session_result["image path"],
                    output_directory=self.params.camera_directory,
                    msession_id=magellon_session.oid
                    # Set other job properties
                )
                db_session.add(job)
                db_session.flush()  # Flush the session to get the generated Oid

                db_image_list = []
                db_job_item_list = []
                separator = "/"
                for image in leginon_image_list:
                    filename = image["filename"]
                    # source_image_path = os.path.join(session_result["image path"], filename)

                    db_image = Image(oid=uuid.uuid4(),
                                     name=filename,
                                     frame_name=image["frame_names"],
                                     magnification=image["mag"],
                                     defocus=image["defocus"],
                                     dose=image["calculated_dose"],
                                     pixel_size=image["pixelsize"],
                                     binning_x=image["bining_x"],
                                     stage_x=image["stage_x"],
                                     stage_y=image["stage_y"],
                                     stage_alpha_tilt=image["stage_alpha_tilt"],
                                     atlas_dimxy=image["dimx"],
                                     atlas_delta_row=image["delta_row"],
                                     atlas_delta_column=image["delta_column"],
                                     binning_y=image["bining_y"],
                                     level=get_image_levels(filename, presets_result["regex_pattern"]),
                                     previous_id=image["image_id"],
                                     acceleration_voltage=image["acceleration_voltage"],
                                     spherical_aberration=image["spherical_aberration"],
                                     session_id=magellon_session.oid)
                    # get_image_levels(filename,presets_result["regex_pattern"])
                    # db_session.add(db_image)
                    # db_session.flush()
                    db_image_list.append(db_image)
                    image_dict[filename] = db_image.oid
                    # image_dict = {db_image.name: db_image.Oid for db_image in db_image_list}

                    # source_image_path = (session_result["image path"] + separator + filename + ".mrc")
                    # change logic to use image's director instead'
                    source_frame_path = os.path.join(self.params.camera_directory, image["frame_names"])
                    source_image_path = os.path.join(session_result["image path"], image["image_name"])

                    #TODO:
                    # source_frame_path = source_frame_path.replace("/gpfs/", "Y:/")
                    # source_image_path = source_image_path.replace("/gpfs/", "Y:/")

                    if self.params.replace_type == "regex" or self.params.replace_type == "standard":
                        source_frame_path = custom_replace(source_frame_path, self.params.replace_type,
                                                           self.params.replace_pattern, self.params.replace_with)
                        source_image_path = custom_replace(source_image_path, self.params.replace_type,
                                                           self.params.replace_pattern, self.params.replace_with)

                    # Create a new job item and associate it with the job and image
                    job_item = ImageJobTask(
                        oid=uuid.uuid4(),
                        job_id=job.oid,
                        frame_name=image["frame_names"] if image.get("frame_names") else None,
                        frame_path=source_frame_path +".tif" if image.get("frame_names") else None,
                        image_path=source_image_path,
                        status_id=1,
                        stage=0,
                        image_id=db_image.oid,
                        # Set job item properties
                    )
                    db_job_item_list.append(job_item)
                    # db_session.add(job_item)

                    # Get the file name and extension from the source path
                    # source_filename, source_extension = os.path.splitext(source_image_path)

                    task = LeginonFrameTransferTaskDto(
                        task_id=uuid.uuid4(),
                        task_alias=f"lftj_{filename}_{job_item.oid}",
                        file_name=f"{filename}",
                        image_id=db_image.oid,
                        image_name=image["image_name"],
                        frame_name=image["frame_names"],
                        image_path=source_image_path,
                        job_id=job_item.oid,

                        frame_path=source_frame_path,
                        # target_path=self.params.target_directory + "/frames/" + f"{image['frame_names']}{source_extension}",
                        job_dto=self.params,
                        status=1,
                        pixel_size=image["pixelsize"],
                        acceleration_voltage=image["acceleration_voltage"],
                        spherical_aberration=image["spherical_aberration"]
                    )
                    self.params.task_list.append(task)
                    # print(f"Filename: {filename}, Spot Size: {spot_size}")

                for db_image in db_image_list:
                    parent_name = get_parent_name(db_image.name)
                    if parent_name in image_dict:
                        db_image.parent_id = image_dict[parent_name]

                # update_levels(db_image_list)

                db_session.bulk_save_objects(db_image_list)
                db_session.bulk_save_objects(db_job_item_list)

                db_session.commit()  # Commit the changes

                if self.params.if_do_subtasks if hasattr(self.params, 'if_do_subtasks') else True:
                    self.run_tasks(db_session,magellon_session )

            return {'status': 'success', 'message': 'Job completed successfully.', "job_id": job_item.oid}
            # self.create_test_tasks()
        except FileNotFoundError as e:
            error_message = f"Source directory not found: {self.params.source_directory}"
            logger.error(error_message, exc_info=True)
            return {"error": error_message, "exception": str(e)}
        except OSError as e:
            error_message = f"Error accessing source directory: {self.params.source_directory}"
            logger.error(error_message, exc_info=True)
            return {"error": error_message, "exception": str(e)}
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            logger.error(error_message, exc_info=True)
            return {"error": error_message, "exception": str(e)}

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
            self.compute_ctf_task(task_dto.image_path, task_dto)

            if task_dto.frame_name:
                self.compute_motioncor_task(task_dto.frame_path, task_dto)

            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            raise TaskFailedException(f"Task failed with error: {str(e)}")
            # return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}

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
            if (task_dto.pixel_size * 10 ** 10) <= 5:
                dispatch_ctf_task(task_dto.task_id, abs_file_path, task_dto)
                return {"message": "Converting to ctf on the way! " + abs_file_path}

        except Exception as e:
            return {"error": str(e)}

    def compute_motioncor_task(self, abs_file_path: str, task_dto: ImportTaskDto):
        try:
            settings = {
                'FmDose': 1.0,
                'PatchesX': 7,
                'PatchesY': 7,
                'Group': 4
            }


            dispatch_motioncor_task(
                task_id = task_dto.task_id,
                full_image_path= abs_file_path+".tif",
                task_dto= task_dto,
                motioncor_settings= settings
            )
            return {"message": "Converting to ctf on the way! " + abs_file_path}

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
        images = create_atlas_images(session_name, label_objects)
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
