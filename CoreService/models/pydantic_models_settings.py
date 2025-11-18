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


class RabbitMQSettings(BaseModel):
    HOST_NAME: Optional[str] = None
    CTF_QUEUE_NAME: Optional[str] = None
    CTF_OUT_QUEUE_NAME: Optional[str] = None
    MOTIONCOR_QUEUE_NAME: Optional[str] = None
    MOTIONCOR_OUT_QUEUE_NAME: Optional[str] = None
    PORT: Optional[int] = 5672
    USER_NAME: Optional[str] = None
    PASSWORD: Optional[str] = None
    VIRTUAL_HOST: Optional[str] = None
    SSL_ENABLED: Optional[bool] = False
    CONNECTION_TIMEOUT: Optional[int] = 30
    PREFETCH_COUNT: Optional[int] = 10


class DirectorySettings(BaseModel):
    IMAGE_ROOT_URL: Optional[str] = None
    ORIGINAL_IMAGES_SUB_URL: Optional[str] = None
    IMAGE_SUB_URL: Optional[str] = None
    THUMBNAILS_SUB_URL: Optional[str] = None
    FRAMES_SUB_URL: Optional[str] = None
    JOBS_PROCESSING_SUB_URL: Optional[str] = None
    THUMBNAILS_SUFFIX: Optional[str] = None
    FRAMES_SUFFIX: Optional[str] = None
    FFT_SUB_URL: Optional[str] = None
    FFT_SUFFIX: Optional[str] = None
    FFT_DIR: Optional[str] = None
    MAGELLON_HOME_DIR: Optional[str] = None
    NFS_ROOT_DIR: Optional[str] = None
    IMAGES_DIR: Optional[str] = None
    THUMBNAILS_DIR: Optional[str] = None
    MAGELLON_JOBS_DIR: Optional[str] = None
    JOBS_DIR: Optional[str] = None
    ATLAS_SUB_URL: Optional[str] = None
    CTF_SUB_URL: Optional[str] = None
    FAO_SUB_URL: Optional[str] = None
    GAIN_SUB_URL: Optional[str] = None
    DEFECTS_SUB_URL: Optional[str] = None
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


class LeginonDatabaseSettings(BaseModel):
    """
    Settings for external Leginon database connection.
    Used for importing Leginon session data and creating atlases.
    """
    ENABLED: Optional[bool] = False
    HOST: Optional[str] = None
    PORT: Optional[int] = 3310
    USER: Optional[str] = None
    PASSWORD: Optional[str] = None
    DATABASE: Optional[str] = "dbemdata"


class ApiDocsSettings(BaseModel):
    """
    Settings for API documentation HTTP Basic Authentication.
    Protects /docs and /openapi.json endpoints.
    """
    ENABLED: Optional[bool] = True
    USERNAME: Optional[str] = "admin"
    PASSWORD: Optional[str] = "changeme"


class SecuritySetupSettings(BaseModel):
    """
    Settings for security system bootstrap/setup endpoint.
    Used during initial application installation to create admin user.
    """
    ENABLED: Optional[bool] = True
    SETUP_TOKEN: Optional[str] = None  # Optional token for extra security
    AUTO_DISABLE: Optional[bool] = True  # Automatically disable after first successful run


class AppSettings(BaseModel):
    consul_settings: ConsulSettings = ConsulSettings()
    directory_settings: DirectorySettings = DirectorySettings()
    database_settings: DatabaseSettings = DatabaseSettings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    leginon_db_settings: LeginonDatabaseSettings = LeginonDatabaseSettings()
    api_docs_settings: ApiDocsSettings = ApiDocsSettings()
    security_setup_settings: SecuritySetupSettings = SecuritySetupSettings()
    SLACK_TOKEN: Optional[str] = None
    BASE_DIRECTORY: Optional[str] = os.path.abspath(os.path.dirname(__file__))
    DOCKER_URL: Optional[str] = None
    DOCKER_REPOSITORY: Optional[str] = None
    DOCKER_USERNAME: Optional[str] = None
    DOCKER_PASSWORD: Optional[str] = None

    DEBUG_CTF: Optional[bool] = None
    DEBUG_CTF_PATH: Optional[str] = None
    DEBUG_CTF_REPLACE: Optional[str] = None

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
            except ValidationError as e:
                print(f"Validation error: {e}")
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
