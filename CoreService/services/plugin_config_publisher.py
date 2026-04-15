"""CoreService-side wrapper for broker-based plugin config (P7).

Thin facade on :class:`magellon_sdk.config_broker.ConfigPublisher` that
takes the global ``rabbitmq_settings`` block off ``app_settings`` so
admin endpoints (or background tasks that need to push config — e.g.,
a config file change watcher) don't have to know the wiring.

Kept separate from the SDK class so we can:

  - Add CoreService-only concerns (authz logging, audit trail) without
    polluting the plugin SDK.
  - Inject a per-process singleton instead of opening a new RMQ
    connection per push.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from magellon_sdk.categories.contract import CategoryContract
from magellon_sdk.config_broker import ConfigPublisher

logger = logging.getLogger(__name__)


_PUBLISHER: Optional[ConfigPublisher] = None
_LOCK = threading.Lock()


def get_config_publisher(rabbitmq_settings: Any) -> ConfigPublisher:
    """Return the process-wide config publisher.

    Lazily constructed so importing this module doesn't require a
    broker — matters for tests and for `alembic` runs that import the
    package transitively.
    """
    global _PUBLISHER
    with _LOCK:
        if _PUBLISHER is None:
            _PUBLISHER = ConfigPublisher(rabbitmq_settings)
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
