import os
import uuid

from pydantic import BaseModel, ValidationError


class ConsulSettings(BaseModel):
    CONSUL_HOST: str
    CONSUL_PORT: int
    CONSUL_USERNAME: str
    CONSUL_PASSWORD: str
    CONSUL_SERVICE_NAME: str
    CONSUL_SERVICE_ID: str


class DirectorySettings(BaseModel):
    IMAGE_ROOT_URL: str
    ORIGINAL_IMAGES_SUB_URL: str
    IMAGE_SUB_URL: str
    THUMBNAILS_SUB_URL: str
    FRAMES_SUB_URL: str
    FFT_SUB_URL: str
    JOBS_PROCESSING_SUB_URL: str
    THUMBNAILS_SUFFIX: str
    FRAMES_SUFFIX: str
    FFT_SUFFIX: str
    IMAGE_ROOT_DIR: str
    IMAGES_DIR: str = f"{IMAGE_ROOT_DIR}/{IMAGE_SUB_URL}"
    FFT_DIR: str = f"{IMAGE_ROOT_DIR}/{FFT_SUB_URL}"
    THUMBNAILS_DIR: str = f"{IMAGE_ROOT_DIR}/{THUMBNAILS_SUB_URL}"
    JOBS_DIR: str = f"{IMAGE_ROOT_DIR}/{JOBS_PROCESSING_SUB_URL}"


class DatabaseSettings(BaseModel):
    DB_Driver: str
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_Port: str
    DB_NAME: str

    @classmethod
    def get_db_connection(cls) -> str:
        """
        Get the database connection string.
        """
        return f'{cls.DB_Driver}://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_Port}/{cls.DB_NAME}'


class AppSettings(BaseModel):
    consul_settings: ConsulSettings = ConsulSettings()
    directory_settings: DirectorySettings = DirectorySettings()
    database_settings: DatabaseSettings = DatabaseSettings()
    SLACK_TOKEN: str
    BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
    ENV_TYPE: str


    @classmethod
    def load_settings(cls, file_path):
        """
        Load settings from a JSON file and update the AppSettings instance.
        """
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                settings_json = file.read()
            try:
                json = cls.model_validate_json(settings_json)
                return json
            except ValidationError:
                # Handle validation error if necessary
                return None
        else:
            # Handle case when file doesn't exist
            return None

    def save_settings(self, file_path: str):
        """
        Save the AppSettings instance to a JSON file.
        """
        with open(file_path, 'w') as file:
            file.write(self.model_dump_json())
