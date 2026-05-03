"""Persistent storage for plugin catalog + operator state (PM1).

Three repositories, one per concern:

  * :class:`PluginRepository` — catalog identity. CRUD on the
    extended ``plugin`` table (alembic 0008): one row per installed
    plugin, keyed by ``oid`` (DB), located by ``manifest_plugin_id``
    (the install-package slug).
  * :class:`PluginStateRepository` — operator-mutable runtime state.
    PM1 owns ``enabled`` + heartbeat mirror; PM4 will extend with
    pause when its semantics are designed.
  * :class:`PluginCategoryDefaultRepository` — per-category default
    routing. Multi-category plugins are first-class: topaz can be
    default for TOPAZ_PARTICLE_PICKING but not for
    MICROGRAPH_DENOISING.

The pre-PM1 in-memory ``PluginStateStore`` and
``InstalledPluginsRegistry`` continue to exist as back-compat shims
that delegate here (see ``core/plugin_state.py`` /
``core/installed_plugins.py``); consumers using the singleton
``get_state_store()`` / ``get_installed_registry()`` API don't need
to change.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.sqlalchemy_models import Plugin, PluginCategoryDefault, PluginState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PluginRepository — catalog identity
# ---------------------------------------------------------------------------


class PluginRepository:
    """CRUD + lookup on the ``plugin`` catalog table.

    Soft-delete via the existing ``deleted_date`` + ``GCRecord``
    columns (XAF convention). ``list_installed`` excludes soft-
    deleted rows by default.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_catalog(
        self,
        manifest_plugin_id: str,
        manifest: Dict[str, Any],
        install_result: Dict[str, Any],
        *,
        user_id: Optional[UUID] = None,
    ) -> Plugin:
        """Insert or update the catalog row for ``manifest_plugin_id``.

        Looks up by ``manifest_plugin_id`` (install-package identity).
        On a re-install / upgrade we replace the columns in place
        rather than minting a new row — keeps ``Plugin.oid`` stable
        for FK references on ``ImageMetaData``.
        """
        existing = self.get_by_manifest_plugin_id(manifest_plugin_id)
        now = datetime.utcnow()

        category = manifest.get("category")
        backend_id = manifest.get("backend_id")
        version = manifest.get("version")
        author = manifest.get("author") or "Unknown"
        archive_id = manifest.get("archive_id")
        schema_version = manifest.get("schema_version") or "1"

        install_method = install_result.get("install_method")
        install_dir = install_result.get("install_dir")
        image_ref = install_result.get("image_ref")
        container_ref = install_result.get("container_ref")

        if existing is not None:
            existing.last_modified_date = now
            existing.last_modified_by = user_id
            existing.version = version
            existing.author = author
            existing.category = category
            existing.backend_id = backend_id
            existing.schema_version = schema_version
            existing.install_method = install_method
            existing.install_dir = install_dir
            existing.image_ref = image_ref
            existing.container_ref = container_ref
            existing.archive_id = archive_id
            existing.manifest_json = manifest
            existing.installed_date = now
            # Clear soft-delete on re-install — operator wants this
            # plugin back; honor that without making them undelete
            # via a separate API.
            existing.deleted_date = None
            existing.GCRecord = None
            return existing

        row = Plugin(
            oid=uuid.uuid4(),
            name=manifest.get("name") or manifest_plugin_id,
            manifest_plugin_id=manifest_plugin_id,
            version=version,
            author=author,
            category=category,
            backend_id=backend_id,
            schema_version=schema_version,
            install_method=install_method,
            install_dir=install_dir,
            image_ref=image_ref,
            container_ref=container_ref,
            archive_id=archive_id,
            manifest_json=manifest,
            installed_date=now,
            created_date=now,
            created_by=user_id,
        )
        self.db.add(row)
        return row

    def list_installed(self, *, include_deleted: bool = False) -> List[Plugin]:
        q = self.db.query(Plugin)
        if not include_deleted:
            q = q.filter(Plugin.deleted_date.is_(None), Plugin.GCRecord.is_(None))
        return q.order_by(Plugin.name).all()

    def get_by_oid(self, oid: UUID) -> Optional[Plugin]:
        return self.db.query(Plugin).filter(Plugin.oid == oid).first()

    def get_by_manifest_plugin_id(
        self, manifest_plugin_id: str
    ) -> Optional[Plugin]:
        return (
            self.db.query(Plugin)
            .filter(Plugin.manifest_plugin_id == manifest_plugin_id)
            .filter(Plugin.deleted_date.is_(None))
            .first()
        )

    def soft_delete(self, oid: UUID) -> None:
        row = self.get_by_oid(oid)
        if row is None:
            return
        row.deleted_date = datetime.utcnow()
        # GCRecord toggles the row out of default queries (XAF idiom).
        row.GCRecord = 1


# ---------------------------------------------------------------------------
# PluginStateRepository — operator-mutable runtime state
# ---------------------------------------------------------------------------


class PluginStateRepository:
    """Reads/writes ``plugin_state`` rows. Default ``enabled=True``
    when the row is missing — matches the in-memory shim's behaviour
    so an un-toggled plugin keeps dispatching."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_or_create(self, plugin_oid: UUID) -> PluginState:
        row = (
            self.db.query(PluginState)
            .filter(PluginState.plugin_oid == plugin_oid)
            .first()
        )
        if row is None:
            row = PluginState(plugin_oid=plugin_oid, enabled=True)
            self.db.add(row)
        return row

    def enabled(self, plugin_oid: UUID) -> bool:
        row = (
            self.db.query(PluginState)
            .filter(PluginState.plugin_oid == plugin_oid)
            .first()
        )
        return True if row is None else bool(row.enabled)

    def set_enabled(self, plugin_oid: UUID, enabled: bool) -> None:
        row = self._get_or_create(plugin_oid)
        row.enabled = enabled

    def touch_heartbeat(self, plugin_oid: UUID, when: datetime) -> None:
        row = self._get_or_create(plugin_oid)
        row.last_heartbeat_at = when
        row.last_seen_at = when

    def snapshot(self) -> Dict[str, Any]:
        rows = self.db.query(PluginState).all()
        return {
            str(r.plugin_oid): {
                "enabled": bool(r.enabled),
                "last_heartbeat_at": r.last_heartbeat_at,
                "last_seen_at": r.last_seen_at,
            }
            for r in rows
        }


# ---------------------------------------------------------------------------
# PluginCategoryDefaultRepository — default routing policy
# ---------------------------------------------------------------------------


class PluginCategoryDefaultRepository:
    """One row per category; multi-category plugins have multiple
    rows pointing at them. ``set_default`` clears any prior default
    for that category in the same transaction (atomic; concurrent
    toggles serialise on the row lock)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_default(self, category: str) -> Optional[UUID]:
        row = (
            self.db.query(PluginCategoryDefault)
            .filter(PluginCategoryDefault.category == category.lower())
            .first()
        )
        return None if row is None else row.plugin_oid

    def set_default(
        self,
        category: str,
        plugin_oid: UUID,
        *,
        user_id: Optional[str] = None,
    ) -> None:
        cat = category.lower()
        existing = (
            self.db.query(PluginCategoryDefault)
            .filter(PluginCategoryDefault.category == cat)
            .first()
        )
        now = datetime.utcnow()
        if existing is None:
            self.db.add(
                PluginCategoryDefault(
                    category=cat,
                    plugin_oid=plugin_oid,
                    set_at=now,
                    set_by_user_id=user_id,
                )
            )
            return
        existing.plugin_oid = plugin_oid
        existing.set_at = now
        existing.set_by_user_id = user_id

    def clear_default(self, category: str) -> None:
        cat = category.lower()
        self.db.query(PluginCategoryDefault).filter(
            PluginCategoryDefault.category == cat
        ).delete()

    def list_all(self) -> Dict[str, UUID]:
        return {
            r.category: r.plugin_oid
            for r in self.db.query(PluginCategoryDefault).all()
        }


__all__ = [
    "PluginRepository",
    "PluginStateRepository",
    "PluginCategoryDefaultRepository",
]
