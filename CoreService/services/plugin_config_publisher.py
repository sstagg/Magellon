"""CoreService facade for ``magellon_sdk.bus.services.config_publisher``.

MB5.4c moved the singleton + reset helper into the SDK. The push
wrappers stay here because they emit a CoreService-specific operator
log line and because keeping ``push_*`` local preserves the
``patch.object(svc, "get_config_publisher")`` test pattern — the
helpers resolve ``get_config_publisher`` via this module's namespace,
so test fixtures that patch on the module can intercept.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from magellon_sdk.bus.services.config_publisher import (
    get_config_publisher,
    reset_publisher,
)
from magellon_sdk.categories.contract import CategoryContract

logger = logging.getLogger(__name__)


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


__all__ = [
    "get_config_publisher",
    "push_broadcast",
    "push_to_category",
    "reset_publisher",
]
