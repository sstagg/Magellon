"""In-memory registry of plugin containers installed via POST /plugins/install (H2).

Keyed by ``install_id`` — the CoreService-generated short UUID returned
in the install response. Thread-safe. Non-persistent; a CoreService
restart wipes the mapping (see plan docs/UNIFIED_PLATFORM_PLAN.md §4
"No central registry yet").

Intentionally lean: no cross-referencing with the liveness registry
here. The /plugins/installed endpoint joins against
:mod:`core.plugin_liveness_registry` at read time so the "is it
announcing?" signal stays live (this registry only knows what
CoreService spawned; the liveness registry knows what's actually
talking on the bus).
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from core.plugin_docker_runner import InstalledPlugin


class InstalledPluginsRegistry:
    """Thread-safe dict of install_id → InstalledPlugin."""

    def __init__(self) -> None:
        self._entries: Dict[str, InstalledPlugin] = {}
        self._lock = threading.Lock()

    def add(self, entry: InstalledPlugin) -> None:
        with self._lock:
            self._entries[entry.install_id] = entry

    def get(self, install_id: str) -> Optional[InstalledPlugin]:
        with self._lock:
            return self._entries.get(install_id)

    def remove(self, install_id: str) -> Optional[InstalledPlugin]:
        with self._lock:
            return self._entries.pop(install_id, None)

    def list(self) -> List[InstalledPlugin]:
        with self._lock:
            return list(self._entries.values())


_REGISTRY: Optional[InstalledPluginsRegistry] = None


def get_installed_registry() -> InstalledPluginsRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = InstalledPluginsRegistry()
    return _REGISTRY


__all__ = ["InstalledPluginsRegistry", "get_installed_registry"]
