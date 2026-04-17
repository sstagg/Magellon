"""In-process operator state for plugin routing decisions (H1).

Two pieces of state, both process-local:

- **enabled[plugin_id] -> bool.** Default: ``True``. When ``False`` the
  dispatcher refuses to route to this plugin. Used to quiesce an impl
  without stopping the plugin process (plugin keeps announcing,
  heartbeating, ready to re-enable in one click).

- **default_impl[category] -> plugin_id.** When multiple impls announce
  the same category, CoreService picks this one for dispatch.
  Self-heals: if no default is set and the current default goes offline
  or is disabled, :meth:`resolve_default` auto-picks the first live
  enabled impl for that category — the UI still shows the operator's
  pinned choice.

Not persisted. A CoreService restart re-seeds from the first live
announce: all impls default to enabled, and the first impl to announce
a category wins the default slot. This matches the liveness registry's
own "non-persistent, rebuilds on reconnect" model.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional


class PluginStateStore:
    """Thread-safe per-plugin enabled flag + per-category default impl."""

    def __init__(self) -> None:
        self._enabled: Dict[str, bool] = {}
        self._default_impl: Dict[str, str] = {}
        self._lock = threading.Lock()

    # -- enabled ---------------------------------------------------------

    def is_enabled(self, plugin_id: str) -> bool:
        with self._lock:
            return self._enabled.get(plugin_id, True)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self._lock:
            self._enabled[plugin_id] = enabled

    # -- default impl per category --------------------------------------

    def get_default(self, category: str) -> Optional[str]:
        with self._lock:
            return self._default_impl.get(category.lower())

    def set_default(self, category: str, plugin_id: str) -> None:
        with self._lock:
            self._default_impl[category.lower()] = plugin_id

    # -- snapshot for admin UI ------------------------------------------

    def snapshot(self) -> Dict[str, Dict[str, object]]:
        with self._lock:
            return {
                "enabled": dict(self._enabled),
                "default_impl": dict(self._default_impl),
            }


_STORE: Optional[PluginStateStore] = None


def get_state_store() -> PluginStateStore:
    global _STORE
    if _STORE is None:
        _STORE = PluginStateStore()
    return _STORE


__all__ = ["PluginStateStore", "get_state_store"]
