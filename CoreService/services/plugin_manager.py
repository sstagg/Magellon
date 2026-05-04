"""PluginManagerService — server-side facade across the plugin sources (PM3).

Joins:

  * **R1** :class:`PluginRepository` — durable catalog (alembic 0008, PM1)
  * **R2** :class:`PluginStateRepository` — operator ``enabled`` flag (PM1),
    surfaced via the in-memory :class:`PluginStateStore` shim for the
    dispatch hot path
  * **R3** :class:`PluginCategoryDefaultRepository` — per-category default
    impl (PM1), same shim
  * **R4** :class:`PluginLivenessRegistry` — broker-fed in-memory liveness

Pre-PM3 every caller (the ``GET /plugins/`` route, the dispatcher's
target resolver, the install pipeline's "is this plugin live yet?"
check) re-implemented the same join inline. PM3 lifts that into one
place — server-side code now asks the manager
"who's running ctffind4?" instead of joining the sources by hand.

Constructor-injected (reviewer-flagged PM3 acceptance criterion): no
module-level singleton, so tests pass fakes for every collaborator
without monkey-patching anything.

PI-6 (2026-05-04): the in-process plugin registry collaborator was
dropped — no live PluginBase subclass exists in CoreService anymore;
all plugins are external broker plugins. ``kind`` always reports
``"broker"``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional, Protocol

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel
from sqlalchemy.orm import Session

from magellon_sdk.bus.services.liveness_registry import (
    PluginLivenessEntry,
    PluginLivenessRegistry,
)
from magellon_sdk.models import (
    Capability,
    Condition,
    IsolationLevel,
    Transport,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class PluginView(BaseModel):
    """Joined view across the five sources — what the UI sees per plugin.

    Field set is identical to the legacy ``plugins.controller.PluginSummary``
    so PM3's wire-shape-byte-identical acceptance holds: the controller
    can return ``List[PluginView]`` and the JSON response stays the same.
    """

    plugin_id: str
    category: str
    name: str
    version: str
    schema_version: str
    description: str
    developer: str
    capabilities: list[Capability] = []
    supported_transports: list[Transport] = []
    default_transport: Transport = Transport.IN_PROCESS
    isolation: IsolationLevel = IsolationLevel.IN_PROCESS
    kind: Literal["in-process", "broker"] = "in-process"
    enabled: bool = True
    is_default_for_category: bool = False
    task_queue: Optional[str] = None


@dataclass(frozen=True)
class CatalogVersionInfo:
    """One catalog row, normalized to the fields PM6's reducer needs.

    Decouples the version comparison from the catalog source's
    concrete shape: PluginCatalog returns CatalogEntry objects with a
    rich manifest; a future hub adapter would yield JSON. Both
    flatten through this dataclass.
    """

    version: str
    archive_url: Optional[str] = None
    release_notes_url: Optional[str] = None


class _CatalogSource(Protocol):
    """Catalog adapter the manager queries for "latest known version"."""

    def latest_for(self, slug: str) -> Optional[CatalogVersionInfo]: ...


class UpdateInfo(BaseModel):
    """One installed plugin × catalog row pair where catalog > installed (PM6)."""

    plugin_id: str
    current_version: str
    latest_version: str
    channel: Literal["stable"] = "stable"
    severity: Literal["patch", "minor", "major"]
    release_notes_url: Optional[str] = None
    archive_url: Optional[str] = None


class InstalledPluginView(BaseModel):
    """Catalog row with physical-location info — what the operator UI's
    "Installed" tab needs to render the where-does-this-plugin-live
    column.

    Distinct from :class:`PluginView` (the join across the five live
    sources): this DTO speaks ONLY to the persistent ``plugin`` table
    (PM1's alembic 0008). A plugin shows up here whether or not it's
    currently announcing on the bus — the UI cross-references with the
    liveness registry to decide which rows are "installed but not
    running" vs. "installed and live".
    """

    plugin_id: str
    """Composed ``<category>/<name>`` for UI consistency with PluginView."""
    manifest_plugin_id: Optional[str] = None
    """The install-package slug (manifest's plugin_id) — what the
    install pipeline keys on. ``None`` for legacy rows that pre-date
    PM1's alembic 0008 column."""
    name: str
    version: Optional[str] = None
    category: Optional[str] = None
    description: str = ""
    developer: Optional[str] = None
    install_method: Optional[Literal["docker", "uv", "archive", "discovered"]] = None
    install_dir: Optional[str] = None
    image_ref: Optional[str] = None
    container_ref: Optional[str] = None
    archive_id: Optional[str] = None
    installed_date: Optional[datetime] = None
    enabled: bool = True
    is_default_for_category: bool = False


class ReplicaInfo(BaseModel):
    """Per-replica health for one plugin (PM5).

    The liveness registry already keys on ``(plugin_id, instance_id)``
    (`magellon-sdk/.../bus/services/liveness_registry.py:137`), so
    PM5 surfaces what the registry already tracks — no schema change,
    no re-key. ``host`` and ``container_id`` are nullable: the
    Announce envelope doesn't carry them today; the field exists so
    a future SDK rev can populate without a wire-shape change.
    """

    instance_id: str
    host: Optional[str] = None
    container_id: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
    last_task_completed_at: Optional[datetime] = None
    in_flight_task_count: int = 0
    status: Literal["Healthy", "Stale", "Lost"]


# ---------------------------------------------------------------------------
# Collaborator protocols (Protocol = duck-typed, so tests pass fakes)
# ---------------------------------------------------------------------------


class _StateStoreLike(Protocol):
    """The :class:`PluginStateStore` surface the manager depends on."""

    def is_enabled(self, plugin_id: str) -> bool: ...
    def get_default(self, category: str) -> Optional[str]: ...
    def set_enabled(self, plugin_id: str, enabled: bool) -> None: ...
    def set_default(self, category: str, plugin_id: str) -> None: ...


# ---------------------------------------------------------------------------
# PluginManagerService
# ---------------------------------------------------------------------------


class PluginManagerService:
    """Read + mutate plugin state across R1–R5 through one object.

    Public reads return :class:`PluginView` (or :class:`Condition` for
    ``status``); public mutations write through to the shared state
    store so the dispatcher's hot-path lookups see the change
    immediately and the DB write-through (PM1) survives a restart.
    """

    def __init__(
        self,
        liveness: PluginLivenessRegistry,
        state_store: _StateStoreLike,
        plugin_repo,                      # PluginRepository
    ) -> None:
        self._liveness = liveness
        self._state = state_store
        self._plugin_repo = plugin_repo

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_all(self) -> List[PluginView]:
        """Discovery view — every live plugin announcing on the bus.

        Auto-seeds the per-category default impl: the first live plugin
        seen for a category becomes its default. Operators can override
        later via ``set_default``. Post-PI-6 every plugin is a broker
        plugin — no in-process classification.
        """
        live_entries = self._liveness.list_live()

        for entry in live_entries:
            if entry.category and self._state.get_default(entry.category) is None:
                self._state.set_default(entry.category, entry.plugin_id)

        seen: set[str] = set()
        out: List[PluginView] = []
        for entry in live_entries:
            view = self._view_from_liveness(entry)
            if view.plugin_id in seen:
                continue
            seen.add(view.plugin_id)
            out.append(view)
        return out

    def list_installed(self) -> List[PluginView]:
        """Catalog view — every cataloged plugin, running or not.

        Reads from the DB (PM1's ``plugin`` table). A row that exists
        here but isn't in ``list_running()`` is "installed but not
        announcing" — useful for the operator UI's offline list.
        """
        rows = self._plugin_repo.list_installed()
        return [self._view_from_plugin_row(p) for p in rows]

    def list_installed_full(self) -> List[InstalledPluginView]:
        """Same scope as :meth:`list_installed` but exposes the
        physical-location columns (``install_method``, ``install_dir``,
        ``image_ref``, ``container_ref``) the manager UI's "Installed"
        tab renders so operators can see where each plugin lives —
        a directory, a Docker image, or a running container.
        """
        rows = self._plugin_repo.list_installed()
        return [self._installed_view_from_plugin_row(p) for p in rows]

    def list_running(self) -> List[PluginView]:
        """Liveness view — only plugins currently announcing on the bus."""
        return [self._view_from_liveness(e) for e in self._liveness.list_live()]

    def get(self, plugin_id: str) -> Optional[PluginView]:
        """Lookup one plugin by id (accepts both bare and ``cat/id`` forms)."""
        short = _strip_category(plugin_id)
        for entry in self._liveness.list_live():
            if entry.plugin_id == short or entry.plugin_id == plugin_id:
                return self._view_from_liveness(entry)
        return None

    def status(self, db: Session, plugin_id: str) -> List[Condition]:
        """Conditions[] (PM2) for one plugin — aggregates per-replica heartbeats."""
        from services.plugin_conditions import compute_conditions

        short = _strip_category(plugin_id)
        latest = self._aggregate_heartbeat(short)
        return compute_conditions(
            db,
            plugin_name=short,
            is_live=latest is not None,
            last_heartbeat_at=latest,
        )

    def list_updates(
        self,
        catalog_source: Optional[_CatalogSource] = None,
    ) -> List[UpdateInfo]:
        """Cross-reference installed catalog against a version source (PM6).

        ``catalog_source`` defaults to :class:`LocalCatalogSource`
        (the filesystem-backed ``core.plugin_catalog`` — populated by
        operator uploads or a future hub-fetch flow). Returns one row
        per installed plugin where the source advertises a newer
        version. Plugins absent from the source, or with versions
        equal-to-or-older than installed, do not appear.
        """
        source = catalog_source or LocalCatalogSource()
        out: List[UpdateInfo] = []
        for installed in self._plugin_repo.list_installed():
            current = installed.version
            slug = installed.manifest_plugin_id or installed.name
            if not current or not slug:
                continue
            latest = source.latest_for(slug)
            if latest is None:
                continue
            severity = _semver_severity(current, latest.version)
            if severity is None:
                continue
            composed_id = (
                f"{installed.category.lower()}/{installed.name}"
                if installed.category else installed.name
            )
            out.append(UpdateInfo(
                plugin_id=composed_id,
                current_version=current,
                latest_version=latest.version,
                severity=severity,
                release_notes_url=latest.release_notes_url,
                archive_url=latest.archive_url,
            ))
        return out

    def replicas(
        self,
        plugin_id: str,
        *,
        now: Optional[datetime] = None,
        healthy_window: timedelta = timedelta(seconds=30),
        stale_window: timedelta = timedelta(seconds=60),
    ) -> List[ReplicaInfo]:
        """Per-replica health view (PM5).

        ``Healthy`` = heartbeat ≤ ``healthy_window`` (default 2× the
        15s heartbeat interval). ``Stale`` = heartbeat between
        ``healthy_window`` and ``stale_window`` (the registry's reap
        cutoff). ``Lost`` = entries past ``healthy_window`` and inside
        ``stale_window`` but with no heartbeat in 2× the interval —
        in practice ``Lost`` and ``Stale`` collapse to the same
        registry-tracked state, but the rendition lets the UI show
        "presumed dead" without losing the row entirely.

        Replicas reaped by the registry's own stale cutoff (60s by
        default) drop out of the list — there's no per-replica
        memory beyond the live window. PM5 deliberately does not
        introduce one; if a replica vanishes for >60s it's treated
        the same as a replica that never existed.
        """
        short = _strip_category(plugin_id)
        ref_now = now or datetime.now(timezone.utc)

        out: List[ReplicaInfo] = []
        for entry in self._liveness.list_live(now=ref_now):
            if entry.plugin_id != short:
                continue
            ts = getattr(entry, "last_heartbeat", None)
            age = ref_now - ts if ts is not None else stale_window * 2
            if age <= healthy_window:
                status: Literal["Healthy", "Stale", "Lost"] = "Healthy"
            elif age <= stale_window:
                # 1×–2× interval: registry still tracks, but pulses are
                # missed — call it Lost so the UI's red-amber-green is
                # decisive.
                status = "Lost"
            else:
                status = "Stale"
            out.append(ReplicaInfo(
                instance_id=entry.instance_id,
                host=None,
                container_id=None,
                last_heartbeat_at=ts,
                last_task_completed_at=None,
                in_flight_task_count=0,
                status=status,
            ))
        return out

    # ------------------------------------------------------------------
    # Mutations — write through the state store (in-memory + DB)
    # ------------------------------------------------------------------

    def enable(self, plugin_id: str) -> None:
        self._state.set_enabled(_strip_category(plugin_id), True)

    def disable(self, plugin_id: str) -> None:
        self._state.set_enabled(_strip_category(plugin_id), False)

    def set_default(self, category: str, plugin_id: str) -> None:
        self._state.set_default(category, _strip_category(plugin_id))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _aggregate_heartbeat(self, short_id: str) -> Optional[datetime]:
        latest: Optional[datetime] = None
        for e in self._liveness.list_live():
            if e.plugin_id != short_id:
                continue
            ts = getattr(e, "last_heartbeat", None)
            if ts is not None and (latest is None or ts > latest):
                latest = ts
        return latest

    def _view_from_liveness(self, entry: PluginLivenessEntry) -> PluginView:
        plugin_id = entry.plugin_id
        if "/" not in plugin_id and entry.category:
            plugin_id = f"{entry.category}/{plugin_id}"
        enabled = self._state.is_enabled(entry.plugin_id)
        is_default = self._state.get_default(entry.category) == entry.plugin_id

        manifest = entry.manifest
        if manifest is not None:
            info = manifest.info
            return PluginView(
                plugin_id=plugin_id,
                category=entry.category,
                name=entry.plugin_id,
                version=info.version,
                schema_version=info.schema_version or "1",
                description=info.description,
                developer=info.developer,
                capabilities=list(manifest.capabilities),
                supported_transports=list(manifest.supported_transports),
                default_transport=manifest.default_transport,
                isolation=manifest.isolation,
                kind="broker",
                enabled=enabled,
                is_default_for_category=is_default,
                task_queue=entry.task_queue,
            )
        return PluginView(
            plugin_id=plugin_id,
            category=entry.category,
            name=entry.plugin_id,
            version=entry.plugin_version or "?",
            schema_version="1",
            description="(manifest pending — restart the plugin "
                        "or wait for the next announce)",
            developer="",
            capabilities=[],
            supported_transports=[Transport.RMQ],
            default_transport=Transport.RMQ,
            isolation=IsolationLevel.CONTAINER,
            kind="broker",
            enabled=enabled,
            is_default_for_category=is_default,
            task_queue=entry.task_queue,
        )

    def _installed_view_from_plugin_row(self, plugin) -> InstalledPluginView:
        manifest = plugin.manifest_json or {}
        category = (plugin.category or "").lower()
        plugin_id = f"{category}/{plugin.name}" if category else plugin.name
        return InstalledPluginView(
            plugin_id=plugin_id,
            manifest_plugin_id=plugin.manifest_plugin_id,
            name=plugin.name,
            version=plugin.version,
            category=category or None,
            description=manifest.get("description") or "",
            developer=plugin.author,
            install_method=plugin.install_method,
            install_dir=plugin.install_dir,
            image_ref=plugin.image_ref,
            container_ref=plugin.container_ref,
            archive_id=str(plugin.archive_id) if plugin.archive_id else None,
            installed_date=plugin.installed_date,
            enabled=self._state.is_enabled(plugin.name),
            is_default_for_category=(
                self._state.get_default(category) == plugin.name
            ),
        )

    def _view_from_plugin_row(self, plugin) -> PluginView:
        manifest = plugin.manifest_json or {}
        category = (plugin.category or "").lower()
        plugin_id = f"{category}/{plugin.name}" if category else plugin.name
        return PluginView(
            plugin_id=plugin_id,
            category=category,
            name=plugin.name,
            version=plugin.version or "?",
            schema_version=plugin.schema_version or "1",
            description=manifest.get("description") or "",
            developer=plugin.author or "",
            capabilities=[],
            supported_transports=[Transport.RMQ],
            default_transport=Transport.RMQ,
            isolation=IsolationLevel.CONTAINER,
            kind="broker",
            enabled=self._state.is_enabled(plugin.name),
            is_default_for_category=(
                self._state.get_default(category) == plugin.name
            ),
            task_queue=None,
        )


# ---------------------------------------------------------------------------
# Helpers + production wiring
# ---------------------------------------------------------------------------


def _strip_category(plugin_id: str) -> str:
    """Accept both ``plugin_id`` and ``<category>/<plugin_id>`` forms."""
    return plugin_id.split("/", 1)[1] if "/" in plugin_id else plugin_id


def _semver_severity(
    current: str, latest: str,
) -> Optional[Literal["patch", "minor", "major"]]:
    """Severity bucket for ``latest`` over ``current`` (PM6 reducer).

    Uses :class:`packaging.version.Version` so SemVer prerelease tags
    sort correctly (``1.2.3-rc.1 < 1.2.3``). Returns ``None`` when
    ``latest`` is not strictly greater than ``current`` — including
    the unparseable / equal cases — so the caller can treat ``None``
    as "no update available."
    """
    try:
        cur = Version(current)
        lat = Version(latest)
    except InvalidVersion:
        return None
    if lat <= cur:
        return None
    if lat.major != cur.major:
        return "major"
    if lat.minor != cur.minor:
        return "minor"
    return "patch"


class LocalCatalogSource:
    """Catalog source backed by the filesystem catalog (``core.plugin_catalog``).

    Reads the local catalog populated by operator uploads. For
    air-gapped deployments this IS the source of truth; for hub-
    aware deployments, a future PR will define ``HubCatalogSource``
    that mirrors the same Protocol — the manager doesn't change.
    """

    def __init__(self, catalog=None) -> None:
        if catalog is None:
            from core.plugin_catalog import get_catalog
            catalog = get_catalog()
        self._catalog = catalog

    def latest_for(self, slug: str) -> Optional[CatalogVersionInfo]:
        # Walk all entries for this plugin_id; pick the one with the
        # highest version. The catalog isn't per-plugin keyed
        # (catalog_id is ``<plugin_id>-<version>``), so we have to scan.
        latest: Optional[CatalogVersionInfo] = None
        latest_v: Optional[Version] = None
        for entry in self._catalog.search(query=None, category=None):
            if entry.manifest.plugin_id != slug:
                continue
            try:
                v = Version(entry.manifest.version)
            except InvalidVersion:
                continue
            if latest_v is None or v > latest_v:
                latest_v = v
                latest = CatalogVersionInfo(
                    version=entry.manifest.version,
                    archive_url=str(entry.archive_path),
                    release_notes_url=None,
                )
        return latest


def get_plugin_manager(db: Session) -> PluginManagerService:
    """Build the facade with the real production collaborators.

    Caller owns ``db``: the session must outlive any read that lands
    on the catalog (``list_installed`` / ``status``). The facade
    itself doesn't open or close sessions.
    """
    from core.plugin_liveness_registry import get_registry as get_liveness_registry
    from core.plugin_state import get_state_store
    from repositories.plugin_repository import PluginRepository

    return PluginManagerService(
        liveness=get_liveness_registry(),
        state_store=get_state_store(),
        plugin_repo=PluginRepository(db),
    )


__all__ = [
    "CatalogVersionInfo",
    "InstalledPluginView",
    "LocalCatalogSource",
    "PluginManagerService",
    "PluginView",
    "ReplicaInfo",
    "UpdateInfo",
    "get_plugin_manager",
]
