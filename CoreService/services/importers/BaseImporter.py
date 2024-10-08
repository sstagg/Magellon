import os
from abc import ABC, abstractmethod

from core.helper import create_directory, dispatch_ctf_task
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, ATLAS_SUB_URL, CTF_SUB_URL

class BaseImporter(ABC):
    def __init__(self):
        self.params = None
        self.db_session = None
        self.job = None

    def setup(self, input_data):
        self.params = input_data

    def process(self, db_session):
        self.db_session = db_session
        try:
            self.create_job()
            self.import_data()
            self.process_imported_data()
            self.post_processing()  # Template Method
            return {'status': 'success', 'message': 'Import completed successfully.', "job_id": self.params.job_id}
        except Exception as e:
            return {'status': 'failure', 'message': f'Import failed with error: {str(e)} Job ID: {self.params.job_id}'}

    def create_job(self):
        # Implementation remains the same as in the previous artifact

    def create_or_get_session(self):
        # Implementation remains the same as in the previous artifact

    def create_or_get_project(self):
        # Implementation remains the same as in the previous artifact

    @abstractmethod
    def import_data(self):
        pass

    @abstractmethod
    def process_imported_data(self):
        pass

    # Template Method
    def post_processing(self):
        self.create_directories()
        self.process_images()

    def create_directories(self):
        create_directory(self.params.target_directory)
        create_directory(os.path.join(self.params.target_directory, ORIGINAL_IMAGES_SUB_URL))
        create_directory(os.path.join(self.params.target_directory, FRAMES_SUB_URL))
        create_directory(os.path.join(self.params.target_directory, FFT_SUB_URL))
        create_directory(os.path.join(self.params.target_directory, IMAGE_SUB_URL))
        create_directory(os.path.join(self.params.target_directory, THUMBNAILS_SUB_URL))
        create_directory(os.path.join(self.params.target_directory, ATLAS_SUB_URL))
        create_directory(os.path.join(self.params.target_directory, CTF_SUB_URL))

    def process_images(self):
        for task in self.get_image_tasks():
            self.convert_image_to_png(task)
            self.compute_fft_png(task)
            self.compute_ctf(task)

    @abstractmethod
    def get_image_tasks(self):
        pass

    def convert_image_to_png(self, task):
        try:
            self.mrc_service.convert_mrc_to_png(abs_file_path=task.image_path, out_dir=self.params.target_directory)
        except Exception as e:
            print(f"Error converting image to PNG: {str(e)}")

    def compute_fft_png(self, task):
        try:
            fft_path = os.path.join(self.params.target_directory, FFT_SUB_URL,
                                    os.path.splitext(os.path.basename(task.image_path))[0] + FFT_SUFFIX)
            self.mrc_service.compute_file_fft(mrc_abs_path=task.image_path, abs_out_file_name=fft_path)
        except Exception as e:
            print(f"Error computing FFT: {str(e)}")

    def compute_ctf(self, task):
        try:
            if (task.pixel_size * 10 ** 10) <= 5:
                dispatch_ctf_task(task.task_id, task.image_path, task)
        except Exception as e:
            print(f"Error computing CTF: {str(e)}")