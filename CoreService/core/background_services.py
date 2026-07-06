"""Lightweight registry for CoreService background service state."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class BackgroundServiceStatus:
    name: str
    status: str
    enabled: bool
    checked_at: float
    service_type: Optional[str] = None
    error: Optional[str] = None


class BackgroundServiceRegistry:
    def __init__(self) -> None:
        self._services: Dict[str, BackgroundServiceStatus] = {}

    def started(self, name: str, service: Any = None) -> None:
        self._services[name] = BackgroundServiceStatus(
            name=name,
            status="ok",
            enabled=True,
            checked_at=time.time(),
            service_type=type(service).__name__ if service is not None else None,
        )

    def failed(self, name: str, exc: BaseException) -> None:
        self._services[name] = BackgroundServiceStatus(
            name=name,
            status="error",
            enabled=True,
            checked_at=time.time(),
            error=str(exc),
        )

    def disabled(self, name: str) -> None:
        self._services[name] = BackgroundServiceStatus(
            name=name,
            status="disabled",
            enabled=False,
            checked_at=time.time(),
        )

    def stopped(self, name: str, service: Any = None) -> None:
        self._services[name] = BackgroundServiceStatus(
            name=name,
            status="stopped",
            enabled=True,
            checked_at=time.time(),
            service_type=type(service).__name__ if service is not None else None,
        )

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        status = self._services.get(name)
        return asdict(status) if status is not None else None

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {name: asdict(status) for name, status in self._services.items()}


def ensure_background_registry(app: Any) -> BackgroundServiceRegistry:
    registry = getattr(app.state, "background_services", None)
    if registry is None:
        registry = BackgroundServiceRegistry()
        app.state.background_services = registry
    return registry
