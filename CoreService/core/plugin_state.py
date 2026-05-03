"""Operator state for plugin routing decisions.

Pre-PM1 was an in-memory dict (silent state loss on every CoreService
restart). Post-PM1 (alembic 0008, 2026-05-04) the same singleton API
is preserved as a back-compat shim — reads stay in memory (fast
lookup on the dispatch hot path); writes hit both memory AND the DB
through ``repositories.plugin_repository``. On first access the
in-memory cache is hydrated from the DB so a CoreService restart
restores every operator decision.

Two pieces of state, both per-plugin or per-category:

- **enabled[plugin_id] -> bool.** Default ``True``. When ``False``
  the dispatcher refuses to route to this plugin. Used to quiesce an
  impl without stopping the plugin process.

- **default_impl[category] -> plugin_id.** When multiple impls
  announce the same category, CoreService picks this one for
  dispatch. Multi-category plugins (topaz: TOPAZ_PARTICLE_PICKING +
  MICROGRAPH_DENOISING) get distinct decisions per category — the
  underlying ``plugin_category_default`` table is keyed on category,
  not on plugin (reviewer-flagged High #1 from
  ``PLUGIN_MANAGER_PLAN.md`` revision 1).

The runtime ``plugin_id`` string is the value of
``PluginInfo.name`` (matches what ``PluginLivenessRegistry`` carries
on each entry). On a write we look up the matching ``Plugin`` row by
``manifest_plugin_id`` first, falling back to ``Plugin.name`` for
plugins that announced before the install pipeline cataloged them.
If neither lookup hits, the write stays in memory only — the
silent-state-loss bug for un-cataloged plugins remains by design
until the install pipeline guarantees a ``plugin`` row for every
announced plugin (a follow-up).
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PluginStateStore:
    """Thread-safe per-plugin enabled flag + per-category default impl.

    Read path: in-memory dict (fast). Write path: in-memory + DB
    write-through. Hydrate-on-first-access from the DB so a restart
    restores operator decisions.
    """

    def __init__(self) -> None:
        self._enabled: Dict[str, bool] = {}
        self._default_impl: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._hydrated = False

    # ------------------------------------------------------------------
    # Hydration (runs once on first access)
    # ------------------------------------------------------------------

    def _hydrate(self) -> None:
        if self._hydrated:
            return
        with self._lock:
            if self._hydrated:
                return
            try:
                from database import session_local
                from models.sqlalchemy_models import (
                    Plugin,
                    PluginCategoryDefault,
                    PluginState,
                )

                with session_local() as db:
                    rows = (
                        db.query(Plugin, PluginState)
                        .outerjoin(
                            PluginState,
                            PluginState.plugin_oid == Plugin.oid,
                        )
                        .filter(Plugin.deleted_date.is_(None))
                        .filter(Plugin.GCRecord.is_(None))
                        .all()
                    )
                    for plugin, state in rows:
                        if state is not None:
                            self._enabled[plugin.name] = bool(state.enabled)
                            if plugin.manifest_plugin_id:
                                self._enabled[plugin.manifest_plugin_id] = (
                                    bool(state.enabled)
                                )

                    for default in db.query(PluginCategoryDefault).all():
                        plugin = (
                            db.query(Plugin)
                            .filter(Plugin.oid == default.plugin_oid)
                            .first()
                        )
                        if plugin is not None:
                            self._default_impl[default.category] = plugin.name
            except Exception:
                logger.exception(
                    "PluginStateStore: DB hydrate failed; starting empty",
                )
            self._hydrated = True

    # ------------------------------------------------------------------
    # enabled
    # ------------------------------------------------------------------

    def is_enabled(self, plugin_id: str) -> bool:
        self._hydrate()
        with self._lock:
            return self._enabled.get(plugin_id, True)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        self._hydrate()
        with self._lock:
            self._enabled[plugin_id] = enabled

        try:
            from database import session_local
            from repositories.plugin_repository import PluginStateRepository

            with session_local() as db:
                plugin = self._lookup_plugin_row(db, plugin_id)
                if plugin is not None:
                    PluginStateRepository(db).set_enabled(plugin.oid, enabled)
                    db.commit()
                else:
                    logger.warning(
                        "PluginStateStore: no plugin row for %s; "
                        "set_enabled persisted in memory only",
                        plugin_id,
                    )
        except Exception:
            logger.exception(
                "PluginStateStore: failed to persist enabled=%s for %s",
                enabled, plugin_id,
            )

    # ------------------------------------------------------------------
    # default impl per category
    # ------------------------------------------------------------------

    def get_default(self, category: str) -> Optional[str]:
        self._hydrate()
        with self._lock:
            return self._default_impl.get(category.lower())

    def set_default(self, category: str, plugin_id: str) -> None:
        self._hydrate()
        with self._lock:
            self._default_impl[category.lower()] = plugin_id

        try:
            from database import session_local
            from repositories.plugin_repository import (
                PluginCategoryDefaultRepository,
            )

            with session_local() as db:
                plugin = self._lookup_plugin_row(db, plugin_id)
                if plugin is not None:
                    PluginCategoryDefaultRepository(db).set_default(
                        category, plugin.oid,
                    )
                    db.commit()
                else:
                    logger.warning(
                        "PluginStateStore: no plugin row for %s; "
                        "set_default persisted in memory only",
                        plugin_id,
                    )
        except Exception:
            logger.exception(
                "PluginStateStore: failed to persist default %s=%s",
                category, plugin_id,
            )

    # ------------------------------------------------------------------
    # snapshot for admin UI
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Dict[str, object]]:
        self._hydrate()
        with self._lock:
            return {
                "enabled": dict(self._enabled),
                "default_impl": dict(self._default_impl),
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _lookup_plugin_row(db, plugin_id: str):
        """Translate the runtime ``plugin_id`` string to a ``Plugin``
        row. Tries ``manifest_plugin_id`` first (the install slug),
        falls back to ``name`` for plugins announced before
        cataloguing.
        """
        from models.sqlalchemy_models import Plugin

        return (
            db.query(Plugin)
            .filter(Plugin.deleted_date.is_(None))
            .filter(
                (Plugin.manifest_plugin_id == plugin_id)
                | (Plugin.name == plugin_id)
            )
            .first()
        )


_STORE: Optional[PluginStateStore] = None


def get_state_store() -> PluginStateStore:
    global _STORE
    if _STORE is None:
        _STORE = PluginStateStore()
    return _STORE


__all__ = ["PluginStateStore", "get_state_store"]
