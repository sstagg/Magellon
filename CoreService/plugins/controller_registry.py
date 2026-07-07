"""Discovery + operator-state routes for the plugins router.

Covers the uniform read surface (list / capabilities / manifest / info
/ health / schemas / status / replicas / updates) and the H1 operator
state (enable / disable / per-category default impl). Lookup logic
lives in :mod:`plugins.registry_service`.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from core.plugin_liveness_registry import get_registry as get_liveness_registry
from core.plugin_state import get_state_store
from magellon_sdk.models import Condition, PluginManifest

from plugins.registry_service import (
    _category_contract_for_plugin,
    _category_for_plugin,
    _live_entry,
    _live_schema_for_plugin,
    _strip_category_prefix,
    build_capabilities_response,
)
from plugins.schemas import (
    PluginSummary,
    _CapabilitiesResponse,
    _SetDefaultRequest,
)

registry_router = APIRouter()


@registry_router.get(
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
    return build_capabilities_response()


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@registry_router.get("/", summary="List all registered plugins")
async def list_plugins() -> List[PluginSummary]:
    """List every plugin the liveness registry has seen.

    Post-PI-6 the join across liveness, operator state, and catalog
    lives in :class:`PluginManagerService`. This route delegates; the
    wire shape stays aligned because
    :class:`services.plugin_manager.PluginView` and
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


@registry_router.get(
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


@registry_router.get(
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


@registry_router.get(
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


@registry_router.get(
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


@registry_router.get("/{plugin_id:path}/manifest", summary="Plugin capability manifest")
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


@registry_router.get("/{plugin_id:path}/info", summary="Plugin metadata")
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


@registry_router.get("/{plugin_id:path}/health", summary="Plugin liveness probe")
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


@registry_router.get("/{plugin_id:path}/schema/input", summary="Plugin input JSON schema")
async def plugin_input_schema(plugin_id: str):
    """Return the plugin's own JSON schema when it announced one
    (PE2-UI, 2026-05-12); otherwise fall back to the category
    contract's input model.

    The plugin-announced schema is the source of truth for the runner
    page form — it carries the rich UI hints (sliders, file pickers,
    accordion groups) the plugin author wrote. The category contract
    is the "minimum every backend in this category supports" floor,
    used when no live plugin is announcing or when an older plugin
    predates PE2.

    The plugin does NOT have to be live for the fallback to fire:
    schema is per-category, so ``_category_contract_for_plugin``
    matches the DB catalog (``manifest_plugin_id`` or ``oid``) so a
    stopped plugin's form still renders on the detail page.
    """
    live_schema = _live_schema_for_plugin(plugin_id, kind="input")
    if live_schema is not None:
        return live_schema
    contract = _category_contract_for_plugin(plugin_id)
    if contract is None or contract.input_model is None:
        raise HTTPException(status_code=404, detail=f"No input schema for {plugin_id}")
    return contract.input_model.model_json_schema()


@registry_router.get("/{plugin_id:path}/schema/output", summary="Plugin output JSON schema")
async def plugin_output_schema(plugin_id: str):
    live_schema = _live_schema_for_plugin(plugin_id, kind="output")
    if live_schema is not None:
        return live_schema
    contract = _category_contract_for_plugin(plugin_id)
    if contract is None or contract.output_model is None:
        raise HTTPException(status_code=404, detail=f"No output schema for {plugin_id}")
    return contract.output_model.model_json_schema()


# ---------------------------------------------------------------------------
# Operator state: enable/disable, default-impl selector (H1)
# ---------------------------------------------------------------------------

@registry_router.post("/{plugin_id:path}/enable", summary="Enable dispatch to a plugin")
async def enable_plugin(plugin_id: str) -> Dict[str, Any]:
    """Allow the dispatcher to route tasks to this plugin.

    Does not start the plugin — it's expected to be announcing already.
    No-op if already enabled. Enables are cheap and idempotent so the
    UI can fire blindly on toggle flip.
    """
    short_id = _strip_category_prefix(plugin_id)
    get_state_store().set_enabled(short_id, True)
    return {"plugin_id": short_id, "enabled": True}


@registry_router.post("/{plugin_id:path}/disable", summary="Disable dispatch to a plugin")
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


@registry_router.get("/categories/defaults", summary="Per-category default impl map")
async def list_category_defaults() -> Dict[str, Any]:
    """Return current per-category default-impl selections.

    UI uses this to render "Default" badges. Key is lowercase category
    name; value is the plugin_id CoreService will route to when the
    dispatch is category-scoped (no explicit plugin_id in the URL).
    """
    snapshot = get_state_store().snapshot()
    return {"defaults": snapshot["default_impl"]}


@registry_router.post(
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
