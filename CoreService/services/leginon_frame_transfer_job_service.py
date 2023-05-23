import os
import shutil
import json
import uuid

from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferTaskDto
from services.file_service import copy_file


class LeginonFrameTransferJobService:
    def __init__(self):
        self.params: LeginonFrameTransferJobDto = None

    def setup(self, input_json: str):
        input_data = json.loads(input_json)
        self.params = LeginonFrameTransferJobDto(**input_data)

    def process(self):
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

        try:
            for task in self.params.task_list:
                self.process_task(task)
        except Exception as e:
            print("An unexpected error occurred:", str(e))

    def process_task(self, task_dto: LeginonFrameTransferTaskDto):
        copy_file(task_dto.image_path, task_dto.job_dto.target_directory)

        # Retrieve metadata from the old MySQL database
        self.retrieve_metadata(task_dto.image_path)

        # Insert metadata into the new MySQL database
        # insert_metadata(metadata)

        # Generate FFT using the REST API
        # generate_fft(image_path)

        # Acknowledge task completion with the job_id and image name as task ID
        # task_id = f"{image_path.split('/')[-1]}_{job_id}"
        # dag_run_id = "{{ dag_run.id }}"
        # task_instance = TaskInstance(task_id, dag_run_id)
        # task_instance.set_state(TaskState.SUCCESS)

    def retrieve_metadata(self, image_name):
        # Implement logic to retrieve metadata from the old MySQL database
        pass

    def insert_metadata(self, metadata, job_id):
        # Implement logic to insert metadata into the new MySQL database
        pass

    def generate_fft(self, image_path):
        # Implement logic to generate FFT of the image through the REST API
        pass
