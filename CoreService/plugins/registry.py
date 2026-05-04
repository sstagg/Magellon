"""Plugin registry — auto-discovers PluginBase subclasses on first use.

Plugins live under ``plugins/<category>/<name>/service.py``. Each
``service.py`` is imported once; any ``PluginBase`` subclass it defines is
instantiated, identified by ``{category}/{get_info().name}``, and cached.

**PI-6 (2026-05-04): VESTIGIAL.** The walk now finds nothing — the
``plugins/`` filesystem holds no service.py files. The last in-process
plugin (``pp/template-picker``) moved to plain functions in
``services/particle_picking/`` in PI-5. This module stays as
backstop scaffolding for any straggler imports
(``services/plugin_manager.py``, ``plugins/controller.py``); it's
harmless because the walk is now a no-op. Removable in a follow-up
PR that prunes those callers.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Iterator, List, Optional

from magellon_sdk.models import PluginManifest
from plugins.base import PluginBase

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginEntry:
    """A registered plugin instance with its resolved id and metadata.

    ``manifest`` is captured at registration time so dispatch/discovery
    code doesn't have to re-call ``instance.manifest()`` on every
    request — and so a plugin manager can reason about *all* plugins
    uniformly without instantiating them.
    """
    plugin_id: str           # e.g. "pp/template-picker"
    category: str            # e.g. "pp"
    name: str                # e.g. "template-picker"
    instance: PluginBase
    manifest: PluginManifest


class PluginRegistry:
    """Lazy, thread-safe registry of discovered plugins."""

    def __init__(self, package: str = "plugins") -> None:
        self._package = package
        self._entries: Dict[str, PluginEntry] = {}
        self._loaded = False
        self._lock = Lock()

    def _discover(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            pkg = importlib.import_module(self._package)
            for module_info in pkgutil.walk_packages(pkg.__path__, prefix=f"{self._package}."):
                # Only import modules named service.py — the plugin contract.
                if not module_info.name.endswith(".service"):
                    continue
                try:
                    module = importlib.import_module(module_info.name)
                except Exception as exc:
                    logger.warning("Skipping %s: import failed (%s)", module_info.name, exc)
                    continue

                for attr in vars(module).values():
                    if not isinstance(attr, type):
                        continue
                    if attr is PluginBase or not issubclass(attr, PluginBase):
                        continue
                    # Per the user's isolation rule: one bad plugin must
                    # not poison discovery for the others. Each plugin
                    # gets its own try/except so an instantiation crash
                    # or manifest() failure leaves the rest registered.
                    try:
                        instance = attr()
                        info = instance.get_info()
                        manifest = instance.manifest()
                    except Exception as exc:
                        logger.warning(
                            "Skipping plugin class %s: instantiation/manifest failed (%s)",
                            attr, exc,
                        )
                        continue

                    # category = first path segment after "plugins."
                    # e.g. plugins.pp.template_picker.service -> "pp"
                    parts = module_info.name.split(".")
                    category = parts[1] if len(parts) >= 3 else ""
                    plugin_id = f"{category}/{info.name}" if category else info.name

                    if plugin_id in self._entries:
                        logger.debug("Plugin %s already registered; skipping duplicate", plugin_id)
                        continue

                    self._entries[plugin_id] = PluginEntry(
                        plugin_id=plugin_id,
                        category=category,
                        name=info.name,
                        instance=instance,
                        manifest=manifest,
                    )
                    logger.info(
                        "Registered plugin: %s (transports=%s, isolation=%s)",
                        plugin_id,
                        [t.value for t in manifest.supported_transports],
                        manifest.isolation.value,
                    )
            self._loaded = True

    # -- public API ---------------------------------------------------------

    def list(self) -> List[PluginEntry]:
        self._discover()
        return list(self._entries.values())

    def get(self, plugin_id: str) -> Optional[PluginEntry]:
        self._discover()
        return self._entries.get(plugin_id)

    def __iter__(self) -> Iterator[PluginEntry]:
        return iter(self.list())

    def refresh(self) -> None:
        """Drop cache and re-discover on next access (useful for dev reloads)."""
        with self._lock:
            self._entries.clear()
            self._loaded = False


# Module-level singleton.
registry = PluginRegistry()
