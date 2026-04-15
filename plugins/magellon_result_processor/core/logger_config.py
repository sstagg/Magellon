"""Compatibility shim — binds this plugin's ``get_plugin_info`` to the shared SDK logging config."""
from services.service import get_plugin_info

from magellon_sdk.logging_config import setup_logging as _sdk_setup_logging


def setup_logging() -> None:
    _sdk_setup_logging(get_plugin_info)


__all__ = ["setup_logging"]
