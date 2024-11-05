import os
from abc import ABC, abstractmethod

from fastapi import Depends
from sqlalchemy.orm import Session

from core.helper import create_directory, dispatch_ctf_task
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, ATLAS_SUB_URL, CTF_SUB_URL
from database import get_db
from models.pydantic_models import ImportJobBase
from models.sqlalchemy_models import Project, Msession
import logging
logger = logging.getLogger(__name__)


class TaskFailedException(Exception):
    pass



class BaseImporter(ABC):
    def __init__(self):
        self.params = None
        self.db_session = None
        self.job = None

    def setup(self, input_data):
        self.params = input_data

    def setup_data(self, input_data: ImportJobBase):
        self.params = input_data

    def process(self,  db_session: Session = Depends(get_db)):
        self.db_session = db_session
        try:
            self.create_job()
            self.import_data()
            self.process_imported_data()
            self.post_processing()  # Template Method
            return {'status': 'success', 'message': 'Import completed successfully.', "job_id": self.params.job_id}
        except Exception as e:
            return {'status': 'failure', 'message': f'Import failed with error: {str(e)} Job ID: {self.params.job_id}'}

    def create_job(self, db_session: Session):
        # Implementation remains the same as in the previous artifact
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
            # get the session object from the database
            session_name = self.params.session_name

            # get list of images to be imported and if there is any

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


    # def create_or_get_session(self):
    # Implementation remains the same as in the previous artifact

    # def create_or_get_project(self):
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