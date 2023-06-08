import time
from datetime import datetime
import os
import shutil
import json
import uuid
from typing import Dict

import pymysql
from fastapi import APIRouter, Depends, HTTPException

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL
from database import get_db
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto, LeginonImageDto
from models.sqlalchemy_models import Frametransferjob, Frametransferjobitem, Image, Project, Msession
from services.file_service import copy_file, create_directory
from services.mrc_image_service import MrcImageService
from sqlalchemy.orm import Session


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
            # self.query_leginon_db()
            # self.create_directories(self.params.target_directory)
            self.create_job(db_session)
            # self.run_tasks()
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

            # get all the images in the leginon database
            # SQL query
            query = """
                SELECT
                  ai.DEF_id AS image_id,
                  ai.filename,
                  sem.magnification AS mag,
                  sem.defocus,
                  cem.`exposure time` AS camera_exposure_time,
                  cem.`save frames` AS save_frames,
                  cem.`frames name` AS frame_names,
                  pd.dose AS preset_dose,
                  pd.`exposure time` AS preset_exposure_time,
                  pd.dose * POWER(10, -20) * cem.`exposure time` / pd.`exposure time` AS calculated_dose,
                  psc.pixelsize AS pixelsize
                FROM AcquisitionImageData ai
                  LEFT OUTER JOIN ScopeEMData sem
                    ON ai.`REF|ScopeEMData|scope` = sem.DEF_id
                  LEFT OUTER JOIN CameraEMData cem
                    ON ai.`REF|CameraEMData|camera` = cem.DEF_id
                  LEFT OUTER JOIN PresetData pd
                    ON ai.`REF|PresetData|preset` = pd.DEF_id
                  LEFT OUTER JOIN InstrumentData TemInstrumentData
                    ON pd.`REF|InstrumentData|tem` = TemInstrumentData.DEF_id
                  LEFT OUTER JOIN InstrumentData CameraInstrumentData
                    ON pd.`REF|InstrumentData|ccdcamera` = CameraInstrumentData.DEF_id
                  LEFT OUTER JOIN (SELECT
                      psc.pixelsize,
                      psc.`REF|InstrumentData|tem`,
                      psc.`REF|InstrumentData|ccdcamera`,
                      psc.magnification
                    FROM PixelSizeCalibrationData psc) psc
                    ON psc.`REF|InstrumentData|tem` = pd.`REF|InstrumentData|tem`
                    AND psc.`REF|InstrumentData|ccdcamera` = pd.`REF|InstrumentData|ccdcamera`
                    AND psc.magnification = sem.magnification
                WHERE ai.filename LIKE %s
            """
            self.leginon_cursor.execute(query, (session_name + "%",))
            leginon_image_list = self.leginon_cursor.fetchall()
            if len(leginon_image_list) > 0:
                # image_dict = {image["filename"]: image for image in leginon_image_list}
                image_dict = {}
                # Create a new job
                job = Frametransferjob(
                    # Oid=uuid.uuid4(),
                    name="Leginon Import: " + session_name,
                    description="Leginon Import for session: " + session_name + "in directory: " + session_result[
                        "image path"],
                    created_on=datetime.now(),
                    # Set other job properties
                )
                db_session.add(job)
                db_session.flush()  # Flush the session to get the generated Oid

                db_image_list = []
                db_job_item_list = []
                separator = "/"
                for image in leginon_image_list:
                    filename = image["filename"]
                    # image_path = os.path.join(session_result["image path"], filename)
                    image_path = (session_result["image path"] + separator + filename + ".mrc")

                    db_image = Image(Oid=uuid.uuid4(), name=filename, magnification=image["mag"],
                                     defocus=image["defocus"], dose=image["calculated_dose"],
                                     pixelsize=image["pixelsize"],
                                     old_id=image["image_id"], session_id=magellon_session.Oid)
                    # db_session.add(db_image)
                    # db_session.flush()
                    db_image_list.append(db_image)
                    image_dict[filename] = db_image.Oid

                    # Create a new job item and associate it with the job and image
                    job_item = Frametransferjobitem(
                        Oid=uuid.uuid4(),
                        job_id=job.Oid,
                        path=image_path,
                        status=1,
                        steps=0,
                        image_id=db_image.Oid,
                        # Set job item properties
                    )
                    db_job_item_list.append(job_item)
                    # db_session.add(job_item)

                    task = LeginonFrameTransferTaskDto(
                        task_id=uuid.uuid4(),
                        task_alias=f"lftj_{filename}_{self.params.job_id}",
                        image_path=image_path,
                        job_dto=self.params,
                        status=1
                    )
                    self.params.task_list.append(task)
                    # print(f"Filename: {filename}, Spot Size: {spot_size}")

                for db_image in db_image_list:
                    parent_name = '_'.join(db_image.name.split('_')[:-1])
                    if parent_name in image_dict:
                        db_image.parent_id = image_dict[parent_name]

                db_session.bulk_save_objects(db_image_list)
                db_session.bulk_save_objects(db_job_item_list)
            # get all the files in the source directory
            # leginon_image_list = [file for file in os.listdir(self.params.source_directory) if
            #               os.path.isfile(os.path.join(self.params.source_directory, file))]

            # print("hello")

            db_session.commit()  # Commit the changes
        except FileNotFoundError as e:
            print("Source directory not found:", self.params.source_directory)
        except OSError as e:
            print("Error accessing source directory:", self.params.source_directory)
        except Exception as e:
            print("An unexpected error occurred:", str(e))
        finally:
            self.close_connections()

    # def create_tasks(self):
    #     try:
    #         image_list = os.listdir(self.params.source_directory)
    #         for image_file in image_list:
    #             image_path = os.path.join(self.params.source_directory, image_file)
    #             task = LeginonFrameTransferTaskDto(
    #                 task_id=uuid.uuid4(),
    #                 task_alias=f"lftj_{image_file}_{self.params.job_id}",
    #                 image_path=image_path,
    #                 job_dto=self.params,
    #                 status=1
    #             )
    #             self.params.task_list.append(task)
    #
    #     except FileNotFoundError as e:
    #         print("Source directory not found:", self.params.source_directory)
    #     except OSError as e:
    #         print("Error accessing source directory:", self.params.source_directory)
    #     except Exception as e:
    #         print("An unexpected error occurred:", str(e))

    # def query_leginon_session(self):
    #     try:
    #         # Execute the query
    #         query = "SELECT * FROM SessionData WHERE name = %s"
    #         session_name = self.params.session_name
    #         cursor.execute(query, (session_name,))
    #
    #         # Fetch all the results
    #         query_leginon_db(query)
    #
    #         # cursor.close()
    #         # connection.close()
    #     except Exception as e:
    #         print("An unexpected error occurred:", str(e))

    def query_leginon_db(self):
        try:
            # Establish a connection to the database
            self.open_leginon_connection()

            # Execute the query
            query = "SELECT * FROM SessionData WHERE name = %s"
            session_name = self.params.session_name
            self.leginon_cursor.execute(query, (session_name,))

            # Fetch all the results
            results = self.leginon_cursor.fetchall()
            for row in results:
                print(row)
                print(row[4])

        except Exception as e:
            print("An unexpected error occurred:", str(e))
        finally:
            self.close_connections()

    def run_tasks(self):
        try:
            # self.leginon_db_connection = pymysql.connect(**self.params.source_mysql_connection)
            self.open_leginon_connection()
            for task in self.params.task_list:
                self.run_task(task)

        except Exception as e:
            print("An unexpected error occurred:", str(e))
        finally:
            # Close the connection
            self.close_connections()

    def run_task(self, task_dto: LeginonFrameTransferTaskDto) -> Dict[str, str]:
        try:
            copy_file(task_dto.image_path, task_dto.job_dto.target_directory)

            # Retrieve metadata from the old MySQL database
            self.retrieve_metadata_task(task_dto.image_path)

            # Insert metadata into the new MySQL database
            # insert_metadata(metadata)

            # Generate FFT using the REST API
            self.convert_image_to_png_task(task_dto.image_path, task_dto.job_dto.target_directory)
            self.compute_fft_png_task(task_dto.image_path, task_dto.job_dto.target_directory)
            # Acknowledge task completion with the job_id and image name as task ID
            # task_id = f"{image_path.split('/')[-1]}_{job_id}"
            # dag_run_id = "{{ dag_run.id }}"
            # task_instance = TaskInstance(task_id, dag_run_id)
            # task_instance.set_state(TaskState.SUCCESS)
            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}

    def create_directories(self, target_dir: str):
        create_directory(target_dir)
        create_directory(os.path.join(target_dir, FFT_SUB_URL))
        create_directory(os.path.join(target_dir, IMAGE_SUB_URL))
        create_directory(os.path.join(target_dir, THUMBNAILS_SUB_URL))

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

    def retrieve_metadata_task(self, image_name):
        # Implement logic to retrieve metadata from the old MySQL database
        query = "SELECT defocus, mag, filename, pixelsize, dose FROM AcquisitionImageData WHERE imagename=%s"
        image_data = []
        try:
            # with self.source_db_connection.cursor() as source_cursor:
            #     # Execute the query for each image data
            #     source_cursor.execute(query, (image_name,))
            #     rows = source_cursor.fetchall()
            if self.leginon_cursor is None:
                self.leginon_cursor = self.leginon_db_connection.cursor()

            self.leginon_cursor.execute(query, (image_name,))
            rows = self.leginon_cursor.fetchall()

            for row in rows:
                defocus, mag, filename, pixelsize, dose = row
                image_dto = LeginonImageDto(defocus=defocus, mag=mag, filename=filename, pixelsize=pixelsize, dose=dose)
                image_data.append(image_dto)

            # Commit the changes
            # self.source_db_connection.commit()
        except Exception as e:
            # Handle the exception here (e.g., print an error message)
            print(f"Error: {str(e)}")

        return image_data

    def insert_metadata_task(self, connection_string: str, image_data: dict):
        # Implement logic to insert metadata into the new MySQL database
        # Prepare the SQL query
        query = """
        INSERT INTO image (
            Oid,
            name,
            path,
            parent,
            session,
            magnification,
            dose,
            defocus
        )
        VALUES (
            %(Oid)s,
            %(name)s,
            %(path)s,
            %(parent)s,
            %(session)s,
            %(magnification)s,
            %(dose)s,
            %(defocus)s
        )
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            path = VALUES(path),
            parent = VALUES(parent),
            session = VALUES(session),
            magnification = VALUES(magnification),
            dose = VALUES(dose),
            defocus = VALUES(defocus)
        """
        source_cursor = self.leginon_db_connection.cursor()
        try:
            # Execute the query for each image data
            for data in image_data:
                source_cursor.execute(query, data)

                # Commit the changes
                self.leginon_db_connection.commit()

        except Exception as e:
            # Handle the exception here (e.g., print an error message)
            print(f"Error: {str(e)}")

        finally:
            # Close the cursor
            source_cursor.close()

    def convert_image_to_png_task(self, abs_file_path, out_dir):
        try:
            # out_dir = "C:/temp/images/"
            self.mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path,
                                                out_dir=out_dir)  # generates png and thumbnails
            return {"message": "MRC file successfully converted to PNG!"}

        except Exception as e:
            return {"error": str(e)}

    def compute_fft_png_task(self, abs_file_path: str, out_dir: str):
        try:
            fft_path = os.path.join(out_dir, FFT_SUB_URL,
                                    os.path.splitext(os.path.basename(abs_file_path))[0] + "_FFT.png")
            # self.create_image_directory(fft_path)
            # self.compute_fft(img=mic, abs_out_file_name=fft_path)
            self.mrc_service.compute_file_fft(mrc_abs_path=abs_file_path, abs_out_file_name=fft_path)
            return {"message": "MRC file successfully converted to fft PNG!"}

        except Exception as e:
            return {"error": str(e)}
