"""Topaz-plugin settings — thin subclass over the shared SDK base.

Two RMQ subscriptions, one container — same shape as the ptolemy plugin.
"""
from typing import Optional

from magellon_sdk.config import (  # noqa: F401
    BaseAppSettings,
    BaseAppSettingsSingleton,
    DatabaseSettings,
    RabbitMQSettings,
)
from magellon_sdk.config.settings import ValidationError  # noqa: F401


class AppSettings(BaseAppSettings):
    JOBS_DIR: Optional[str] = None
    HOST_JOBS_DIR: Optional[str] = None

    PICK_QUEUE_NAME: str = "topaz_pick_tasks_queue"
    PICK_OUT_QUEUE_NAME: str = "topaz_pick_out_tasks_queue"
    DENOISE_QUEUE_NAME: str = "micrograph_denoise_tasks_queue"
    DENOISE_OUT_QUEUE_NAME: str = "micrograph_denoise_out_tasks_queue"


class AppSettingsSingleton(BaseAppSettingsSingleton):
    _settings_class = AppSettings


__all__ = [
    "AppSettings",
    "AppSettingsSingleton",
    "DatabaseSettings",
    "RabbitMQSettings",
    "ValidationError",
]
