"""Database-backed plugin installation inventory.

This service is the bridge between the physical install pipeline
(``.mpn`` archives, uv/docker installers, broker discovery) and the
durable ``plugin``/``plugin_state`` tables. The invariant is:

* local install/upgrade success writes a catalog row;
* uninstall soft-deletes that row;
* broker-discovered plugins are cataloged as disabled until an operator
  explicitly enables them.
"""
from __future__ import annotations

import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import UUID

from magellon_sdk.archive.manifest import (
    PluginArchiveManifest,
    load_manifest_bytes,
)
from magellon_sdk.discovery import Announce, Heartbeat
from magellon_sdk.models.manifest import PluginManifest
from sqlalchemy.orm import Session
from models.sqlalchemy_models import Plugin
from repositories.plugin_repository import PluginRepository, PluginStateRepository
from services.plugin_installer.protocol import InstallResult

logger = logging.getLogger(__name__)


class PluginCatalogPersistence:
    """Persists plugin install/discovery state into SQL."""

    CANONICAL_MANIFEST = "manifest.yaml"
    LEGACY_MANIFEST = "plugin.yaml"

    def __init__(self, session_factory: Any = None) -> None:
        if session_factory is None:
            from database import session_local
            session_factory = session_local
        self._session_factory = session_factory

    def record_install(
        self,
        archive_path: Path,
        result: InstallResult,
        *,
        user_id: Optional[UUID] = None,
    ) -> Plugin:
        """Record a successful local install or upgrade."""
        manifest = self._load_archive_manifest(archive_path)
        payload = _archive_manifest_payload(manifest)
        install_result = _install_result_payload(result)

        db = self._session_factory()
        try:
            row = PluginRepository(db).upsert_catalog(
                manifest.plugin_id,
                payload,
                install_result,
                user_id=user_id,
            )
            db.commit()
            return row
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def record_uninstall(self, plugin_id: str) -> bool:
        """Soft-delete a plugin catalog row after physical uninstall."""
        db = self._session_factory()
        try:
            row = _find_plugin_row(db, plugin_id)
            if row is None:
                db.commit()
                return False
            PluginRepository(db).soft_delete(row.oid)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_installed(self) -> Dict[str, str]:
        """Return ``{plugin_id: install_method}`` from the durable catalog."""
        db = self._session_factory()
        try:
            rows = PluginRepository(db).list_installed()
            return {
                (row.manifest_plugin_id or row.name): (row.install_method or "")
                for row in rows
                if row.manifest_plugin_id or row.name
            }
        finally:
            db.close()

    def record_announce(self, msg: Announce) -> None:
        """Catalog an announcing plugin if the DB has never seen it.

        A newly discovered plugin is intentionally disabled. Existing
        rows keep their operator state.
        """
        payload = _runtime_manifest_payload(
            plugin_id=msg.plugin_id,
            plugin_version=msg.plugin_version,
            category=msg.category,
            manifest=msg.manifest,
            backend_id=msg.backend_id,
            instance_id=msg.instance_id,
            source="announce",
        )
        install_result = {
            "install_method": "discovered",
            "install_dir": None,
            "image_ref": None,
            "container_ref": msg.task_queue,
        }
        self._upsert_discovered(
            plugin_id=msg.plugin_id,
            manifest=payload,
            install_result=install_result,
            seen_at=_as_utc_naive(msg.ts),
        )

    def record_heartbeat(self, msg: Heartbeat) -> None:
        """Mirror heartbeat time and create a disabled stub if needed."""
        payload = {
            "name": msg.plugin_id,
            "version": msg.plugin_version,
            "author": "Unknown",
            "category": msg.category,
            "backend_id": msg.plugin_id,
            "schema_version": "1",
            "description": "",
            "discovered": {
                "source": "heartbeat",
                "instance_id": msg.instance_id,
                "status": msg.status,
            },
        }
        self._upsert_discovered(
            plugin_id=msg.plugin_id,
            manifest=payload,
            install_result={"install_method": "discovered"},
            seen_at=_as_utc_naive(msg.ts),
        )

    def _upsert_discovered(
        self,
        *,
        plugin_id: str,
        manifest: Dict[str, Any],
        install_result: Dict[str, Any],
        seen_at: datetime,
    ) -> None:
        db = self._session_factory()
        created = False
        try:
            repo = PluginRepository(db)
            state_repo = PluginStateRepository(db)
            # Look up by manifest_plugin_id first (exact slug match),
            # then fall back to (category, backend_id). The heartbeat
            # path uses the runtime plugin_id ("FFT Plugin") which
            # doesn't match the install-time slug ("fft"); without
            # the fallback we'd create a parallel "discovered" row
            # for every installed plugin that's currently announcing.
            existing = repo.get_by_manifest_plugin_id(plugin_id)
            if existing is None:
                existing = repo.get_by_category_backend(
                    manifest.get("category") or "",
                    manifest.get("backend_id") or "",
                )
            created = existing is None
            if existing is None:
                row = repo.upsert_catalog(plugin_id, manifest, install_result)
            else:
                # An install-time row already represents this plugin;
                # don't overwrite its install_dir / port / endpoint
                # with discovery-time nulls. Just update the heartbeat.
                row = existing
            state_repo.touch_heartbeat(row.oid, seen_at)
            if created:
                state_repo.set_enabled(row.oid, False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        if created:
            try:
                from core.plugin_state import get_state_store
                get_state_store().set_enabled(plugin_id, False)
            except Exception:
                logger.exception(
                    "could not update in-memory disabled state for %s",
                    plugin_id,
                )

    def _load_archive_manifest(self, archive_path: Path) -> PluginArchiveManifest:
        with zipfile.ZipFile(archive_path) as z:
            for name in (self.CANONICAL_MANIFEST, self.LEGACY_MANIFEST):
                try:
                    with z.open(name) as f:
                        return load_manifest_bytes(f.read())
                except KeyError:
                    continue
        raise FileNotFoundError(
            f"archive {archive_path} contains neither "
            f"{self.CANONICAL_MANIFEST} nor {self.LEGACY_MANIFEST}"
        )


def get_plugin_catalog_persistence() -> PluginCatalogPersistence:
    return PluginCatalogPersistence()


def persist_announce(msg: Announce) -> None:
    """Best-effort module-level helper for the liveness listener."""
    get_plugin_catalog_persistence().record_announce(msg)


def persist_heartbeat(msg: Heartbeat) -> None:
    """Best-effort module-level helper for the liveness listener."""
    get_plugin_catalog_persistence().record_heartbeat(msg)


def _archive_manifest_payload(manifest: PluginArchiveManifest) -> Dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    payload["name"] = manifest.name
    payload["version"] = manifest.version
    payload["author"] = manifest.author or "Unknown"
    payload["category"] = manifest.category
    payload["backend_id"] = manifest.backend_id or manifest.plugin_id
    payload["archive_id"] = str(manifest.archive_id)
    payload["schema_version"] = manifest.manifest_version
    return payload


def _runtime_manifest_payload(
    *,
    plugin_id: str,
    plugin_version: str,
    category: str,
    manifest: PluginManifest,
    backend_id: Optional[str],
    instance_id: str,
    source: str,
) -> Dict[str, Any]:
    payload = manifest.model_dump(mode="json")
    info = manifest.info
    payload["name"] = info.name or plugin_id
    payload["version"] = info.version or plugin_version
    payload["author"] = info.developer or "Unknown"
    payload["category"] = category
    payload["backend_id"] = backend_id or manifest.resolved_backend_id()
    payload["schema_version"] = info.schema_version or "1"
    payload["description"] = info.description or ""
    payload["discovered"] = {"source": source, "instance_id": instance_id}
    return payload


def _install_result_payload(result: InstallResult) -> Dict[str, Any]:
    return {
        "install_method": result.install_method,
        "install_dir": str(result.install_dir) if result.install_dir else None,
        "image_ref": None,
        "container_ref": None,
        "http_endpoint": result.http_endpoint,
        "port": result.port,
    }


def _find_plugin_row(db: Session, plugin_id: str) -> Optional[Plugin]:
    row = PluginRepository(db).get_by_manifest_plugin_id(plugin_id)
    if row is not None:
        return row
    return (
        db.query(Plugin)
        .filter(Plugin.name == plugin_id)
        .filter(Plugin.deleted_date.is_(None))
        .first()
    )


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


__all__ = [
    "PluginCatalogPersistence",
    "get_plugin_catalog_persistence",
    "persist_announce",
    "persist_heartbeat",
]
