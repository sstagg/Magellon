"""PluginManagerService — server-side facade across the five plugin sources (PM3).

Joins:

  * **R1** :class:`PluginRegistry` — in-process plugins discovered at boot
  * **R2** :class:`PluginRepository` — durable catalog (alembic 0008, PM1)
  * **R3** :class:`PluginStateRepository` — operator ``enabled`` flag (PM1),
    surfaced via the in-memory :class:`PluginStateStore` shim for the
    dispatch hot path
  * **R4** :class:`PluginCategoryDefaultRepository` — per-category default
    impl (PM1), same shim
  * **R5** :class:`PluginLivenessRegistry` — broker-fed in-memory liveness

Pre-PM3 every caller (the ``GET /plugins/`` route, the dispatcher's
target resolver, the install pipeline's "is this plugin live yet?"
check) re-implemented the same four-way join inline. PM3 lifts that
into one place — server-side code now asks the manager
"who's running ctffind4?" instead of joining R1–R5 by hand.

Constructor-injected (reviewer-flagged PM3 acceptance criterion): no
module-level singleton, so tests pass fakes for the five collaborators
without monkey-patching anything.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional, Protocol

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
        in_process,                       # PluginRegistry
        liveness: PluginLivenessRegistry,
        state_store: _StateStoreLike,
        plugin_repo,                      # PluginRepository
    ) -> None:
        self._in_process = in_process
        self._liveness = liveness
        self._state = state_store
        self._plugin_repo = plugin_repo

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def list_all(self) -> List[PluginView]:
        """Discovery view — every live plugin (in-process + broker).

        Auto-seeds the per-category default impl: the first live plugin
        seen for a category becomes its default. Operators can override
        later via ``set_default``. Preserves the byte-for-byte legacy
        behaviour of ``GET /plugins/``.
        """
        in_proc_ids = {entry.plugin_id for entry in self._in_process.list()}
        live_entries = self._liveness.list_live()

        for entry in live_entries:
            if entry.category and self._state.get_default(entry.category) is None:
                self._state.set_default(entry.category, entry.plugin_id)

        seen: set[str] = set()
        out: List[PluginView] = []
        for entry in live_entries:
            view = self._view_from_liveness(entry, in_proc_ids)
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

    def list_running(self) -> List[PluginView]:
        """Liveness view — only plugins currently announcing on the bus."""
        in_proc_ids = {entry.plugin_id for entry in self._in_process.list()}
        return [
            self._view_from_liveness(e, in_proc_ids)
            for e in self._liveness.list_live()
        ]

    def get(self, plugin_id: str) -> Optional[PluginView]:
        """Lookup one plugin by id (accepts both bare and ``cat/id`` forms)."""
        short = _strip_category(plugin_id)
        in_proc_ids = {entry.plugin_id for entry in self._in_process.list()}
        for entry in self._liveness.list_live():
            if entry.plugin_id == short or entry.plugin_id == plugin_id:
                return self._view_from_liveness(entry, in_proc_ids)
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

    def _view_from_liveness(
        self,
        entry: PluginLivenessEntry,
        in_proc_ids: set[str],
    ) -> PluginView:
        plugin_id = entry.plugin_id
        if "/" not in plugin_id and entry.category:
            plugin_id = f"{entry.category}/{plugin_id}"
        kind: Literal["in-process", "broker"] = (
            "in-process" if plugin_id in in_proc_ids else "broker"
        )
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
                kind=kind,
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
            kind=kind,
            enabled=enabled,
            is_default_for_category=is_default,
            task_queue=entry.task_queue,
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


def get_plugin_manager(db: Session) -> PluginManagerService:
    """Build the facade with the real production collaborators.

    Caller owns ``db``: the session must outlive any read that lands
    on the catalog (``list_installed`` / ``status``). The facade
    itself doesn't open or close sessions.
    """
    from core.plugin_liveness_registry import get_registry as get_liveness_registry
    from core.plugin_state import get_state_store
    from plugins.registry import registry as in_process_registry
    from repositories.plugin_repository import PluginRepository

    return PluginManagerService(
        in_process=in_process_registry,
        liveness=get_liveness_registry(),
        state_store=get_state_store(),
        plugin_repo=PluginRepository(db),
    )


__all__ = [
    "PluginManagerService",
    "PluginView",
    "ReplicaInfo",
    "get_plugin_manager",
]
