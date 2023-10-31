import os
import uuid
from typing import Optional

import yaml
from pydantic import BaseModel, ValidationError


class ConsulSettings(BaseModel):
    CONSUL_HOST: Optional[str] = None
    CONSUL_PORT: Optional[int] = None
    CONSUL_USERNAME: Optional[str] = None
    CONSUL_PASSWORD: Optional[str] = None
    CONSUL_SERVICE_NAME: Optional[str] = None
    CONSUL_SERVICE_ID: Optional[str] = None


class DirectorySettings(BaseModel):
    IMAGE_ROOT_URL: Optional[str] = None
    ORIGINAL_IMAGES_SUB_URL: Optional[str] = None
    IMAGE_SUB_URL: Optional[str] = None
    THUMBNAILS_SUB_URL: Optional[str] = None
    FRAMES_SUB_URL: Optional[str] = None
    FFT_SUB_URL: Optional[str] = None
    JOBS_PROCESSING_SUB_URL: Optional[str] = None
    THUMBNAILS_SUFFIX: Optional[str] = None
    FRAMES_SUFFIX: Optional[str] = None
    FFT_SUFFIX: Optional[str] = None
    IMAGE_ROOT_DIR: Optional[str] = None
    NFS_ROOT_DIR: Optional[str] = None
    IMAGES_DIR: Optional[str] = None
    FFT_DIR: Optional[str] = None
    THUMBNAILS_DIR: Optional[str] = None
    JOBS_DIR: Optional[str] = None
    ATLAS_SUB_URL: Optional[str] = None
    ATLAS_SUFFIX: Optional[str] = None


class DatabaseSettings(BaseModel):
    DB_Driver: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_Port: Optional[int] = None
    DB_NAME: Optional[str] = None

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
    SLACK_TOKEN: Optional[str] = None
    BASE_DIRECTORY: Optional[str] = os.path.abspath(os.path.dirname(__file__))
    ENV_TYPE: Optional[str] = None

    @classmethod
    def load_settings(cls, file_path):
        """
        Load settings from a JSON file and update the AppSettings instance.
        """
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                data_dict = yaml.safe_load(file)
            try:
                obj = cls.parse_obj(data_dict)
                return obj
            except ValidationError:
                # Handle validation error if necessary
                return None
        else:
            # Handle case when file doesn't exist
            return None
    @classmethod
    def load_settings_json(cls, file_path):
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
        with open(file_path, "w") as file:
            yaml.dump(self.dict(), file)

    def save_settings_json(self, file_path: str):
        """
        Save the AppSettings instance to a JSON file.
        """
        with open(file_path, 'w') as file:
            file.write(self.model_dump_json())
