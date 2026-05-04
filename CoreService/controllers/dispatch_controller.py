"""Generic dispatch surface — one URL pattern per category × capability (PT-6).

After PT-3..PT-5 every category that pins a default plugin advertising
``Capability.SYNC`` or ``Capability.PREVIEW`` gets these endpoints
for free::

  POST   /dispatch/{category}/run                       — Capability.SYNC
  POST   /dispatch/{category}/preview                   — Capability.PREVIEW
  POST   /dispatch/{category}/preview/{id}/retune       — Capability.PREVIEW
  DELETE /dispatch/{category}/preview/{id}              — Capability.PREVIEW

Each handler is a thin wrapper around
:func:`services.sync_dispatcher.dispatch_capability` — validate the
body against the category's ``input_model``, route via the operator-
pinned default plugin's ``http_endpoint``, return the plugin's
response verbatim.

This is the generic shape ``controllers/particle_picking_controller``
ended up wrapping. Particle-picking keeps its feature-named URLs
(``/particle-picking/...``) for back-compat with the React UI; new
categories adopting SYNC/PREVIEW get the generic shape automatically.

Why static routes (vs dynamic per-category registration)? FastAPI
plays well with parameterized paths. Registering one endpoint with a
``{category}`` path param + runtime validation is simpler than
walking ``CATEGORIES`` at startup and registering N routes. The
trade-off is OpenAPI sees a single route per verb instead of one per
category — operators/tools that read the spec see fewer paths but
can call any category they know about.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

from magellon_sdk.categories.contract import CATEGORIES, CategoryContract
from magellon_sdk.models.manifest import Capability
from services.sync_dispatcher import (
    BackendNotLive,
    CapabilityMissing,
    PluginCallFailed,
    dispatch_capability,
    forget_preview_route,
    lookup_preview_route,
)

logger = logging.getLogger(__name__)

dispatch_router = APIRouter()


def _normalize_name(name: str) -> str:
    """Lowercase + collapse spaces/hyphens to underscores so URL
    callers can use any of ``particle_picking``, ``particle-picking``,
    or the display form ``particle picking`` interchangeably."""
    return name.lower().replace("-", "_").replace(" ", "_")


def _resolve_category(name: str) -> CategoryContract:
    lookup = _normalize_name(name)
    for contract in CATEGORIES.values():
        if _normalize_name(contract.category.name) == lookup:
            return contract
    raise HTTPException(
        status_code=404,
        detail=f"Unknown category {name!r}. Known: "
               f"{sorted(_normalize_name(c.category.name) for c in CATEGORIES.values())}",
    )


def _validate_input(contract: CategoryContract, body: Dict[str, Any]) -> None:
    """Validate the body against the category's input_model. Raises
    422 on invalid input rather than letting Pydantic 500 us.

    Note: the plugin's SDK router (``make_sync_router`` /
    ``make_preview_router``) re-validates against the same model
    on its side via the patched ``__annotations__`` body parser.
    The double validation is intentional — CoreService validates
    early so a bad body never traverses the network; the plugin's
    router validates so a misbehaving caller (curl, a different
    CoreService) can't bypass our check. Don't "fix" the duplication.
    """
    if contract.input_model is None:
        return
    try:
        contract.input_model.model_validate(body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid input: {exc}")


def _http_from_dispatch_error(exc: Exception) -> HTTPException:
    """Same mapping the particle-picking controller uses."""
    if isinstance(exc, BackendNotLive):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, CapabilityMissing):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, PluginCallFailed):
        return HTTPException(status_code=exc.status_code, detail=exc.detail)
    return HTTPException(status_code=500, detail=str(exc))


# Per-verb timeouts. Interactive retune is sub-100ms typical; cap at
# 5s so a hung plugin surfaces fast. Preview is the cold-start
# computation (load image, FFT correlation) — needs more headroom.
# Run/sync is the full job; keep the dispatcher's general default.
_TIMEOUT_RETUNE_S = 5.0
_TIMEOUT_PREVIEW_S = 30.0
_TIMEOUT_RUN_S = 60.0


async def _dispatch_off_thread(
    category: str,
    capability: Capability,
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    target_backend: Optional[str] = None,
    instance_id: Optional[str] = None,
    timeout_seconds: float = _TIMEOUT_RUN_S,
) -> Dict[str, Any]:
    """sync_dispatcher uses blocking httpx; run in the executor so we
    don't stall the event loop on a slow plugin."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                category, capability, method, path,
                body=body, target_backend=target_backend,
                instance_id=instance_id,
                timeout_seconds=timeout_seconds,
            ),
        )
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)


# ---------------------------------------------------------------------------
# SYNC capability — POST /dispatch/{category}/run
# ---------------------------------------------------------------------------


@dispatch_router.post(
    "/{category}/run",
    summary="Synchronous dispatch — calls the default plugin's /execute",
)
async def dispatch_run(
    category: str,
    body: Dict[str, Any] = Body(...),
    target_backend: Optional[str] = None,
):
    contract = _resolve_category(category)
    _validate_input(contract, body)
    return await _dispatch_off_thread(
        _normalize_name(contract.category.name), Capability.SYNC,
        "POST", "/execute", body=body, target_backend=target_backend,
    )


# ---------------------------------------------------------------------------
# PREVIEW capability — three endpoints
# ---------------------------------------------------------------------------


@dispatch_router.post(
    "/{category}/preview",
    summary="Compute correlation maps and return initial preview payload",
)
async def dispatch_preview(
    category: str,
    body: Dict[str, Any] = Body(...),
    target_backend: Optional[str] = None,
):
    contract = _resolve_category(category)
    _validate_input(contract, body)
    return await _dispatch_off_thread(
        _normalize_name(contract.category.name), Capability.PREVIEW,
        "POST", "/preview", body=body, target_backend=target_backend,
        timeout_seconds=_TIMEOUT_PREVIEW_S,
    )


@dispatch_router.post(
    "/{category}/preview/{preview_id}/retune",
    summary="Re-extract with new tunable params (no recompute)",
)
async def dispatch_retune(
    category: str,
    preview_id: str,
    body: Dict[str, Any] = Body(...),
    target_backend: Optional[str] = None,
):
    contract = _resolve_category(category)
    # Sticky preview routing: pin to the replica that owns the
    # cached score maps. Without this, multi-replica deployments
    # see retune slider ticks land on a different replica → 404
    # (preview_id doesn't exist there).
    pinned_instance = lookup_preview_route(preview_id)
    return await _dispatch_off_thread(
        _normalize_name(contract.category.name), Capability.PREVIEW,
        "POST", f"/preview/{preview_id}/retune",
        body=body, target_backend=target_backend,
        instance_id=pinned_instance,
        timeout_seconds=_TIMEOUT_RETUNE_S,
    )


@dispatch_router.delete(
    "/{category}/preview/{preview_id}",
    summary="Discard a preview and free memory",
)
async def dispatch_preview_delete(
    category: str,
    preview_id: str,
    target_backend: Optional[str] = None,
):
    contract = _resolve_category(category)
    pinned_instance = lookup_preview_route(preview_id)
    try:
        result = await _dispatch_off_thread(
            _normalize_name(contract.category.name), Capability.PREVIEW,
            "DELETE", f"/preview/{preview_id}",
            target_backend=target_backend,
            instance_id=pinned_instance,
            timeout_seconds=_TIMEOUT_RETUNE_S,
        )
    finally:
        # Clear the mapping regardless of plugin success — stale
        # entries waste memory and can leak preview_id collisions
        # if a future plugin reuses the same id.
        forget_preview_route(preview_id)
    return result


# ---------------------------------------------------------------------------
# Capability introspection
# ---------------------------------------------------------------------------


@dispatch_router.get(
    "/capabilities",
    summary="Per-category live capability map",
)
async def list_dispatch_capabilities():
    """For each known category, list the capabilities its
    operator-pinned default plugin currently advertises plus whether
    the plugin announced an ``http_endpoint`` (sync calls won't reach
    it without one).

    Used by the React UI to decide which controls to render: show
    the preview slider only when the default plugin advertises
    ``Capability.PREVIEW`` AND has an ``http_endpoint``; hide the
    sync run button when neither ``Capability.SYNC`` nor a bus
    consumer is reachable.
    """
    from core.plugin_liveness_registry import get_registry as get_liveness_registry
    from core.plugin_state import get_state_store

    state = get_state_store()
    live_by_category: Dict[str, list] = {}
    for entry in get_liveness_registry().list_live():
        cat = _normalize_name(entry.category or "")
        live_by_category.setdefault(cat, []).append(entry)

    out = []
    for contract in CATEGORIES.values():
        cat_key = _normalize_name(contract.category.name)
        default_id = state.get_default(cat_key)
        live = live_by_category.get(cat_key, [])

        # Pick the operator-pinned default if it's live; otherwise the
        # first live candidate. Same priority sync_dispatcher uses.
        chosen = None
        if default_id:
            for entry in live:
                if entry.plugin_id == default_id:
                    chosen = entry
                    break
        if chosen is None and live:
            chosen = live[0]

        capabilities: list = []
        http_endpoint = None
        plugin_id = None
        enabled = True
        if chosen is not None:
            plugin_id = chosen.plugin_id
            http_endpoint = chosen.http_endpoint
            enabled = state.is_enabled(chosen.plugin_id)
            if chosen.manifest is not None:
                capabilities = [
                    c.value for c in (chosen.manifest.capabilities or [])
                ]

        # supports_sync / supports_preview report what the React UI
        # can actually call — capability advertised + http_endpoint
        # set + plugin enabled. Disabled plugins silently fail the
        # 503 check at dispatch time, so the UI must hide controls.
        out.append({
            "category": cat_key,
            "category_display_name": contract.category.name,
            "default_plugin_id": default_id,
            "live_plugin_id": plugin_id,
            "live_plugin_count": len(live),
            "capabilities": capabilities,
            "http_endpoint": http_endpoint,
            "enabled": enabled,
            "supports_sync": (
                Capability.SYNC.value in capabilities
                and bool(http_endpoint)
                and enabled
            ),
            "supports_preview": (
                Capability.PREVIEW.value in capabilities
                and bool(http_endpoint)
                and enabled
            ),
        })
    return {"categories": out}


__all__ = ["dispatch_router"]
