"""Generic plugin HTTP router — discovery + batch submission for any plugin.

Endpoints:
    GET  /plugins/                              — list registered plugins
    GET  /plugins/{plugin_id}/info              — plugin metadata
    GET  /plugins/{plugin_id}/health            — liveness probe
    GET  /plugins/{plugin_id}/requirements      — dependency check
    GET  /plugins/{plugin_id}/schema/input      — input JSON schema
    GET  /plugins/{plugin_id}/schema/output     — output JSON schema
    POST /plugins/{plugin_id}/jobs              — submit one job
    POST /plugins/{plugin_id}/jobs/batch        — fan out over N images
    GET  /plugins/jobs                          — list jobs (optional plugin filter)
    GET  /plugins/jobs/{job_id}                 — job detail

Plugin-specific routes (preview/retune for template-picker, etc.) remain on
the plugin's own router. This controller covers everything that's uniform
across plugins.
"""
from __future__ import annotations

import asyncio
import io
import logging
import uuid
import zipfile
from datetime import datetime, datetime as _datetime, timezone as _timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

# Sentinel for max() over heartbeat datetimes; lets entries without a
# heartbeat sort below entries with one without raising on None compares.
_MIN_DT = _datetime.min.replace(tzinfo=_timezone.utc)

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from core.installed_plugins import get_installed_registry
from core.plugin_catalog import get_catalog
from core.plugin_docker_runner import (
    DockerNotAvailable,
    VolumeMount,
    get_runner as get_docker_runner,
)
from core.plugin_liveness_registry import get_registry as get_liveness_registry
from core.plugin_state import get_state_store
from magellon_sdk import __version__ as sdk_version
from magellon_sdk.archive import (
    PluginArchiveManifest,
    SchemaVersionError,
    SdkCompatError,
    check_sdk_compat,
    load_manifest_bytes,
)
from magellon_sdk.bus import get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.categories.contract import CATEGORIES, CategoryContract
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import (
    Capability,
    Condition,
    IsolationLevel,
    PluginManifest,
    TaskMessage,
    TaskStatus,
    Transport,
)
from services.job_manager import job_manager

logger = logging.getLogger(__name__)

plugins_router = APIRouter()


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class PluginSummary(BaseModel):
    """Discovery payload — identity + the capability fields a UI / manager
    needs to decide *whether* and *how* to call this plugin.

    The full manifest is also fetchable at /plugins/{id}/manifest, but
    embedding the small high-signal subset here means the discovery
    endpoint is enough to render a plugin picker / health dashboard
    without N round-trips."""
    plugin_id: str
    category: str
    name: str
    version: str
    schema_version: str
    description: str
    developer: str
    # Capability subset surfaced into discovery — full manifest at /manifest
    capabilities: list[Capability] = []
    supported_transports: list[Transport] = []
    default_transport: Transport = Transport.IN_PROCESS
    isolation: IsolationLevel = IsolationLevel.IN_PROCESS
    # How the UI should treat this entry:
    # - ``in-process``: PluginBase subclass living in this CoreService
    #   process; reachable via POST /plugins/{plugin_id}/jobs.
    # - ``broker``: external plugin (Docker container or separate
    #   process) that announced itself on ``magellon.plugins.liveness``;
    #   dispatch flows through the bus, not through this controller's
    #   /jobs endpoint.
    kind: Literal["in-process", "broker"] = "in-process"
    # Operator state (H1). ``enabled`` defaults True until an operator
    # toggles it. ``is_default_for_category`` is derived from the
    # per-category default-impl selection — the UI uses it to render
    # a "Default" badge and to decide which impl a category-scoped
    # dispatch would pick today.
    enabled: bool = True
    is_default_for_category: bool = False
    # Plugin-declared task queue (SDK 1.1+ Announce.task_queue). ``None``
    # for pre-1.1 plugins; the dispatcher falls back to the legacy
    # category-scoped route in that case.
    task_queue: Optional[str] = None


class JobSubmitRequest(BaseModel):
    """Submit one job for a plugin. ``input`` shape is validated by the plugin."""
    input: Dict[str, Any]
    name: Optional[str] = None
    image_id: Optional[str] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None
    target_backend: Optional[str] = None
    """Pin the dispatch to a specific backend within the plugin's
    category (X.1). Only meaningful for broker-dispatched plugins;
    ignored by the in-process path. When set and no live backend
    matches, the controller returns 503 instead of round-robining."""
    parent_run_id: Optional[uuid.UUID] = None
    """Optional PipelineRun rollup the new job belongs to (Phase 8 /
    2026-05-04 reviewer-flagged Medium #6). Pre-Phase-8 callers leave
    None → job lands as a standalone run; UI rollup view shows it
    alone. Pipeline orchestrators set this so children link back to
    the parent rollup via ImageJob.parent_run_id."""


class BatchSubmitRequest(BaseModel):
    """Fan out the same plugin over many inputs (one job per input)."""
    inputs: List[Dict[str, Any]] = Field(..., min_length=1)
    name: Optional[str] = None
    image_ids: Optional[List[str]] = None
    user_id: Optional[str] = None
    msession_id: Optional[str] = None
    target_backend: Optional[str] = None
    parent_run_id: Optional[uuid.UUID] = None


# ---------------------------------------------------------------------------
# Capabilities — one consolidated catalog (X.1)
# ---------------------------------------------------------------------------
#
# UI and dispatcher both need the same picture: which categories exist,
# which backends serve each, which is default. Today this is split across
# GET /plugins/, GET /plugins/categories/defaults, and GET
# /plugins/{id}/manifest — three reads + a join in JS. /capabilities
# returns one snapshot.

class _BackendSummary(BaseModel):
    """One backend serving a category. Folds plugin + manifest + state."""

    backend_id: str
    plugin_id: str
    """``<category>/<short>`` form to match the rest of the discovery API."""
    name: str
    version: str
    schema_version: str
    description: str = ""
    developer: str = ""
    capabilities: list[Capability] = []
    isolation: IsolationLevel = IsolationLevel.IN_PROCESS
    default_transport: Transport = Transport.IN_PROCESS
    live_replicas: int
    enabled: bool
    is_default_for_category: bool
    task_queue: Optional[str] = None


class _CategoryCapabilities(BaseModel):
    code: int
    name: str
    description: str
    default_backend: Optional[str] = None
    backends: list[_BackendSummary] = []
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class _CapabilitiesResponse(BaseModel):
    sdk_version: str
    categories: list[_CategoryCapabilities] = []


@plugins_router.get(
    "/capabilities",
    summary="Consolidated catalog: categories × backends + defaults",
    response_model=_CapabilitiesResponse,
)
async def list_capabilities() -> _CapabilitiesResponse:
    """Single-shot snapshot for the dispatcher and the UI.

    For each known :class:`CategoryContract` we list every live backend
    (deduplicated by ``(category, backend_id)``, replicas counted),
    annotate the operator-pinned default, and embed the category's
    canonical input/output JSON Schemas. Reads from the same liveness
    registry + state store the dispatcher consults — no separate
    cache, no risk of drift.
    """
    state = get_state_store()

    # Group live entries by (category, backend_id). Replicas (same
    # plugin_id with different instance_ids) collapse into one summary
    # row with ``live_replicas`` counted.
    by_category_backend: Dict[str, Dict[str, list]] = {}
    for entry in get_liveness_registry().list_live():
        cat_key = (entry.category or "").lower()
        backend_key = (entry.backend_id or entry.plugin_id or "").lower() or "unknown"
        by_category_backend.setdefault(cat_key, {}).setdefault(backend_key, []).append(entry)

    response_categories: list[_CategoryCapabilities] = []
    for code, contract in sorted(CATEGORIES.items(), key=lambda kv: kv[0]):
        cat_key = contract.category.name.lower()
        default_backend = state.get_default(cat_key)
        backends = []
        for backend_key, entries in sorted(by_category_backend.get(cat_key, {}).items()):
            # Pick a representative entry for manifest fields. All
            # replicas of one backend share manifest/version, so any is
            # equivalent; we take the most recent heartbeat for stability.
            rep = max(
                entries,
                key=lambda e: e.last_heartbeat or _MIN_DT,
            )
            manifest = rep.manifest
            info = manifest.info if manifest is not None else None
            short_id = rep.plugin_id
            composed_id = (
                short_id if "/" in short_id else f"{cat_key}/{short_id}"
            )
            is_default = state.get_default(cat_key) == short_id
            backends.append(_BackendSummary(
                backend_id=backend_key,
                plugin_id=composed_id,
                name=short_id,
                version=(info.version if info else rep.plugin_version) or "?",
                schema_version=(info.schema_version if info else "1") or "1",
                description=(info.description if info else "") or "",
                developer=(info.developer if info else "") or "",
                capabilities=list(manifest.capabilities) if manifest else [],
                isolation=manifest.isolation if manifest else IsolationLevel.CONTAINER,
                default_transport=(
                    manifest.default_transport if manifest else Transport.RMQ
                ),
                live_replicas=len(entries),
                enabled=state.is_enabled(short_id),
                is_default_for_category=is_default,
                task_queue=rep.task_queue,
            ))


        # X.9: deterministic ordering — default backend first, then
        # alphabetical by backend_id. UIs can render straight from this
        # without re-sorting, and golden / contract tests get a stable
        # response shape across runs.
        backends.sort(key=lambda b: (
            0 if b.is_default_for_category else 1,
            b.backend_id,
        ))

        # Best-effort JSON Schema for the category I/O. Some
        # CategoryContract.input_model classes may not emit clean
        # JSON Schema (exotic types); failing here would break the
        # whole endpoint, so swallow.
        try:
            input_schema = (
                contract.input_model.model_json_schema() if contract.input_model else None
            )
        except Exception:  # noqa: BLE001
            input_schema = None
        try:
            output_schema = (
                contract.output_model.model_json_schema() if contract.output_model else None
            )
        except Exception:  # noqa: BLE001
            output_schema = None

        response_categories.append(_CategoryCapabilities(
            code=code,
            name=contract.category.name,
            description=contract.category.description,
            default_backend=default_backend,
            backends=backends,
            input_schema=input_schema,
            output_schema=output_schema,
        ))

    return _CapabilitiesResponse(
        sdk_version=sdk_version,
        categories=response_categories,
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@plugins_router.get("/", summary="List all registered plugins")
async def list_plugins() -> List[PluginSummary]:
    """List every plugin the liveness registry has seen.

    Post-PM3 the four-way join (in-process registry × liveness × state
    store × catalog) lives in :class:`PluginManagerService`. This route
    delegates; the wire shape is byte-identical to the pre-PM3
    response since :class:`services.plugin_manager.PluginView` and
    :class:`PluginSummary` carry the same fields.
    """
    from database import session_local
    from services.plugin_manager import get_plugin_manager

    with session_local() as db:
        manager = get_plugin_manager(db)
        views = manager.list_all()
        # Mutations inside list_all() (auto-seed of default impl) write
        # through the state store, which owns its own DB commit. We
        # still commit the session in case any future read picks up
        # work — cheap and avoids a "no commit" footgun later.
        db.commit()
    return [PluginSummary(**v.model_dump()) for v in views]


@plugins_router.get(
    "/{plugin_id:path}/status",
    response_model=List[Condition],
    summary="Plugin status — Conditions[] (PM2)",
)
def plugin_status(plugin_id: str) -> List[Condition]:
    """Kubernetes-style multi-axis status for one plugin (PM2).

    Returns ``Conditions[]`` covering Installed / Enabled / Live /
    Healthy / Default. Cheaper than re-fetching the full ``GET
    /plugins/`` join when the UI only needs to refresh the chip
    cluster on a status pulse.

    Liveness data comes from the in-memory ``PluginLivenessRegistry``
    (registry already keys on ``(plugin_id, instance_id)`` per
    reviewer-flagged High #3 of the plan revision — the manager
    aggregates across replicas for the headline ``Live`` axis).
    """
    from database import session_local
    from services.plugin_manager import get_plugin_manager

    with session_local() as db:
        return get_plugin_manager(db).status(db, plugin_id)


@plugins_router.get(
    "/db",
    summary="All cataloged plugins with physical-install location",
)
def plugins_db():
    """Every plugin row in the DB catalog, including offline ones.

    Distinct from ``GET /plugins/`` (which lists currently-announcing
    plugins from the in-memory liveness registry). This endpoint
    answers "what's installed on this server, where do they live, and
    how were they installed" — needed by the operator UI's "Installed"
    tab to render the where-does-this-plugin-live column.
    """
    from database import session_local
    from services.plugin_manager import get_plugin_manager

    with session_local() as db:
        return get_plugin_manager(db).list_installed_full()


@plugins_router.get(
    "/updates",
    summary="Available updates for installed plugins (PM6)",
)
def plugin_updates():
    """Cross-reference installed catalog × local plugin catalog.

    For each installed plugin, returns one row when the local catalog
    advertises a strictly-newer version. Severity is bucketed by
    SemVer (``patch`` / ``minor`` / ``major``) so the UI can colour
    the upgrade chip without re-comparing client-side.

    Per the plan §9, server-side reads from the LOCAL catalog only —
    there's no server-side hub fetch. Hub-fed updates land in the
    local catalog via uploads (today) or via a future hub-fetch flow
    that is intentionally out of PM6's scope.
    """
    from database import session_local
    from services.plugin_manager import get_plugin_manager

    with session_local() as db:
        return get_plugin_manager(db).list_updates()


@plugins_router.get(
    "/{plugin_id:path}/replicas",
    summary="Per-replica health for one plugin (PM5)",
)
def plugin_replicas(plugin_id: str):
    """Per-replica view (PM5) — one row per ``instance_id`` for the plugin.

    The liveness registry already keys on ``(plugin_id, instance_id)``;
    this endpoint surfaces the per-instance rows. Status classifies
    each replica as ``Healthy`` / ``Stale`` / ``Lost`` from heartbeat
    age — see :meth:`PluginManagerService.replicas` for thresholds.
    """
    from database import session_local
    from services.plugin_manager import get_plugin_manager

    with session_local() as db:
        return get_plugin_manager(db).replicas(plugin_id)


@plugins_router.get("/{plugin_id:path}/manifest", summary="Plugin capability manifest")
async def plugin_manifest(plugin_id: str) -> PluginManifest:
    """Full capability description — what the plugin needs (resources,
    isolation) and how it can be reached (transports). Sourced from
    the broker's announce envelope (cached in the liveness registry).
    """
    short = _strip_category_prefix(plugin_id)
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id in (short, plugin_id) and entry.manifest is not None:
            return entry.manifest
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


def _live_entry(plugin_id: str):
    """Find the liveness entry for a plugin or 404. Replaces the
    pre-PI-6 ``_require_plugin`` which read from the in-process
    registry — now everything is a broker plugin."""
    short = _strip_category_prefix(plugin_id)
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id in (short, plugin_id):
            return entry
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@plugins_router.get("/{plugin_id:path}/info", summary="Plugin metadata")
async def plugin_info(plugin_id: str):
    """Read identity from the announce manifest. Pre-PI-6 this called
    PluginBase.get_info() on an in-process instance; now it's a flat
    projection of manifest.info."""
    entry = _live_entry(plugin_id)
    if entry.manifest is None:
        raise HTTPException(status_code=503, detail="Plugin manifest pending")
    info = entry.manifest.info
    return {
        "name": info.name,
        "developer": info.developer,
        "description": info.description,
        "version": info.version,
        "schema_version": getattr(info, "schema_version", "1") or "1",
    }


@plugins_router.get("/{plugin_id:path}/health", summary="Plugin liveness probe")
async def plugin_health(plugin_id: str):
    """A plugin in the live registry is heartbeating; if it's not in
    the registry, ``_live_entry`` 404s."""
    entry = _live_entry(plugin_id)
    return {
        "status": "ok",
        "last_heartbeat_at": (
            entry.last_heartbeat.isoformat() if entry.last_heartbeat else None
        ),
    }


def _category_contract_for_plugin(plugin_id: str) -> Optional[CategoryContract]:
    """Resolve ``plugin_id`` → :class:`CategoryContract` tolerantly.

    Schema is a property of the **category**, not the running instance,
    so we should be able to answer ``GET /plugins/{id}/schema/input``
    on a stopped or never-started plugin too. Resolution order:

      1. Live registry — bare or composed runtime form
         ("template-picker" or "particle_picking/template-picker").
         Covers running plugins; fastest path.
      2. DB catalog — match against ``manifest_plugin_id`` (the slug
         the operator typed when installing) or ``oid`` (the stable
         UUID). Covers installed-but-stopped plugins, and accepts
         the oid form as a stable alternative for free.

    Returns ``None`` only when no resolver matched — the endpoint then
    400s/404s as appropriate. Production rollouts should never see
    None for a plugin that's actually installed.

    Distinct from :func:`_category_for_plugin` (further down) which
    returns just the category-name string for the live registry only.
    Different concerns, different return shapes — keep them separate.
    """
    short = _strip_category_prefix(plugin_id)
    # 1. Live registry
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id in (short, plugin_id):
            return _category_contract_by_name(entry.category)
    # 2. DB catalog — covers installed-but-stopped + oid form
    category = _category_for_plugin_from_db(plugin_id, short)
    if category:
        return _category_contract_by_name(category)
    return None


# Back-compat alias — the pre-2026-05 helper was named ``_category_for_live_plugin``
# (live-registry only). The new resolver is strictly a superset: it
# covers the same live path plus a DB fallback. Aliasing keeps any
# callers that imported the old name working without churn.
_category_for_live_plugin = _category_contract_for_plugin


def _category_for_plugin_from_db(plugin_id: str, short: str) -> Optional[str]:
    """DB-backed identifier → category name resolver.

    Tries (in order): ``manifest_plugin_id == short``,
    ``manifest_plugin_id == plugin_id``, ``oid == plugin_id`` (parsed
    as UUID), ``name == short``. Returns ``None`` when none match.
    Reads on a short-lived session so this stays cheap to call from
    request handlers.
    """
    from sqlalchemy.orm import Session as _Session
    from database import session_local
    from models.sqlalchemy_models import Plugin

    db: _Session = session_local()
    try:
        for candidate in (short, plugin_id):
            row = (
                db.query(Plugin)
                .filter(Plugin.manifest_plugin_id == candidate)
                .filter(Plugin.deleted_date.is_(None))
                .first()
            )
            if row and row.category:
                return row.category
        # oid path — only attempt if the input parses as UUID; cheap
        # to skip otherwise so we don't try a UUID query for every
        # slug request.
        try:
            oid = uuid.UUID(plugin_id)
        except (ValueError, AttributeError):
            oid = None
        if oid is not None:
            row = (
                db.query(Plugin)
                .filter(Plugin.oid == oid)
                .filter(Plugin.deleted_date.is_(None))
                .first()
            )
            if row and row.category:
                return row.category
        # Last-ditch fallback: match by display ``name`` (the announce
        # form before P5 used the human name). Bounded scan; tens of
        # rows in production. Skip if short is empty.
        if short:
            row = (
                db.query(Plugin)
                .filter(Plugin.name == short)
                .filter(Plugin.deleted_date.is_(None))
                .first()
            )
            if row and row.category:
                return row.category
        return None
    finally:
        db.close()


@plugins_router.get("/{plugin_id:path}/schema/input", summary="Plugin input JSON schema")
async def plugin_input_schema(plugin_id: str):
    """Schema comes from the plugin's category contract — every backend
    in a category shares the same input/output shape (the whole point
    of CategoryContract). The React form reader uses this to render
    the per-plugin form.

    The plugin does NOT have to be live: schema is per-category, so
    ``_category_contract_for_plugin`` falls back to the DB catalog
    (matching ``manifest_plugin_id`` or ``oid``) so a stopped plugin's
    form still renders on the detail page.
    """
    contract = _category_contract_for_plugin(plugin_id)
    if contract is None or contract.input_model is None:
        raise HTTPException(status_code=404, detail=f"No input schema for {plugin_id}")
    return contract.input_model.model_json_schema()


@plugins_router.get("/{plugin_id:path}/schema/output", summary="Plugin output JSON schema")
async def plugin_output_schema(plugin_id: str):
    contract = _category_contract_for_plugin(plugin_id)
    if contract is None or contract.output_model is None:
        raise HTTPException(status_code=404, detail=f"No output schema for {plugin_id}")
    return contract.output_model.model_json_schema()


# ---------------------------------------------------------------------------
# Job submission — single and batch
# ---------------------------------------------------------------------------

@plugins_router.post("/{plugin_id:path}/jobs", summary="Submit one plugin job (async)")
async def submit_job(plugin_id: str, request: JobSubmitRequest, sid: str | None = None):
    """Dispatch one job to a broker plugin via ``bus.tasks.send``.

    Post-PI-6 there are no in-process plugins; every dispatch flows
    through the bus. The plugin's runner consumes the task and
    publishes the result + step events back. ``job_manager`` rows
    track lifecycle the same way regardless of where the plugin runs.
    """
    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_job(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@plugins_router.post("/{plugin_id:path}/jobs/batch", summary="Submit a batch of plugin jobs (one per input)")
async def submit_batch(plugin_id: str, request: BatchSubmitRequest, sid: str | None = None):
    if request.image_ids is not None and len(request.image_ids) != len(request.inputs):
        raise HTTPException(
            status_code=422,
            detail="image_ids length must match inputs length when provided",
        )

    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_batch(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find_broker_plugin(plugin_id: str) -> Optional[CategoryContract]:
    """Look up a broker plugin by plugin_id, resolve its category contract.

    Plugins in the liveness registry use whatever ``plugin_id`` they
    announced (typically ``info.name``, e.g. ``"FFT — magnitude spectrum"``);
    the ``/plugins/`` list prepends the category (e.g.
    ``"fft/FFT — magnitude spectrum"``); the manifest's bare slug
    (e.g. ``"fft"``) is a third valid form an operator might type.
    Accept all three; returns the :class:`CategoryContract` — that's
    what we need for dispatch (category-scoped TaskRoute + input_model
    for validation).

    Match order:
      1. ``entry.plugin_id == plugin_id`` (composed or runtime form match)
      2. ``entry.plugin_id == short_id`` (composed form stripped to runtime)
      3. ``entry.backend_id == short_id`` (manifest slug match — covers
         e.g. ``/plugins/fft/jobs`` where the runtime form differs)
    """
    short_id = _strip_category_prefix(plugin_id)
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id == short_id or entry.plugin_id == plugin_id:
            return _category_contract_by_name(entry.category)
    # Slug fallback — matches the install-time backend_id rather than
    # the announce-time plugin_id. Covers the common case where the
    # plugin announces under its display name but the URL/UI refers
    # to it by its manifest slug.
    for entry in get_liveness_registry().list_live():
        if entry.backend_id and entry.backend_id == short_id:
            return _category_contract_by_name(entry.category)
    return None


def _resolve_dispatch_target(
    plugin_id: str, contract: CategoryContract,
    *,
    target_backend: Optional[str] = None,
) -> "PluginLivenessEntry":
    """Pick the live plugin instance that should receive this dispatch.

    Three HTTP-layer failures short-circuit here so callers see a real
    error instead of a silently queued task:

    * ``target_backend`` set but no live plugin claims it → 503.
    * No live impl for this category → 503 (H1.c).
    * Named impl is present but disabled → 409.

    The target has to be both ``enabled`` and in the liveness window.
    A disabled default still counts as the default — we don't silently
    fail over to a different impl — so the UI can surface the real
    state to the operator.

    When ``target_backend`` is set, the backend pin wins over the
    operator-pinned default and over the URL-named impl: the caller
    asked for a specific implementation and silently routing to a
    different one would mask their intent.
    """
    from core.plugin_liveness_registry import PluginLivenessEntry  # local: avoid cycle

    state = get_state_store()
    short_id = _strip_category_prefix(plugin_id)

    # Candidates for this category, from the liveness registry.
    live: list[PluginLivenessEntry] = [
        e for e in get_liveness_registry().list_live()
        if e.category.lower() == contract.category.name.lower()
    ]

    # Backend pin wins. We do not consult the URL-named impl or the
    # operator default — the pin is a binding directive.
    if target_backend:
        wanted = target_backend.lower()
        for e in live:
            if (e.backend_id or "").lower() != wanted:
                continue
            if not state.is_enabled(e.plugin_id):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Backend {wanted!r} for category "
                        f"{contract.category.name!r} is disabled"
                    ),
                )
            return e
        raise HTTPException(
            status_code=503,
            detail=(
                f"No live plugin claims backend_id={target_backend!r} for "
                f"category {contract.category.name!r}"
            ),
        )

    # Explicit impl? Must match the URL exactly. Disabled → 409.
    for e in live:
        if e.plugin_id == short_id:
            if not state.is_enabled(e.plugin_id):
                raise HTTPException(
                    status_code=409,
                    detail=f"Plugin {short_id} is disabled",
                )
            return e

    # No explicit impl name — caller passed a category-scoped id.
    # Route to the pinned default if it's live and enabled.
    default_id = state.get_default(contract.category.name.lower())
    if default_id:
        for e in live:
            if e.plugin_id == default_id:
                if not state.is_enabled(e.plugin_id):
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Default impl {default_id!r} for category "
                            f"{contract.category.name!r} is disabled"
                        ),
                    )
                return e

    # No default and no explicit id — any live enabled candidate will do.
    for e in live:
        if state.is_enabled(e.plugin_id):
            return e

    raise HTTPException(
        status_code=503,
        detail=(
            f"No live enabled plugin for category "
            f"{contract.category.name!r} — cannot dispatch"
        ),
    )


def _normalize_category_key(s: str) -> str:
    """Collapse spaces / underscores / case so display-form names
    (``"Particle Picking"``) and slug-form names (``"particle_picking"``)
    compare equal. Plugin manifests use the slug form; ``CategoryContract``
    declares the display form. Without this, the DB-fallback resolver
    can't bridge the two."""
    return "".join(s.lower().split()).replace("_", "").replace("-", "")


def _category_contract_by_name(category_name: str) -> Optional[CategoryContract]:
    """Find a :class:`CategoryContract` by its category name.

    :data:`CATEGORIES` is keyed by code; brokers announce by name. Scan
    once — there are only a handful of categories in practice. The
    matcher is space/underscore/case insensitive so plugin manifests
    can use the slug form (``"particle_picking"``) and the contract
    side can use the display form (``"Particle Picking"``) without
    coordination.
    """
    target = _normalize_category_key(category_name)
    for contract in CATEGORIES.values():
        if _normalize_category_key(contract.category.name) == target:
            return contract
    return None


# ---------------------------------------------------------------------------
# Broker dispatch — publish to magellon.tasks.<category> via the bus
# ---------------------------------------------------------------------------

_BROKER_ENVELOPE_SOURCE = "magellon/core_service/plugin_controller"


def _validate_broker_input(contract: CategoryContract, raw: Dict[str, Any]):
    """Validate input against the category's Pydantic input model.

    Contracts like ``CTF``/``FFT``/``MOTIONCOR_CATEGORY`` pin
    ``input_model`` (e.g. ``CtfInput``). ``PARTICLE_PICKER`` doesn't
    pin one yet (see contract.py) — fall back to round-tripping the
    raw dict so dispatch still works for those.
    """
    model = contract.input_model
    if model is None:
        return raw
    try:
        return model.model_validate(raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")


def _derive_subject(
    contract: CategoryContract,
    validated_input,
) -> Tuple[Optional[str], Optional[uuid.UUID]]:
    """Derive (subject_kind, subject_id) for dispatch (Phase 3 / 2026-05-04 fix).

    Authoritative resolution at dispatch time so the runner's
    contract-default fallback isn't load-bearing. Three cases:

      * Aggregate-input categories (TWO_D_CLASSIFICATION → input has
        ``particle_stack_id``): subject is the source artifact.
      * Image-keyed categories (everything else): subject_kind comes
        from the contract (default ``'image'``); subject_id stays
        None here — the dispatch layer at ``_submit_broker_job``
        threads ``request.image_id`` into ImageJobTask.subject_id
        directly via ``create_job``.

    Returns (subject_kind, subject_id). Either may be None.
    """
    subject_kind: Optional[str] = (
        contract.subject_kind if contract is not None else None
    )
    subject_id: Optional[uuid.UUID] = None

    # Aggregate categories carry the subject id explicitly on the
    # input model. Read it without coupling to the concrete class.
    candidate_id = getattr(validated_input, "particle_stack_id", None)
    if candidate_id is not None:
        if isinstance(candidate_id, str):
            try:
                subject_id = uuid.UUID(candidate_id)
            except ValueError:
                subject_id = None
        else:
            subject_id = candidate_id

    return subject_kind, subject_id


def _build_task_dto(
    contract: CategoryContract,
    validated_input,
    task_id: uuid.UUID,
    job_id: str,
    user_id: Optional[str],
    target_backend: Optional[str] = None,
    subject_kind: Optional[str] = None,
    subject_id: Optional[uuid.UUID] = None,
) -> TaskMessage:
    """Wrap a validated input in the TaskMessage the bus transports.

    ``task_id`` must match the one registered with ``job_manager.create_job``;
    otherwise the step-event projector can't link events back to the
    job row and the row stays ``queued`` forever.

    ``target_backend`` rides on the DTO so the dispatcher can route to
    a specific backend's queue. The controller path uses the resolved
    ``target.task_queue`` directly (no round-trip through the
    dispatcher), but the field is still set so the consuming plugin
    can confirm it was the intended recipient.

    ``subject_kind`` / ``subject_id`` (Phase 3, reviewer-flagged High #4
    in 2026-05-04 fix) are stamped explicitly here. The runner's
    contract-default fallback (Phase 3d) covers ``subject_kind`` even
    when None; ``subject_id`` MUST be set here for aggregate-input
    categories or the projector loses the lineage link.
    """
    data = (
        validated_input.model_dump(mode="json")
        if hasattr(validated_input, "model_dump")
        else validated_input
    )
    return TaskMessage(
        id=task_id,
        worker_instance_id=uuid.uuid4(),
        job_id=uuid.UUID(job_id),
        data=data,
        type=contract.category,
        status=TaskStatus(code=0, name="pending", description="Task is pending"),
        target_backend=target_backend,
        subject_kind=subject_kind,
        subject_id=subject_id,
    )


def _publish_to_bus(
    contract: CategoryContract, task: TaskMessage, target_queue: Optional[str] = None,
) -> bool:
    """Publish to the target impl's queue (SDK 1.1+) or the legacy
    category-scoped route when no impl-specific queue is known.

    The fallback matters for pre-1.1 plugins whose announce doesn't
    carry ``task_queue``; they still consume from the legacy category
    queue and the binder's legacy_queue_map resolves the route.
    """
    if target_queue:
        route = TaskRoute.named(target_queue)
    else:
        route = TaskRoute.for_category(contract)
    envelope = Envelope.wrap(
        source=_BROKER_ENVELOPE_SOURCE,
        type="magellon.task.dispatch",
        subject=route.subject,
        data=task,
    )
    receipt = get_bus().tasks.send(route, envelope)
    if not receipt.ok:
        logger.error(
            "broker dispatch failed on %s: %s", route.subject, receipt.error,
        )
    return receipt.ok


async def _submit_broker_job(
    plugin_id: str,
    contract: CategoryContract,
    request: JobSubmitRequest,
) -> Dict[str, Any]:
    validated = _validate_broker_input(contract, request.input)
    settings = (
        validated.model_dump(mode="json")
        if hasattr(validated, "model_dump") else validated
    )
    # Resolve the target impl BEFORE creating a job row — that way
    # H1.c's 503 ("no live enabled impl") doesn't leave an orphan
    # queued row behind.
    target = _resolve_dispatch_target(
        plugin_id, contract, target_backend=request.target_backend,
    )

    # Generate the task_id up front so the same id registered with the
    # job_manager rides inside the TaskMessage. The step-event projector
    # needs this linkage to flip the job row's status.
    task_id = uuid.uuid4()

    # Phase 3 / 2026-05-04 reviewer-flagged High #4: derive subject
    # axis at dispatch time so it lands on both the ImageJobTask row
    # and the TaskMessage. The classifier's particle_stack_id flows
    # from the input dict here straight onto the persistent row.
    subject_kind, subject_id = _derive_subject(contract, validated)

    envelope = job_manager.create_job(
        plugin_id=plugin_id,
        name=request.name or f"{plugin_id} job",
        settings=settings,
        task_ids=[task_id],
        image_ids=[request.image_id] if request.image_id else None,
        user_id=request.user_id,
        msession_id=request.msession_id,
        parent_run_id=getattr(request, "parent_run_id", None),
        subject_kind=subject_kind,
        subject_id=subject_id,
    )
    task = _build_task_dto(
        contract, validated, task_id, envelope["job_id"], request.user_id,
        target_backend=request.target_backend,
        subject_kind=subject_kind,
        subject_id=subject_id,
    )
    if not _publish_to_bus(contract, task, target.task_queue):
        job_manager.fail_job(envelope["job_id"], error="Failed to publish task to bus")
        raise HTTPException(status_code=502, detail="Failed to publish task to bus")
    return envelope


async def _submit_broker_batch(
    plugin_id: str,
    contract: CategoryContract,
    request: BatchSubmitRequest,
) -> Dict[str, Any]:
    # Up-front validation — fail the whole batch cleanly rather than
    # creating half the jobs then failing mid-flight.
    validated_inputs = [
        _validate_broker_input(contract, raw) for raw in request.inputs
    ]

    # Resolve the target impl once for the whole batch. Rolls any 503
    # (no live impl) / 409 (disabled) before a single job row is
    # created, so a batch never half-lands.
    target = _resolve_dispatch_target(
        plugin_id, contract, target_backend=request.target_backend,
    )

    envelopes: List[Dict[str, Any]] = []
    publish_failures: List[str] = []
    for idx, validated in enumerate(validated_inputs):
        image_id = request.image_ids[idx] if request.image_ids else None
        settings = (
            validated.model_dump(mode="json")
            if hasattr(validated, "model_dump") else validated
        )
        task_id = uuid.uuid4()
        # Same Phase-3 / Medium-#6 wiring as _submit_broker_job.
        subject_kind, subject_id = _derive_subject(contract, validated)
        env = job_manager.create_job(
            plugin_id=plugin_id,
            name=request.name or f"{plugin_id} batch [{idx + 1}/{len(validated_inputs)}]",
            settings=settings,
            task_ids=[task_id],
            image_ids=[image_id] if image_id else None,
            user_id=request.user_id,
            msession_id=request.msession_id,
            parent_run_id=getattr(request, "parent_run_id", None),
            subject_kind=subject_kind,
            subject_id=subject_id,
        )
        envelopes.append(env)
        task = _build_task_dto(
            contract, validated, task_id, env["job_id"], request.user_id,
            target_backend=request.target_backend,
            subject_kind=subject_kind,
            subject_id=subject_id,
        )
        if not _publish_to_bus(contract, task, target.task_queue):
            job_manager.fail_job(env["job_id"], error="Failed to publish task to bus")
            publish_failures.append(env["job_id"])

    if publish_failures:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to publish {len(publish_failures)}/{len(envelopes)} tasks to bus",
        )
    return {"jobs": envelopes, "count": len(envelopes)}


# ---------------------------------------------------------------------------
# Operator state: enable/disable, default-impl selector (H1)
# ---------------------------------------------------------------------------

class _SetDefaultRequest(BaseModel):
    plugin_id: str


def _strip_category_prefix(plugin_id: str) -> str:
    """Accept both ``plugin_id`` and ``<category>/<plugin_id>`` forms.

    The discovery list uses the composed form for UI uniqueness; the
    liveness registry + state store key on the bare plugin_id.
    """
    return plugin_id.split("/", 1)[1] if "/" in plugin_id else plugin_id


def _category_for_plugin(short_id: str) -> Optional[str]:
    for entry in get_liveness_registry().list_live():
        if entry.plugin_id == short_id:
            return entry.category
    return None


@plugins_router.post("/{plugin_id:path}/enable", summary="Enable dispatch to a plugin")
async def enable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Allow the dispatcher to route tasks to this plugin.

    Does not start the plugin — it's expected to be announcing already.
    No-op if already enabled. Enables are cheap and idempotent so the
    UI can fire blindly on toggle flip.
    """
    short_id = _strip_category_prefix(plugin_id)
    get_state_store().set_enabled(short_id, True)
    return {"plugin_id": short_id, "enabled": True}


@plugins_router.post("/{plugin_id:path}/disable", summary="Disable dispatch to a plugin")
async def disable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Quiesce a plugin without stopping it.

    The plugin keeps announcing + heartbeating; the dispatcher refuses
    new tasks. In-flight tasks are unaffected — this is a pause switch,
    not a kill switch. A disabled default impl still counts as the
    default for its category; a dispatch attempt returns 503 rather
    than silently promoting another impl.
    """
    short_id = _strip_category_prefix(plugin_id)
    get_state_store().set_enabled(short_id, False)
    return {"plugin_id": short_id, "enabled": False}


@plugins_router.get("/categories/defaults", summary="Per-category default impl map")
async def list_category_defaults() -> Dict[str, Any]:
    """Return current per-category default-impl selections.

    UI uses this to render "Default" badges. Key is lowercase category
    name; value is the plugin_id CoreService will route to when the
    dispatch is category-scoped (no explicit plugin_id in the URL).
    """
    snapshot = get_state_store().snapshot()
    return {"defaults": snapshot["default_impl"]}


@plugins_router.post(
    "/categories/{category}/default",
    summary="Pin the default impl for a category",
)
async def set_category_default(category: str, request: _SetDefaultRequest) -> Dict[str, Any]:
    """Choose which impl handles category-scoped dispatches.

    Category-scoped dispatch means "route a CTF task" without naming an
    impl: we publish to the default impl's task queue. A replacement
    impl (second CTF engine, community upload) can be installed and
    announced without taking traffic until the operator flips this.
    """
    short_id = _strip_category_prefix(request.plugin_id)
    # Validate the plugin is actually live + in this category — fail
    # loudly rather than pin a typo as default.
    cat = _category_for_plugin(short_id)
    if cat is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin {short_id} is not in the live registry — can't make it the default.",
        )
    if cat.lower() != category.lower():
        raise HTTPException(
            status_code=422,
            detail=f"Plugin {short_id} is in category {cat!r}, not {category!r}.",
        )
    get_state_store().set_default(category, short_id)
    return {"category": category.lower(), "default_plugin_id": short_id}


# ---------------------------------------------------------------------------
# Install flow — spawn a plugin container from a Docker image ref (H2)
# ---------------------------------------------------------------------------
#
# Security note: this endpoint launches arbitrary Docker images with the
# CoreService user's Docker privileges. In effect, anyone who can POST
# here can run code on the host. Gate behind an admin-only auth scope
# before exposing /plugins/install beyond localhost. H2 ships the
# mechanism; auth is a cross-cutting concern tracked separately.
#
# Scope clarification: H2 owns the container lifecycle. The operator is
# responsible for the image pointing at the right RMQ and declaring the
# right task_queue — CoreService does not inject config. A follow-up
# phase (plugin images reading RMQ from env with yaml fallback) can
# make "install arbitrary image and it just works" possible; today we
# assume the image was built for this deployment.

class _InstallVolume(BaseModel):
    host_path: str
    container_path: str
    read_only: bool = False


class _InstallPluginRequest(BaseModel):
    """Everything docker run needs. Everything config-ish the plugin
    itself reads from its own settings YAML — not our problem here."""
    image_ref: str = Field(..., description="Docker image ref, e.g. ghcr.io/org/plugin:v1")
    env: Dict[str, str] = Field(default_factory=dict)
    volumes: List[_InstallVolume] = Field(default_factory=list)
    network: Optional[str] = Field(
        default=None,
        description="Docker network name. Use the network RMQ is on "
                    "(e.g. 'magellon_default' under docker-compose) so "
                    "the plugin can resolve rabbitmq by hostname.",
    )


def _ensure_docker() -> None:
    """Fail fast with 503 when the docker CLI / daemon is unreachable.

    Called from every /installed endpoint before we touch the runner —
    better to tell the client "Docker unavailable" than surface a
    FileNotFoundError as a 500.
    """
    if not get_docker_runner().ping():
        raise HTTPException(
            status_code=503,
            detail="Docker is not available on this CoreService host.",
        )


@plugins_router.post("/install", summary="Install a plugin from a Docker image")
async def install_plugin(request: _InstallPluginRequest) -> Dict[str, Any]:
    """Spawn a plugin container in detached mode.

    The container will announce itself on ``magellon.plugins.announce.*``
    if it's a Magellon plugin image built for this deployment. That
    announcement flows into the liveness registry (same path the
    fixed-set plugins use); the GET /plugins/ page picks it up on the
    next refresh with ``kind=broker``.

    If the image is misconfigured (wrong RMQ host, wrong credentials,
    not actually a plugin), ``docker run`` itself succeeds but the
    plugin never announces. The installed-plugins entry stays
    ``running`` with no liveness match — the UI surfaces this as
    "installed but not announcing" so the operator can diagnose
    without CoreService pretending to know more than it does.
    """
    _ensure_docker()
    runner = get_docker_runner()
    volumes = [
        VolumeMount(v.host_path, v.container_path, v.read_only) for v in request.volumes
    ]
    entry = runner.run_image(
        image_ref=request.image_ref,
        env=request.env,
        volumes=volumes,
        network=request.network,
    )
    if entry.state == "failed":
        # Still record the entry so the operator can read the error
        # message from GET /installed; running it through the registry
        # keeps one consistent "where is my install" story.
        get_installed_registry().add(entry)
        raise HTTPException(
            status_code=502,
            detail=f"docker run failed: {entry.error or 'unknown error'}",
        )
    get_installed_registry().add(entry)
    return entry.to_dict()


def _parse_archive_bytes(raw: bytes):
    """Extract + validate plugin.yaml from archive bytes. Raises the
    right HTTPExceptions so callers can just propagate."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            try:
                with z.open("plugin.yaml") as f:
                    manifest_bytes = f.read()
            except KeyError:
                raise HTTPException(
                    status_code=422,
                    detail="archive has no top-level plugin.yaml — "
                           "pack with `magellon-sdk plugin pack <dir>`",
                )
    except zipfile.BadZipFile:
        raise HTTPException(status_code=422, detail="archive is not a valid zip file")

    try:
        return load_manifest_bytes(manifest_bytes)
    except SchemaVersionError as exc:
        raise HTTPException(status_code=422, detail=f"unsupported schema_version: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface pydantic + yaml errors as-is
        raise HTTPException(status_code=422, detail=f"invalid plugin.yaml: {exc}")


def _enforce_sdk_compat(manifest) -> None:
    try:
        check_sdk_compat(manifest.sdk_compat, sdk_version)
    except SdkCompatError as exc:
        # Hard-fail: installing a plugin whose SDK pin excludes us
        # risks field-shape drift at runtime. Better the operator
        # rebuilds their plugin against a compatible SDK.
        raise HTTPException(
            status_code=409,
            detail=f"plugin incompatible with this CoreService (SDK {sdk_version}): {exc}",
        )


def _install_from_manifest(manifest) -> Dict[str, Any]:
    """Docker-run the image declared in ``manifest`` with its defaults.

    Shared by both the raw-archive upload path and the catalog-install
    path — the "spawn the container + record the install" behaviour
    is identical once we have a validated manifest in hand.
    """
    _ensure_docker()
    runner = get_docker_runner()
    volumes = [
        VolumeMount(v.host, v.container, v.read_only)
        for v in manifest.install_defaults.volumes
    ]
    entry = runner.run_image(
        image_ref=manifest.image.ref,
        env=dict(manifest.install_defaults.env),
        volumes=volumes,
        network=manifest.install_defaults.network,
    )
    if entry.state == "failed":
        get_installed_registry().add(entry)
        raise HTTPException(
            status_code=502,
            detail=f"docker run failed: {entry.error or 'unknown error'}",
        )
    get_installed_registry().add(entry)

    response = entry.to_dict()
    response["archive"] = {
        "plugin_id": manifest.plugin_id,
        "name": manifest.name,
        "version": manifest.version,
        "category": manifest.category,
    }
    return response


@plugins_router.post(
    "/install/archive",
    summary="Install a plugin from a .mpn archive upload",
)
async def install_plugin_archive(
    archive: UploadFile = File(..., description="A .mpn zip archive."),
) -> Dict[str, Any]:
    """Accept a ``.mpn`` archive, validate its manifest, spawn
    the container using manifest defaults.

    The archive is what ``magellon-sdk plugin pack`` produces: a zip
    with a top-level ``plugin.yaml`` (see :mod:`magellon_sdk.archive`).
    """
    try:
        raw = await archive.read()
    finally:
        await archive.close()

    manifest = _parse_archive_bytes(raw)
    _enforce_sdk_compat(manifest)
    return _install_from_manifest(manifest)


# ---------------------------------------------------------------------------
# Plugin catalog (H3b) — filesystem-backed store for uploaded archives
# ---------------------------------------------------------------------------
#
# Upload is immediate-publish — no human review gate. See
# core/plugin_catalog.py top-of-module note for where that lives when
# we add it. Trust model: same as /install. Gate behind admin auth
# before public exposure.


class _CatalogInstallResponse(BaseModel):
    """POST /catalog/{catalog_id}/install response shape."""
    install: Dict[str, Any]
    catalog_id: str


@plugins_router.get("/catalog", summary="Browse the plugin catalog")
async def browse_catalog(
    search: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Return catalog entries with optional substring + category filter.

    ``categories`` is included so the UI can render a filter bar showing
    only categories that actually have entries — avoids dead chips.
    """
    cat = get_catalog()
    entries = [e.to_dict() for e in cat.search(query=search, category=category)]
    return {"entries": entries, "categories": cat.categories()}


@plugins_router.post("/catalog", summary="Upload a plugin archive to the catalog")
async def upload_catalog_entry(
    archive: UploadFile = File(..., description="A .mpn zip archive."),
) -> Dict[str, Any]:
    """Publish a ``.mpn`` archive to the catalog.

    Validates the manifest up front; SDK-compat mismatch is a warning
    here, not a hard fail — the catalog may host archives targeting
    future SDK versions, and the install endpoint enforces compat at
    install time.
    """
    try:
        raw = await archive.read()
    finally:
        await archive.close()

    manifest = _parse_archive_bytes(raw)
    # Do NOT _enforce_sdk_compat here — an archive incompatible with
    # today's CoreService may still be useful to catalog for a future
    # upgrade. Compat is checked at install time instead.
    entry = get_catalog().upload(archive_bytes=raw, manifest=manifest)
    return {"catalog_id": entry.catalog_id, **entry.to_dict()}


@plugins_router.delete(
    "/catalog/{catalog_id}",
    summary="Remove an entry from the catalog",
)
async def delete_catalog_entry(catalog_id: str) -> Dict[str, Any]:
    entry = get_catalog().remove(catalog_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"catalog entry {catalog_id} not found")
    return entry.to_dict()


@plugins_router.post(
    "/catalog/{catalog_id}/install",
    summary="Install a plugin from a catalog entry",
)
async def install_catalog_entry(catalog_id: str) -> _CatalogInstallResponse:
    """Re-use the upload-path install logic against the stored archive.

    Compat is enforced here (not at upload time) so catalog browsers
    see the entry even when it targets a future SDK — they just can't
    install it until CoreService upgrades.
    """
    entry = get_catalog().get(catalog_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"catalog entry {catalog_id} not found")
    _enforce_sdk_compat(entry.manifest)
    install_response = _install_from_manifest(entry.manifest)
    return _CatalogInstallResponse(install=install_response, catalog_id=catalog_id)


@plugins_router.get("/installed", summary="List installed plugin containers")
async def list_installed() -> Dict[str, Any]:
    """Return current installs with Docker-refreshed state.

    Joins each install_id against the liveness registry so the UI can
    distinguish "container is running and announcing" (healthy) from
    "container is running but not announcing" (config issue) and
    "container stopped/crashed" (Docker-level failure).
    """
    _ensure_docker()
    runner = get_docker_runner()
    live_plugin_ids = {
        e.plugin_id for e in get_liveness_registry().list_live()
    }

    rows: List[Dict[str, Any]] = []
    for entry in get_installed_registry().list():
        docker_state = runner.inspect_state(entry)
        if docker_state is not None:
            entry.state = docker_state
        row = entry.to_dict()
        # Best-effort liveness hint: if ANY live plugin was recorded
        # since this container started, mark it announcing. We can't
        # key on container_id (liveness doesn't know Docker IDs), so
        # this is a coarse "is anyone new talking?" signal. Future
        # work: have plugins stamp their container_id on Announce.
        row["announcing_on_bus"] = bool(live_plugin_ids)
        rows.append(row)
    return {"installed": rows}


@plugins_router.post("/installed/{install_id}/stop", summary="Stop an installed container")
async def stop_installed(install_id: str) -> Dict[str, Any]:
    _ensure_docker()
    entry = get_installed_registry().get(install_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Install {install_id} not found")
    get_docker_runner().stop(entry)
    return entry.to_dict()


@plugins_router.delete("/installed/{install_id}", summary="Remove an installed container")
async def remove_installed(install_id: str) -> Dict[str, Any]:
    _ensure_docker()
    entry = get_installed_registry().remove(install_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Install {install_id} not found")
    get_docker_runner().remove(entry)
    return entry.to_dict()


@plugins_router.get("/jobs", summary="List plugin jobs")
async def list_all_jobs(plugin_id: Optional[str] = None, limit: int = 100):
    return job_manager.list_jobs(plugin_id=plugin_id, limit=limit)


@plugins_router.get("/jobs/{job_id}", summary="Get plugin job detail")
async def get_any_job(job_id: str):
    try:
        return job_manager.get_job(job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")


@plugins_router.delete("/jobs/{job_id}", summary="Request cancellation of a running plugin job")
async def cancel_any_job(job_id: str):
    """Cooperative cancel: flags the job so the plugin stops at its next
    progress checkpoint. Terminal jobs are untouched; the current envelope
    is returned so the caller can observe the outcome."""
    try:
        envelope = job_manager.get_job(job_id, include_result=False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")

    if envelope["status"] in ("completed", "failed", "cancelled"):
        return envelope

    job_manager.request_cancel(job_id)
    return {**envelope, "cancel_requested": True}


