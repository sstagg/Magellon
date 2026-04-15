"""Base settings models and singleton machinery shared by every plugin.

Plugins subclass :class:`BaseAppSettings` to add plugin-specific fields
(``JOBS_DIR``, ``OUT_QUEUES``, …), and subclass :class:`BaseAppSettingsSingleton`
setting ``_settings_class`` to that subclass. The YAML/JSON load and save
helpers live on the base so plugins inherit them for free.
"""
from __future__ import annotations

import os
from typing import Any, ClassVar, Dict, Optional, Type

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
        return f"{cls.DB_Driver}://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_Port}/{cls.DB_NAME}"


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


class BaseAppSettings(BaseModel):
    """Fields common to every plugin's ``AppSettings``.

    Subclasses add plugin-specific fields (e.g. result_processor's
    ``OUT_QUEUES``, ctf/motioncor's ``JOBS_DIR``). The YAML/JSON helpers
    below return ``cls(...)`` so subclass instances come back from
    ``AppSettings.load_yaml_file_settings(...)``.
    """

    consul_settings: ConsulSettings = ConsulSettings()
    database_settings: DatabaseSettings = DatabaseSettings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    LOCAL_IP_ADDRESS: Optional[str] = None
    PORT_NUMBER: Optional[int] = None
    REPLACE_TYPE: Optional[str] = None
    REPLACE_PATTERN: Optional[str] = None
    REPLACE_WITH: Optional[str] = None
    BASE_DIRECTORY: Optional[str] = os.path.abspath(os.path.dirname(__file__))
    ENV_TYPE: Optional[str] = None

    @classmethod
    def load_yaml_file_settings(cls, file_path: str):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                data_dict = yaml.safe_load(file)
            try:
                return cls.parse_obj(data_dict)
            except ValidationError:
                return None
        return None

    @classmethod
    def load_yaml_settings(cls, yaml_string: str):
        try:
            data_dict = yaml.safe_load(yaml_string)
            return cls.parse_obj(data_dict)
        except (ValidationError, yaml.YAMLError):
            return None

    @classmethod
    def load_json_file_settings(cls, file_path: str):
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                settings_json = file.read()
            try:
                return cls.model_validate_json(settings_json)
            except ValidationError:
                return None
        return None

    def save_yaml_settings(self, file_path: str) -> None:
        with open(file_path, "w") as file:
            yaml.dump(self.dict(), file)

    def save_settings_to_json_file(self, file_path: str) -> None:
        with open(file_path, "w") as file:
            file.write(self.model_dump_json())


class BaseAppSettingsSingleton:
    """Process-wide singleton for a plugin's ``AppSettings``.

    Subclass and set ``_settings_class`` to your concrete ``AppSettings``
    type. Override ``_dev_yaml`` / ``_prod_yaml`` only if you need paths
    other than ``./configs/settings_{dev,prod}.yml``.

    Instances are stored in a class-keyed dict so multiple plugin
    singletons can coexist in one interpreter (useful in tests).
    """

    _instances: ClassVar[Dict[type, Any]] = {}
    _settings_class: ClassVar[Optional[Type[BaseAppSettings]]] = None
    _dev_yaml: ClassVar[str] = "./configs/settings_dev.yml"
    _prod_yaml: ClassVar[str] = "./configs/settings_prod.yml"

    @classmethod
    def get_instance(cls) -> Optional[BaseAppSettings]:
        if cls not in cls._instances:
            cls._instances[cls] = cls._create_instance()
        return cls._instances[cls]

    @classmethod
    def _create_instance(cls) -> Optional[BaseAppSettings]:
        if cls._settings_class is None:
            raise TypeError(
                f"{cls.__name__} must set _settings_class to a BaseAppSettings subclass"
            )
        path = cls._prod_yaml if os.environ.get("APP_ENV", "development") == "production" else cls._dev_yaml
        return cls._settings_class.load_yaml_file_settings(path)

    @classmethod
    def update_settings_from_yaml(cls, yaml_string: str) -> Optional[BaseAppSettings]:
        if cls._settings_class is None:
            return None
        try:
            new_settings = cls._settings_class.load_yaml_settings(yaml_string)
            if new_settings:
                cls._instances[cls] = new_settings
            return cls._instances.get(cls)
        except ValidationError:
            return None
