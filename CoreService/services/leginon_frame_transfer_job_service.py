import os
import shutil
import json
import uuid
from typing import Dict

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto
from services.file_service import copy_file, create_directory
from services.mrc_image_service import MrcImageService

mrc_service = MrcImageService()


class LeginonFrameTransferJobService:
    def __init__(self):
        self.params: LeginonFrameTransferJobDto = None

    def setup(self, input_json: str):
        input_data = json.loads(input_json)
        self.params = LeginonFrameTransferJobDto(**input_data)

    def setup_data(self, input_data: LeginonFrameTransferJobDto):
        self.params = input_data

    def process(self):
        self.create_directories(self.params.target_directory)
        self.create_tasks()

        self.run_tasks()

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
            for task in self.params.task_list:
                self.run_task(task)
        except Exception as e:
            print("An unexpected error occurred:", str(e))

    def run_task(self, task_dto: LeginonFrameTransferTaskDto)-> Dict[str, str]:
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

    def retrieve_metadata_task(self, image_name):
        # Implement logic to retrieve metadata from the old MySQL database
        pass

    def insert_metadata_task(self, metadata, job_id):
        # Implement logic to insert metadata into the new MySQL database
        pass

    def generate_fft(self, image_path):
        # Implement logic to generate FFT of the image through the REST API
        pass

    def convert_image_to_png_task(self, abs_file_path, out_dir):
        try:
            # out_dir = "C:/temp/images/"
            mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)  # generates png and thumbnails
            return {"message": "MRC file successfully converted to PNG!"}

        except Exception as e:
            return {"error": str(e)}

    def compute_fft_png_task(self, abs_file_path: str, out_dir: str):
        try:
            fft_path = os.path.join(out_dir, FFT_SUB_URL,
                                    os.path.splitext(os.path.basename(abs_file_path))[0] + "_FFT.png")
            # self.create_image_directory(fft_path)
            # self.compute_fft(img=mic, abs_out_file_name=fft_path)
            mrc_service.compute_file_fft(mrc_abs_path=abs_file_path, abs_out_file_name=fft_path)
            return {"message": "MRC file successfully converted to fft PNG!"}

        except Exception as e:
            return {"error": str(e)}
