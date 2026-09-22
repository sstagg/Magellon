"""Shared JSON logging config for Magellon plugins.

Plugins previously copy-pasted ``core/logger_config.py``. The only real
per-plugin difference was the import path of ``get_plugin_info``; here we
inject it as a callable so the SDK does not depend on any plugin's
package layout.
"""
from __future__ import annotations

import logging.config
import os
from pathlib import Path
from typing import Any, Callable

from pythonjsonlogger import jsonlogger


def setup_logging(plugin_info_provider: Callable[[], Any]) -> None:
    """Configure root logging with rich console + rotating JSON file handler.

    ``plugin_info_provider`` is called lazily at log-format time; it must
    return an object exposing ``instance_id``, ``name``, and ``version``.
    """

    class _PluginJsonFormatter(jsonlogger.JsonFormatter):
        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            log_record["level"] = record.levelname
            info = plugin_info_provider()
            log_record["instance"] = str(info.instance_id)
            log_record["plugin_name"] = str(info.name)
            log_record["plugin_version"] = str(info.version)

    log_dir = Path(os.environ.get("MAGELLON_LOG_DIR", "/tmp/magellon-logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "class": "rich.logging.RichHandler",
                "formatter": "detailed",
            },
            "console2": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_path),
                "maxBytes": 1024 * 1024 * 5,  # 5 MB
                "backupCount": 5,
                "formatter": "json",
            },
        },
        "formatters": {
            "json": {
                "()": _PluginJsonFormatter,
                "format": "(asctime)s  [%(levelname)s] %(filename)s:%(lineno)d  %(name)s: %(message)s",
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            },
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s %(filename)s:%(lineno)d - %(message)s",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"],
        },
        "loggers": {
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    logging.config.dictConfig(config)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
