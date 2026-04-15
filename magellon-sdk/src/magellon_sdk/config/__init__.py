"""Shared configuration primitives for Magellon plugins.

Plugins define an ``AppSettings`` subclass of :class:`BaseAppSettings`
with any plugin-specific fields, plus a 2-line ``AppSettingsSingleton``
subclass that binds the concrete settings type.
"""
from __future__ import annotations

from magellon_sdk.config.settings import (
    BaseAppSettings,
    BaseAppSettingsSingleton,
    ConsulSettings,
    DatabaseSettings,
    RabbitMQSettings,
)

__all__ = [
    "BaseAppSettings",
    "BaseAppSettingsSingleton",
    "ConsulSettings",
    "DatabaseSettings",
    "RabbitMQSettings",
]
