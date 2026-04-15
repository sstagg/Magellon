"""MotionCor-plugin settings — thin subclass over the shared SDK base."""
from typing import Optional

from magellon_sdk.config import (  # noqa: F401
    BaseAppSettings,
    BaseAppSettingsSingleton,
    ConsulSettings,
    DatabaseSettings,
    RabbitMQSettings,
)
from magellon_sdk.config.settings import ValidationError  # noqa: F401


class AppSettings(BaseAppSettings):
    JOBS_DIR: Optional[str] = None
    HOST_JOBS_DIR: Optional[str] = None


class AppSettingsSingleton(BaseAppSettingsSingleton):
    _settings_class = AppSettings


__all__ = [
    "AppSettings",
    "AppSettingsSingleton",
    "ConsulSettings",
    "DatabaseSettings",
    "RabbitMQSettings",
    "ValidationError",
]
