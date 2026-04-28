"""Ptolemy-plugin settings — thin subclass over the shared SDK base.

Extra fields beyond the shared base:

* ``SQUARE_QUEUE_NAME`` / ``SQUARE_OUT_QUEUE_NAME`` — dispatch + result
  queues for the low-mag category.
* ``HOLE_QUEUE_NAME`` / ``HOLE_OUT_QUEUE_NAME`` — same, for med-mag.

One process, two RMQ subscriptions. The legacy single-queue
``QUEUE_NAME`` / ``OUT_QUEUE_NAME`` from ``RabbitMQSettings`` is left
unused by this plugin — the two-category runners override them per-queue.
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

    SQUARE_QUEUE_NAME: str = "square_detection_tasks_queue"
    SQUARE_OUT_QUEUE_NAME: str = "square_detection_out_tasks_queue"
    HOLE_QUEUE_NAME: str = "hole_detection_tasks_queue"
    HOLE_OUT_QUEUE_NAME: str = "hole_detection_out_tasks_queue"


class AppSettingsSingleton(BaseAppSettingsSingleton):
    _settings_class = AppSettings


__all__ = [
    "AppSettings",
    "AppSettingsSingleton",
    "DatabaseSettings",
    "RabbitMQSettings",
    "ValidationError",
]
