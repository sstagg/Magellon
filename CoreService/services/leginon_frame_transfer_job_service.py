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
from fastapi import Depends

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX
from database import get_db
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto
from models.sqlalchemy_models import Frametransferjob, Frametransferjobitem, Image, Project, Msession
from services.file_service import copy_file, create_directory, check_file_exists
from services.mrc_image_service import MrcImageService
from sqlalchemy.orm import Session

MAX_RETRIES = 3
logger = logging.getLogger(__name__)


class TaskFailedException(Exception):
    pass


# def check_file_exists(folder, filename_without_extension):
#     file_pattern = os.path.join(folder, filename_without_extension + '.*')
#     matching_files = glob.glob(file_pattern)
#
#     if matching_files:
#         return os.path.basename(matching_files[0])
#
#     return None

# Recursive function to update levels
# def update_levels(image_list: list[Image], parent_id=None, level=0):
#     for image in image_list:
#         if image.parent_id == parent_id:
#             image.level = level
#             update_levels(image_list, parent_id=image.Oid, level=level + 1)  # Recursive function to update levels


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
            self.create_job(db_session)
            end_time = time.time()  # Stop measuring the time
            execution_time = end_time - start_time
            return {'status': 'success', 'message': 'Task completed successfully.',
                    'execution_time': f'{execution_time} seconds'}
        except Exception as e:
            return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}

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
                    magellon_session = Msession(name=magellon_session_name, project_id=magellon_project.Oid)
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

            presets_query = """
            SELECT GROUP_CONCAT(DISTINCT p.name ORDER BY LENGTH(p.name) DESC SEPARATOR '|')  AS regex_pattern FROM PresetData p
            LEFT JOIN SessionData s ON  p.`REF|SessionData|session` = s.DEF_id
            WHERE s.DEF_id = %s;
            """
            self.leginon_cursor.execute(presets_query, (session_result["DEF_id"],))
            presets_result = self.leginon_cursor.fetchone()
            print(presets_result)

            # presets_results = self.leginon_cursor.fetchall()
            # for presets_result in presets_results:
            #     print(presets_result)

            # get all the images in the leginon database
            # SQL query
            query = """
                SELECT DISTINCT
                    ai.DEF_id AS image_id,
                    ai.filename,
                    ai.`MRC|image` AS image_name,
                    sem.magnification AS mag,
                    sem.defocus,
                    cem.`exposure time` AS camera_exposure_time,
                    cem.`save frames` AS save_frames,
                    cem.`frames name` AS frame_names,
                    cem.`SUBD|binning|x` AS bining_x,
                    cem.`SUBD|binning|y` AS bining_y,
                    pd.dose AS preset_dose,
                    pd.`exposure time` AS preset_exposure_time,
                    pd.dose * POWER(10, -20) * cem.`exposure time` / pd.`exposure time` AS calculated_dose,
                    psc.pixelsize AS pixelsize,
                    psc.pixelsize * cem.`SUBD|binning|x` AS result_pixelSize
                FROM AcquisitionImageData ai
                LEFT OUTER JOIN ScopeEMData sem ON ai.`REF|ScopeEMData|scope` = sem.DEF_id
                LEFT OUTER JOIN CameraEMData cem ON ai.`REF|CameraEMData|camera` = cem.DEF_id
                LEFT OUTER JOIN PresetData pd ON ai.`REF|PresetData|preset` = pd.DEF_id
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

            # wants to copy image from target_dir + image.name to base_dir + session_name + images dir + image.name
            # wants to copy image from camera_dir + frame.name to base_dir + session_name + frames dir + image.name_frame

            if len(leginon_image_list) > 0:
                # image_dict = {image["filename"]: image for image in leginon_image_list}
                image_dict = {}
                # Create a new job
                job = Frametransferjob(
                    # Oid=uuid.uuid4(),
                    name="Leginon Import: " + session_name,
                    description="Leginon Import for session: " +
                                session_name + "in directory: " + session_result["image path"],
                    created_on=datetime.now(), path=session_result["image path"],
                    output_dir=self.params.camera_directory
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

                    db_image = Image(Oid=uuid.uuid4(), name=filename, magnification=image["mag"],
                                     defocus=image["defocus"], dose=image["calculated_dose"],
                                     pixel_size=image["pixelsize"], binning_x=image["bining_x"],
                                     binning_y=image["bining_y"], level=get_image_levels(filename,presets_result["regex_pattern"]),
                                     old_id=image["image_id"], session_id=magellon_session.Oid)
                    # get_image_levels(filename,presets_result["regex_pattern"])
                    # db_session.add(db_image)
                    # db_session.flush()
                    db_image_list.append(db_image)
                    image_dict[filename] = db_image.Oid

                    # source_image_path = (session_result["image path"] + separator + filename + ".mrc")
                    # change logic to use image's director instead'
                    source_frame_path = os.path.join(self.params.camera_directory, image["frame_names"])
                    source_image_path = os.path.join(session_result["image path"], image["image_name"])

                    # Create a new job item and associate it with the job and image
                    job_item = Frametransferjobitem(
                        Oid=uuid.uuid4(),
                        job_id=job.Oid,
                        frame_name=image["frame_names"],
                        frame_path=source_frame_path,
                        image_name=image["image_name"],
                        image_path=source_image_path,
                        status=1,
                        steps=0,
                        image_id=db_image.Oid,
                        # Set job item properties
                    )
                    db_job_item_list.append(job_item)
                    # db_session.add(job_item)

                    # Get the file name and extension from the source path
                    # source_filename, source_extension = os.path.splitext(source_image_path)

                    task = LeginonFrameTransferTaskDto(
                        task_id=uuid.uuid4(),
                        task_alias=f"lftj_{filename}_{self.params.job_id}",
                        file_name=f"{filename}",
                        image_name=image["image_name"],
                        frame_name=image["frame_names"],
                        image_path=source_image_path,
                        frame_path=source_frame_path,
                        # target_path=self.params.target_directory + "/frames/" + f"{image['frame_names']}{source_extension}",
                        job_dto=self.params,
                        status=1
                    )
                    self.params.task_list.append(task)
                    # print(f"Filename: {filename}, Spot Size: {spot_size}")

                for db_image in db_image_list:
                    parent_name = '_'.join(db_image.name.split('_')[:-1])
                    if parent_name in image_dict:
                        db_image.parent_id = image_dict[parent_name]

                # update_levels(db_image_list)

                db_session.bulk_save_objects(db_image_list)
                db_session.bulk_save_objects(db_job_item_list)

                # get all the files in the source directory
                # print("hello")

                # update_levels_query = text("""
                #     SET @tlevel = 1;
                #     UPDATE image set level=NULL;
                #     UPDATE image SET level = 0 WHERE parent_id IS NULL;
                #     while  @tlevel < 8 do
                #         UPDATE image AS child
                #         JOIN image AS parent ON child.parent_id = parent.oid
                #         SET child.level = @tlevel + 1
                #         WHERE parent.level = @tlevel;
                #
                #         SET @tlevel = @tlevel + 1;
                #     end while;""")
                # db_session.execute(update_levels_query)
                db_session.commit()  # Commit the changes

                if self.params.if_do_subtasks if hasattr(self.params, 'if_do_subtasks') else True:
                    self.run_tasks()
                # self.create_test_tasks()
        except FileNotFoundError as e:
            print("Source directory not found:", self.params.source_directory)
        except OSError as e:
            print("Error accessing source directory:", self.params.source_directory)
        except Exception as e:
            print("An unexpected error occurred:", str(e))
        finally:
            self.close_connections()

    # def create_test_tasks(self):
    #     # get all the files in the source directory
    #     leginon_image_list = [file for file in os.listdir(self.params.camera_directory) if
    #                           os.path.isfile(os.path.join(self.params.camera_directory, file))]
    #     # self.create_directories()
    #     self.params.task_list.clear()
    #     for image in leginon_image_list:
    #         task = LeginonFrameTransferTaskDto(
    #             task_id=uuid.uuid4(),
    #             task_alias=f"lftj_{image}_{self.params.job_id}",
    #             file_name=f"{image}",
    #             image_path=self.params.camera_directory + "/" + image,
    #             job_dto=self.params,
    #             status=1
    #         )
    #         self.params.task_list.append(task)
    #     self.run_tasks()

    def run_tasks(self):
        try:
            # directory_path = os.path.join(self.params.target_directory, self.params.session_name)
            create_directories(self.params.target_directory)
            # self.create_directories(self.params.target_directory + "/" + self.params.session_name)
            # self.open_leginon_connection()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # The run_task function is submitted to the executor using executor.submit, and the resulting Future
                # objects are stored in a dictionary future_to_task to keep track of each task.
                future_to_task = {executor.submit(self.run_task, task): task for task in
                                  self.params.task_list}  # LeginonFrameTransferTaskDto

                # The as_completed function from concurrent.futures is used to iterate through completed futures as
                # they become available. Within the loop, the code checks for task results and implements the retry
                # logic by catching exceptions and retrying up to the maximum retry count.
                for future in concurrent.futures.as_completed(future_to_task):
                    task = future_to_task[future]
                    retry_count = 0
                    while retry_count < MAX_RETRIES:
                        try:
                            future.result()
                            print(f"Task completed successfully: {task.task_alias}")
                            break  # Task completed successfully, exit the retry loop
                        except TaskFailedException as e:
                            print(f"Task failed: {str(e)}")
                            retry_count += 1
                            if retry_count < MAX_RETRIES:
                                print(f"Retrying... Attempt {retry_count}")
                                time.sleep(1)  # Add a small delay before retrying

                    if retry_count == MAX_RETRIES:
                        print(f"Max retries exceeded for task: {task.task_alias}")
                        # Perform any additional handling for failed tasks
        except Exception as e:
            print("An unexpected error occurred:", str(e))
        # finally:
        #     self.close_connections()

    # ```mermaid
    # graph LR
    #     A(Copy Image) --> B(Copy Frame)
    #     B --> C(Convert Image to PNG)
    #     C --> D(Compute FFT)
    # ```
    def run_task(self, task_dto: LeginonFrameTransferTaskDto) -> Dict[str, str]:
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
            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            raise TaskFailedException(f"Task failed with error: {str(e)}")
            # return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}

    def transfer_frame(self, task_dto):
        # copy frame if exists
        if task_dto.frame_name:
            frame_path = check_file_exists(self.params.camera_directory, task_dto.frame_name)

            if frame_path:
                _, file_extension = os.path.splitext(frame_path)
                target_path = os.path.join(task_dto.job_dto.target_directory, FRAMES_SUB_URL,
                                           task_dto.file_name + FRAMES_SUFFIX + file_extension)
                copy_file(frame_path, target_path)

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
        # if self.magellon_db_connection is not None:
        #     self.magellon_db_connection.close()
        #     self.magellon_db_connection = None

    def convert_image_to_png_task(self, abs_file_path, out_dir):
        try:
            self.mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path,
                                                out_dir=out_dir)  # generates png and thumbnails
            return {"message": "MRC file successfully converted to PNG!"}

        except Exception as e:
            return {"error": str(e)}

    def compute_fft_png_task(self, abs_file_path: str, out_dir: str):
        try:
            fft_path = os.path.join(out_dir, FFT_SUB_URL,
                                    os.path.splitext(os.path.basename(abs_file_path))[0] + FFT_SUFFIX)
            # self.create_image_directory(fft_path)
            # self.compute_fft(img=mic, abs_out_file_name=fft_path)
            self.mrc_service.compute_file_fft(mrc_abs_path=abs_file_path, abs_out_file_name=fft_path)
            return {"message": "MRC file successfully converted to fft PNG!"}

        except Exception as e:
            return {"error": str(e)}
