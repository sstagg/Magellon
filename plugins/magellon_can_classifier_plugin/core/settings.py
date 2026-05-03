"""CAN classifier plugin settings — minimal subclass over the SDK base."""
from magellon_sdk.config import (  # noqa: F401
    BaseAppSettings,
    BaseAppSettingsSingleton,
    DatabaseSettings,
    RabbitMQSettings,
)
from magellon_sdk.config.settings import ValidationError  # noqa: F401


class AppSettings(BaseAppSettings):
    """No plugin-specific fields beyond SDK defaults."""


class AppSettingsSingleton(BaseAppSettingsSingleton):
    _settings_class = AppSettings


__all__ = [
    "AppSettings",
    "AppSettingsSingleton",
    "DatabaseSettings",
    "RabbitMQSettings",
    "ValidationError",
]
