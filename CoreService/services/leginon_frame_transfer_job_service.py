import os
import shutil
import json
import uuid
from typing import Dict

import pymysql

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto, LeginonImageDto
from services.db_service import execute_sql_query
from services.file_service import copy_file, create_directory
from services.mrc_image_service import MrcImageService


class LeginonFrameTransferJobService:

    def __init__(self):
        self.params: LeginonFrameTransferJobDto = None
        self.mrc_service = MrcImageService()
        self.source_db_connection: pymysql.Connection = None
        self.source_cursor: pymysql.cursors.Cursor = None
        self.magellon_db_connection: pymysql.Connection = None
        self.magellon_cursor: pymysql.cursors.Cursor = None

    def setup(self, input_json: str):
        input_data = json.loads(input_json)
        self.params = LeginonFrameTransferJobDto(**input_data)

    def setup_data(self, input_data: LeginonFrameTransferJobDto):
        self.params = input_data

    def process(self) -> Dict[str, str]:
        try:
            self.create_directories(self.params.target_directory)
            self.create_tasks()
            self.run_tasks()
            return {'status': 'success', 'message': 'Task completed successfully.'}
        except Exception as e:
            return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}

    def create_tasks(self):
        try:
            image_list = os.listdir(self.params.source_directory)
            for image_file in image_list:
                image_path = os.path.join(self.params.source_directory, image_file)
                task = LeginonFrameTransferTaskDto(
                    task_id=uuid.uuid4(),
                    task_alias=f"lftj_{image_file}_{self.params.job_id}",
                    image_path=image_path,
                    job_dto=self.params,
                    status=1
                )
                self.params.task_list.append(task)

        except FileNotFoundError as e:
            print("Source directory not found:", self.params.source_directory)
        except OSError as e:
            print("Error accessing source directory:", self.params.source_directory)
        except Exception as e:
            print("An unexpected error occurred:", str(e))

    def run_tasks(self):
        try:
            self.source_db_connection = pymysql.connect(**self.params.source_mysql_connection)
            for task in self.params.task_list:
                self.run_task(task)

        except Exception as e:
            print("An unexpected error occurred:", str(e))
        finally:
            # Close the connection
            self.close_cursores()
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

    def close_cursores(self):
        if self.source_cursor is not None:
            self.source_cursor.close()
            self.source_cursor = None
        if self.magellon_cursor is not None:
            self.magellon_cursor.close()
            self.magellon_cursor = None

    def close_connections(self):
        if self.source_db_connection is not None:
            self.source_db_connection.close()
            self.source_db_connection = None
        if self.magellon_db_connection is not None:
            self.magellon_db_connection.close()
            self.magellon_db_connection = None

    def retrieve_metadata_task(self, image_name):
        # Implement logic to retrieve metadata from the old MySQL database
        query = "SELECT defocus, mag, filename, pixelsize, dose FROM AcquisitionImageData WHERE imagename=%s"
        image_data = []
        try:
            # with self.source_db_connection.cursor() as source_cursor:
            #     # Execute the query for each image data
            #     source_cursor.execute(query, (image_name,))
            #     rows = source_cursor.fetchall()
            if self.source_cursor is None:
                self.source_cursor = self.source_db_connection.cursor()

            self.source_cursor.execute(query, (image_name,))
            rows = self.source_cursor.fetchall()

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
        source_cursor = self.source_db_connection.cursor()
        try:
            # Execute the query for each image data
            for data in image_data:
                source_cursor.execute(query, data)

                # Commit the changes
                self.source_db_connection.commit()

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
