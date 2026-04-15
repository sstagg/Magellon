"""CTF-plugin settings — thin subclass over the shared SDK base.

Shared fields and the YAML/JSON loader methods live in
``magellon_sdk.config.settings``; this file only declares the fields
specific to the CTF plugin.
"""
from typing import Optional

from magellon_sdk.config import (  # noqa: F401  (re-exports for back-compat)
    BaseAppSettings,
    BaseAppSettingsSingleton,
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
    "DatabaseSettings",
    "RabbitMQSettings",
    "ValidationError",
]
