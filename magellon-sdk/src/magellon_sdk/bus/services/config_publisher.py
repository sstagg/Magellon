"""Process-wide config-publisher singleton (MB5.4c).

Relocated from ``CoreService/services/plugin_config_publisher.py``.
The underlying publisher (:class:`magellon_sdk.config_broker.ConfigPublisher`)
already rides the MessageBus as of MB5.2, so this module is an
organizational consolidation — singleton lifecycle + two operator-
friendly push helpers — that any bus-based deployment can use.

CoreService keeps a thin re-export so admin controllers and tests
import unchanged (``from services.plugin_config_publisher import ...``).

Design:

- One publisher per process, lazily constructed on first push.
  Opening a fresh :class:`ConfigPublisher` per push would rebuild
  the bus-side route objects every time; trivially cheap but the
  singleton also gives tests a predictable reset point.
- Push helpers emit a structured log line each call so operators
  get an audit trail without the admin controller having to log
  twice.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from magellon_sdk.bus.interfaces import MessageBus
from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.config_broker import ConfigPublisher

logger = logging.getLogger(__name__)


_PUBLISHER: Optional[ConfigPublisher] = None
_LOCK = threading.Lock()


def get_config_publisher(
    rabbitmq_settings: Any = None,
    *,
    bus: Optional[MessageBus] = None,
) -> ConfigPublisher:
    """Return the process-wide config publisher.

    Lazily constructed so importing this module doesn't require a
    broker — matters for tests and for ``alembic`` runs that import
    the package transitively.

    ``rabbitmq_settings`` is retained for backcompat with pre-MB5.4c
    callers (the CoreService admin controllers still pass it). The
    :class:`ConfigPublisher` no longer consults it post-MB5.2 — the
    bus was configured at startup from the same settings.
    """
    global _PUBLISHER
    with _LOCK:
        if _PUBLISHER is None:
            _PUBLISHER = ConfigPublisher(rabbitmq_settings, bus=bus)
        return _PUBLISHER


def push_to_category(
    rabbitmq_settings: Any,
    contract: CategoryContract,
    settings: Dict[str, Any],
    *,
    version: Optional[int] = None,
) -> None:
    pub = get_config_publisher(rabbitmq_settings)
    pub.publish_to_category(contract, settings, version=version)
    logger.info(
        "plugin config push: category=%s keys=%s version=%s",
        contract.category.name.lower(),
        sorted(settings.keys()),
        version,
    )


def push_broadcast(
    rabbitmq_settings: Any,
    settings: Dict[str, Any],
    *,
    version: Optional[int] = None,
) -> None:
    pub = get_config_publisher(rabbitmq_settings)
    pub.publish_broadcast(settings, version=version)
    logger.info(
        "plugin config push: broadcast keys=%s version=%s",
        sorted(settings.keys()),
        version,
    )


def reset_publisher() -> None:
    """Test helper — drop the cached publisher between tests."""
    global _PUBLISHER
    with _LOCK:
        if _PUBLISHER is not None:
            try:
                _PUBLISHER.close()
            except Exception:
                pass
        _PUBLISHER = None


__all__ = [
    "get_config_publisher",
    "push_broadcast",
    "push_to_category",
    "reset_publisher",
]
