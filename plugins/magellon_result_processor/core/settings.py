"""Result-processor settings — extends the shared SDK base with fan-in queue config.

The result processor consumes a *list* of out-queues (limitation #7 /
fan-in path in CURRENT_ARCHITECTURE.md §4.1), so it needs
``OUT_QUEUES`` on its RabbitMQ settings and a ``MAGELLON_HOME_DIR`` for
output file placement. Everything else comes from the shared SDK base.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from magellon_sdk.config import (  # noqa: F401
    BaseAppSettings,
    BaseAppSettingsSingleton,
    ConsulSettings,
    DatabaseSettings,
)
from magellon_sdk.config import RabbitMQSettings as _BaseRabbitMQSettings
from magellon_sdk.config.settings import ValidationError  # noqa: F401


class QueueType(str, Enum):
    CTF = "ctf"
    MOTIONCOR = "motioncor"
    PARTICLE_PICKING = "particle_picking"
    DEBUG = "debug"


class OutQueueConfig(BaseModel):
    name: str
    queue_type: QueueType
    dir_name: Optional[str] = None
    category: Optional[int] = None


class RabbitMQSettings(_BaseRabbitMQSettings):
    OUT_QUEUES: List[OutQueueConfig] = []


class AppSettings(BaseAppSettings):
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    MAGELLON_HOME_DIR: Optional[str] = None


class AppSettingsSingleton(BaseAppSettingsSingleton):
    _settings_class = AppSettings


__all__ = [
    "AppSettings",
    "AppSettingsSingleton",
    "ConsulSettings",
    "DatabaseSettings",
    "OutQueueConfig",
    "QueueType",
    "RabbitMQSettings",
    "ValidationError",
]
