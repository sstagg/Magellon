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
    422 on invalid input rather than letting Pydantic 500 us."""
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


async def _dispatch_off_thread(
    category: str,
    capability: Capability,
    method: str,
    path: str,
    *,
    body: Optional[Dict[str, Any]] = None,
    target_backend: Optional[str] = None,
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
    return await _dispatch_off_thread(
        _normalize_name(contract.category.name), Capability.PREVIEW,
        "POST", f"/preview/{preview_id}/retune",
        body=body, target_backend=target_backend,
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
    return await _dispatch_off_thread(
        _normalize_name(contract.category.name), Capability.PREVIEW,
        "DELETE", f"/preview/{preview_id}",
        target_backend=target_backend,
    )


__all__ = ["dispatch_router"]
