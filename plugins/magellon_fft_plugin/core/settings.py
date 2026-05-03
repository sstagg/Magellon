"""FFT-plugin settings — minimal subclass over the shared SDK base.

FFT has no plugin-specific settings beyond the SDK defaults (broker,
GPFS, database). The previous version added ``JOBS_DIR`` /
``HOST_JOBS_DIR`` fields the FFT compute never read; they were carried
from the CTF/MotionCor plugins where output staging needs them.

The subclasses still exist because :class:`BaseAppSettingsSingleton`
needs ``_settings_class`` set to load YAML — re-exporting the base
directly would break ``AppSettingsSingleton.get_instance()``.
"""
from magellon_sdk.config import (  # noqa: F401
    BaseAppSettings,
    BaseAppSettingsSingleton,
    DatabaseSettings,
    RabbitMQSettings,
)
from magellon_sdk.config.settings import ValidationError  # noqa: F401


class AppSettings(BaseAppSettings):
    """No plugin-specific fields — FFT runs on the SDK defaults."""


class AppSettingsSingleton(BaseAppSettingsSingleton):
    _settings_class = AppSettings


__all__ = [
    "AppSettings",
    "AppSettingsSingleton",
    "DatabaseSettings",
    "RabbitMQSettings",
    "ValidationError",
]
