import os
from typing import Optional

import pydantic_core
import yaml
from pydantic import BaseModel

ValidationError = pydantic_core.ValidationError


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


class ConsulSettings(BaseModel):
    CONSUL_HOST: Optional[str] = None
    CONSUL_PORT: Optional[int] = None
    CONSUL_USERNAME: Optional[str] = None
    CONSUL_PASSWORD: Optional[str] = None
    CONSUL_SERVICE_NAME: Optional[str] = None
    CONSUL_SERVICE_ID: Optional[str] = None

class RabbitMQSettings(BaseModel):
    HOST_NAME: Optional[str] = None
    QUEUE_NAME: Optional[str] = None
    OUT_QUEUE_NAME: Optional[str] = None
    PORT: Optional[int] = 5672
    USER_NAME: Optional[str] = None
    PASSWORD: Optional[str] = None
    VIRTUAL_HOST: Optional[str] = None
    SSL_ENABLED: Optional[bool] = False
    CONNECTION_TIMEOUT: Optional[int] = 30
    PREFETCH_COUNT: Optional[int] = 10


class AppSettings(BaseModel):
    consul_settings: ConsulSettings = ConsulSettings()
    database_settings: DatabaseSettings = DatabaseSettings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    LOCAL_IP_ADDRESS: Optional[str] = None
    PORT_NUMBER: Optional[int] = None
    ROOT_DIR: Optional[str] = None
    REPLACE_TYPE: Optional[str] = None
    REPLACE_PATTERN: Optional[str] = None
    REPLACE_WITH: Optional[str] = None
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


class AppSettingsSingleton:
    _instance: Optional[AppSettings] = None

    @classmethod
    def get_instance(cls) -> AppSettings:
        if cls._instance is None:
            cls._instance = cls._create_instance()
        return cls._instance

    @classmethod
    def _create_instance(cls) -> AppSettings:
        if os.environ.get('APP_ENV', "development") == 'production':
            return AppSettings.load_settings("./configs/settings_prod.yml")
        else:
            return AppSettings.load_settings("./configs/settings_dev.yml")

# app_settings: AppSettings = None
#
# if os.environ.get('APP_ENV', "development") == 'production':
#     # from .config_prod import *
#     app_settings = AppSettings.load_settings("./configs/settings_prod.yaml")
# else:
#     # from .config_dev import *
#     app_settings = AppSettings.load_settings("./configs/settings_dev.yaml")