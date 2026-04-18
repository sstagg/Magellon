"""Filesystem-backed plugin catalog (H3b).

Stores ``.magplugin`` archives uploaded via ``POST /plugins/catalog``
under ``CoreService/data/plugin_catalog/``. Each catalog entry is:

- ``<catalog_id>.magplugin`` — the archive bytes as uploaded.
- ``<catalog_id>.json``     — parsed manifest + upload metadata. Kept
  alongside so a read-only scan of the directory at boot is enough
  to reconstruct the index without re-unzipping every archive.

Catalog id is the slug ``<plugin_id>-<version>``. Collisions with an
existing catalog id are handled as "replace" — the author pushed a new
build of the same version. If you want strict immutability, enforce it
at the HTTP layer; this module's contract is "last-write wins."

Scope notes:

- **No review workflow.** Upload is immediate-publish. A future H3b.2
  (human gate) can slot between this module's :meth:`upload` and the
  manifest becoming queryable via :meth:`search` — maintain the same
  API here, add a ``status`` field and filter ``search`` to approved
  entries. Not doing it today to ship the user-visible Browse-plugins
  UX in one session.

- **Trust.** Anyone with access to the catalog endpoint can push an
  archive that installs an arbitrary Docker image. Same ``gate behind
  admin auth before public exposure`` caveat as H2 applies.
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from magellon_sdk.archive import (
    PluginArchiveManifest,
    load_manifest_bytes,
)

logger = logging.getLogger(__name__)


# Default catalog directory. Overridable by the endpoint layer if an
# operator sets MAGELLON_CATALOG_DIR; keeping a module-level default
# means tests can bypass the env var by calling set_catalog_dir()
# before constructing PluginCatalog.
_DEFAULT_CATALOG_DIR = Path("data") / "plugin_catalog"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class CatalogEntry:
    """One plugin published to the catalog.

    ``manifest`` is the parsed ``plugin.yaml``. ``archive_path`` points
    to the on-disk ``.magplugin`` — the install flow needs it to hand
    to the existing /install/archive bytes handler without re-fetching
    anything.
    """
    catalog_id: str
    manifest: PluginArchiveManifest
    archive_path: Path
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        m = self.manifest
        return {
            "catalog_id": self.catalog_id,
            "plugin_id": m.plugin_id,
            "name": m.name,
            "version": m.version,
            "category": m.category,
            "sdk_compat": m.sdk_compat,
            "image_ref": m.image.ref,
            "description": m.description,
            "developer": m.developer,
            "license": m.license,
            "uploaded_at": self.uploaded_at.isoformat(),
            "uploaded_by": self.uploaded_by,
        }


# ---------------------------------------------------------------------------
# Catalog store
# ---------------------------------------------------------------------------

class PluginCatalog:
    """Thread-safe filesystem-backed catalog."""

    def __init__(self, catalog_dir: Optional[Path] = None) -> None:
        self.dir = Path(catalog_dir) if catalog_dir else _DEFAULT_CATALOG_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, CatalogEntry] = {}
        self._lock = threading.Lock()
        self._rescan()

    # -- catalog_id derivation ------------------------------------------

    @staticmethod
    def _catalog_id(manifest: PluginArchiveManifest) -> str:
        # <plugin_id>-<version>. plugin_id is already a lowercase slug
        # (validated by PluginArchiveManifest); version is whatever the
        # author declared. Replace anything that'd confuse filesystems.
        version = manifest.version.replace("/", "_")
        return f"{manifest.plugin_id}-{version}"

    # -- persistence -----------------------------------------------------

    def _sidecar_path(self, catalog_id: str) -> Path:
        return self.dir / f"{catalog_id}.json"

    def _archive_path(self, catalog_id: str) -> Path:
        return self.dir / f"{catalog_id}.magplugin"

    def _rescan(self) -> None:
        """Load every sidecar+archive pair in the catalog dir.

        Called at boot and after each mutation so concurrent processes
        (e.g. a future multi-worker CoreService) converge. For single-
        process use the in-memory dict is authoritative.
        """
        new: Dict[str, CatalogEntry] = {}
        for sidecar in self.dir.glob("*.json"):
            catalog_id = sidecar.stem
            archive_path = self._archive_path(catalog_id)
            if not archive_path.exists():
                logger.warning(
                    "catalog: sidecar %s has no matching archive — skipping",
                    sidecar.name,
                )
                continue
            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
                # Manifest is the authoritative metadata; we re-parse it
                # rather than trust a denormalized copy in the sidecar.
                manifest = PluginArchiveManifest.model_validate(data["manifest"])
                entry = CatalogEntry(
                    catalog_id=catalog_id,
                    manifest=manifest,
                    archive_path=archive_path,
                    uploaded_at=datetime.fromisoformat(data["uploaded_at"]),
                    uploaded_by=data.get("uploaded_by"),
                )
                new[catalog_id] = entry
            except Exception:  # noqa: BLE001
                logger.exception("catalog: failed to load %s", sidecar.name)
        with self._lock:
            self._entries = new

    def _persist(self, entry: CatalogEntry) -> None:
        payload = {
            "manifest": entry.manifest.model_dump(),
            "uploaded_at": entry.uploaded_at.isoformat(),
            "uploaded_by": entry.uploaded_by,
        }
        self._sidecar_path(entry.catalog_id).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    # -- public API ------------------------------------------------------

    def upload(
        self,
        *,
        archive_bytes: bytes,
        manifest: PluginArchiveManifest,
        uploaded_by: Optional[str] = None,
    ) -> CatalogEntry:
        """Store an archive + manifest sidecar. Last-write wins on
        catalog_id collision (same plugin_id + version)."""
        catalog_id = self._catalog_id(manifest)
        archive_path = self._archive_path(catalog_id)
        archive_path.write_bytes(archive_bytes)
        entry = CatalogEntry(
            catalog_id=catalog_id,
            manifest=manifest,
            archive_path=archive_path,
            uploaded_by=uploaded_by,
        )
        self._persist(entry)
        with self._lock:
            self._entries[catalog_id] = entry
        return entry

    def get(self, catalog_id: str) -> Optional[CatalogEntry]:
        with self._lock:
            return self._entries.get(catalog_id)

    def remove(self, catalog_id: str) -> Optional[CatalogEntry]:
        with self._lock:
            entry = self._entries.pop(catalog_id, None)
        if entry is None:
            return None
        # Remove both files — ignore missing-file errors so operators
        # can manually clean up half-broken entries without tripping us.
        for path in (self._archive_path(catalog_id), self._sidecar_path(catalog_id)):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        return entry

    def search(
        self,
        *,
        query: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[CatalogEntry]:
        """Filter by substring match on name/description/plugin_id and
        exact category match. Both filters optional; no filters = all."""
        q = query.lower().strip() if query else None
        cat = category.lower().strip() if category else None
        with self._lock:
            entries = list(self._entries.values())
        results: List[CatalogEntry] = []
        for e in entries:
            m = e.manifest
            if cat and m.category.lower() != cat:
                continue
            if q:
                haystack = " ".join([
                    m.plugin_id, m.name, m.description, m.developer,
                ]).lower()
                if q not in haystack:
                    continue
            results.append(e)
        # Stable order: most-recently-uploaded first — matches what a
        # browse UI expects to surface.
        results.sort(key=lambda e: e.uploaded_at, reverse=True)
        return results

    def categories(self) -> Dict[str, int]:
        """Category → count. Drives the UI's category-chip filter so
        empty categories don't show up."""
        out: Dict[str, int] = {}
        with self._lock:
            for e in self._entries.values():
                out[e.manifest.category] = out.get(e.manifest.category, 0) + 1
        return out


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_CATALOG: Optional[PluginCatalog] = None


def get_catalog() -> PluginCatalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = PluginCatalog()
    return _CATALOG


__all__ = [
    "CatalogEntry",
    "PluginCatalog",
    "get_catalog",
    "load_manifest_bytes",
]
