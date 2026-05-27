"""Particle-picking HTTP surface — thin facade over the plugin (PT-5).

Pre-PT-5 this controller carried 600+ lines of compute logic — the
FFT correlation algorithm + the TTLCache + every per-image
preprocessing step. Post-PT-5 the algorithm and cache live in the
plugin (the external ``magellon_template_picker_plugin``); this
controller is a thin proxy that:

  1. Translates the React UI's ``TemplatePickerInput`` shape into
     the SDK's category-input shape (``CryoEmImageInput``).
  2. Calls ``dispatch_capability(...)`` to route to the plugin's
     SYNC or PREVIEW endpoints over HTTP.
  3. Maps the plugin's response back into the wire shapes the
     React UI already expects (so the UI doesn't change).
  4. Owns the DB-side concerns (run-and-save persists picks via
     ``ImageMetaData``; batch orchestration loops over a session;
     COCO export reads the saved record).

Compute lives entirely in the plugin. Swapping the picker
(template-matching → topaz → custom CNN) is now a plugin-side
change: register a new plugin, declare ``Capability.SYNC`` /
``Capability.PREVIEW``, set it as the per-category default. This
controller doesn't move.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from config import ORIGINAL_IMAGES_SUB_URL, app_settings
from core.helper import dispatch_particle_pick_task
from core.plugin_liveness_registry import get_registry as get_liveness_registry
from core.sqlalchemy_row_level_security import check_session_access
from database import get_db
from dependencies.auth import get_current_user_id
from magellon_sdk.models.manifest import Capability
from models.sqlalchemy_models import Image, ImageMetaData, Msession, Plugin
from services.job_manager import job_manager
from services.particle_picking.models import (
    BatchItemResult,
    BatchPickRequest,
    BatchPickResult,
    PreviewResult,
    RetuneRequest,
    RetuneResult,
    TemplatePickerInput,
    TemplatePickerOutput,
)
from services.sync_dispatcher import (
    BackendNotLive,
    CapabilityMissing,
    PluginCallFailed,
    dispatch_capability,
)

logger = logging.getLogger(__name__)

particle_picking_router = APIRouter()


# Stable plugin_id used by JobManager rows.
_PLUGIN_ID = "particle-picking/template-picker"

# Category the dispatcher routes to. The operator-pinned default
# under this category receives every sync call.
_CATEGORY = "particle_picking"


# ---------------------------------------------------------------------------
# Wire shape — plugin owns TemplatePickerInput as its real input model
# (PE2-UI, 2026-05-12). The facade now passes the validated body straight
# through; CoreService and the plugin agree on the JSON shape via the
# plugin's announced /schema/input. CoreService keeps its own copy of
# the TemplatePickerInput class as a server-side fallback validator (so
# /particle-picking/preview still 422s on bad input even if the plugin
# isn't live).
# ---------------------------------------------------------------------------


def _plugin_payload(req: TemplatePickerInput) -> Dict[str, Any]:
    """Build the POST body for the plugin's SYNC /execute and PREVIEW
    /preview endpoints — both validate against ``TemplatePickerInput``
    now that the plugin owns its input shape."""
    return req.model_dump(mode="json")


def _http_from_dispatch_error(exc: Exception) -> HTTPException:
    """Map sync_dispatcher errors to HTTP statuses for this controller."""
    if isinstance(exc, BackendNotLive):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, CapabilityMissing):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, PluginCallFailed):
        return HTTPException(status_code=exc.status_code, detail=exc.detail)
    return HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Synchronous pick (sync /execute)
# ---------------------------------------------------------------------------


@particle_picking_router.post(
    "/",
    response_model=TemplatePickerOutput,
    summary="Run template-based particle picking (synchronous)",
)
async def template_pick(input_data: TemplatePickerInput) -> TemplatePickerOutput:
    """Single-image pick. Routes to the operator-pinned default
    plugin's ``POST /execute`` (SYNC capability).
    """
    try:
        body = await _run_plugin_execute(input_data)
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)
    return _output_from_plugin(body, input_data)


async def _run_plugin_execute(req: TemplatePickerInput) -> Dict[str, Any]:
    """Off-thread dispatch — sync_dispatcher uses blocking httpx.
    Run in the executor so we don't block the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: dispatch_capability(
            _CATEGORY, Capability.SYNC, "POST", "/execute",
            body=_plugin_payload(req),
        ),
    )


def _output_from_plugin(
    body: Dict[str, Any], req: TemplatePickerInput,
) -> TemplatePickerOutput:
    """Map the plugin's ``ParticlePickingOutput`` JSON onto the
    legacy ``TemplatePickerOutput`` shape the React UI expects."""
    target_apix = req.image_pixel_size * req.bin_factor
    return TemplatePickerOutput(
        particles=[],  # plugin doesn't inline picks (rule 1)
        num_particles=int(body.get("num_particles", 0)),
        num_templates=len(req.template_paths),
        target_pixel_size=target_apix,
        image_binning=req.bin_factor,
        image_shape=body.get("image_shape"),
        particles_csv_path=body.get("particles_csv_path"),
        particles_json_path=body.get("particles_json_path"),
        summary=body.get("summary"),
    )


# ---------------------------------------------------------------------------
# Preview / retune flow (PREVIEW capability)
#
# Backend-aware: the picker the operator selected in the React panel
# decides which category dispatch_capability routes to. Topaz lives
# under its own ``topaz_particle_picking`` category and is pinned by
# backend_id; template-picker uses the ``particle_picking`` default.
# ---------------------------------------------------------------------------


def _resolve_pp_category(backend: Optional[str]) -> str:
    """Map a UI backend id to the dispatch category.

    Topaz lives under its own ``topaz_particle_picking`` category;
    everything else uses ``particle_picking``. The category alone
    disambiguates the target plugin — no backend-id pin needed (and
    pinning is fragile: the announced backend_id is the SDK-derived
    ``topaz-particle-picking``, not the manifest's ``topaz``)."""
    if backend and "topaz" in backend.lower():
        return "topaz_particle_picking"
    return _CATEGORY


class PreviewRequest(BaseModel):
    """Backend-agnostic preview body. Template-picker params or Topaz
    engine knobs ride as extras; the controller routes by ``backend``
    and reshapes the payload for the target plugin."""
    model_config = ConfigDict(extra="allow")

    backend: Optional[str] = None
    image_path: str
    session_name: Optional[str] = None


def _resolve_preview_image_path(session_name: Optional[str], image_path: str) -> str:
    """Resolve UI image names to raw MRC paths, preserving explicit paths."""
    if not session_name:
        return image_path
    normalized = image_path.replace("\\", "/")
    if os.path.isabs(image_path) or normalized.startswith("/gpfs/"):
        return image_path
    return _resolve_mrc_path(session_name, image_path)


def _preview_payload(req: PreviewRequest, is_topaz: bool) -> Dict[str, Any]:
    """Reshape a PreviewRequest into the body the target plugin expects."""
    raw = req.model_dump()
    extras = {k: v for k, v in raw.items()
              if k not in ("backend", "image_path", "session_name")}
    image_path = _resolve_preview_image_path(req.session_name, req.image_path)
    if is_topaz:
        # TopazPickInput shape: input_file + nested engine_opts. Resolve
        # the MRC path server-side from the image name + session so the
        # frontend doesn't need the filesystem layout.
        return {"input_file": image_path, "image_path": image_path, "engine_opts": extras}
    # template-picker: re-validate against the strict input model so a
    # bad body still 422s even though this endpoint's signature is loose.
    tp = TemplatePickerInput.model_validate({"image_path": image_path, **extras})
    return _plugin_payload(tp)


@particle_picking_router.post(
    "/preview",
    response_model=PreviewResult,
    summary="Compute correlation maps and return initial picks + score map",
)
async def template_pick_preview(req: PreviewRequest) -> PreviewResult:
    category = _resolve_pp_category(req.backend)
    is_topaz = category == "topaz_particle_picking"
    try:
        payload = _preview_payload(req, is_topaz=is_topaz)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    try:
        loop = asyncio.get_running_loop()
        body = await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                category, Capability.PREVIEW, "POST", "/preview",
                body=payload,
            ),
        )
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)
    return PreviewResult.model_validate(body)


@particle_picking_router.post(
    "/preview/{preview_id}/retune",
    response_model=RetuneResult,
    summary="Re-extract particles with new tunable params (no recompute)",
)
async def template_pick_retune(
    preview_id: str, params: RetuneRequest, backend: Optional[str] = None,
) -> RetuneResult:
    category = _resolve_pp_category(backend)
    try:
        loop = asyncio.get_running_loop()
        body = await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                category, Capability.PREVIEW, "POST",
                f"/preview/{preview_id}/retune",
                body=params.model_dump(),
            ),
        )
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)
    return RetuneResult.model_validate(body)


@particle_picking_router.delete(
    "/preview/{preview_id}",
    summary="Discard a preview and free memory",
)
async def template_pick_preview_delete(preview_id: str, backend: Optional[str] = None):
    category = _resolve_pp_category(backend)
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                category, Capability.PREVIEW, "DELETE",
                f"/preview/{preview_id}",
            ),
        )
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Async job flow — fire-and-forget wrapper over the SYNC dispatch
# ---------------------------------------------------------------------------


@particle_picking_router.post(
    "/async",
    summary="Submit async template-picking job with Socket.IO progress",
)
async def template_pick_async(input_data: TemplatePickerInput, sid: str | None = None):
    envelope = job_manager.create_job(
        plugin_id=_PLUGIN_ID,
        name="Particle Picking",
        settings=input_data.model_dump(mode="json"),
        image_ids=None,
    )
    job_id = envelope["job_id"]
    asyncio.create_task(_run_picking_job(job_id, input_data, sid))
    return envelope


async def _run_picking_job(job_id: str, input_data: TemplatePickerInput, sid: str | None):
    """Run the pick via the plugin's sync /execute endpoint, push
    job-state transitions over Socket.IO. The plugin emits its own
    step events via the bus (PROGRESS_REPORTING capability)."""
    from core.socketio_server import emit_job_update, emit_log

    try:
        running = job_manager.mark_running(job_id, progress=0)
        await emit_job_update(sid, running)
        await emit_log('info', 'picking', f"Particle picking started: {input_data.image_path}")

        body = await _run_plugin_execute(input_data)
        result = _output_from_plugin(body, input_data)

        completed = job_manager.complete_job(
            job_id, result=result.model_dump(), num_items=result.num_particles,
        )
        await emit_job_update(sid, completed)
        await emit_log('info', 'picking',
                        f"Particle picking completed — {result.num_particles} particles found")
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        failed = job_manager.fail_job(job_id, error=str(exc))
        await emit_job_update(sid, failed)
        await emit_log('error', 'picking', f"Particle picking failed: {exc}")
    except Exception as exc:  # noqa: BLE001
        failed = job_manager.fail_job(job_id, error=str(exc))
        await emit_job_update(sid, failed)
        await emit_log('error', 'picking', f"Particle picking failed: {exc}")
        logger.exception("Async particle picking failed: %s", exc)


# ---------------------------------------------------------------------------
# Job management — feature-scoped convenience endpoints
# ---------------------------------------------------------------------------


@particle_picking_router.get("/jobs", summary="List particle-picking jobs")
async def list_jobs():
    return job_manager.list_jobs(plugin_id=_PLUGIN_ID)


@particle_picking_router.get("/jobs/{job_id}", summary="Get particle-picking job details")
async def get_job(job_id: str):
    try:
        return job_manager.get_job(job_id)
    except (LookupError, ValueError):
        raise HTTPException(status_code=404, detail="Job not found")


# ---------------------------------------------------------------------------
# Metadata — flat constants. The /capabilities endpoint and the React
# form reader use these for the picker's metadata pane.
# ---------------------------------------------------------------------------


_PICKER_INFO = {
    "name": "template-picker",
    "developer": "Magellon",
    "description": "FFT-based template matching particle picker with normalized correlation",
    "version": "1.0.0",
}


@particle_picking_router.get("/info", summary="Particle-picking metadata")
async def template_pick_info():
    return _PICKER_INFO


@particle_picking_router.get("/health", summary="Particle-picking health check")
async def template_pick_health():
    return {"status": "ok"}


@particle_picking_router.get("/requirements", summary="Particle-picking dependency check")
async def template_pick_requirements():
    """Post-PT-5 the compute lives in the plugin; CoreService doesn't
    need scipy / mrcfile / PIL anymore. Always reports OK; if the
    plugin's actual deps are missing the operator sees that on the
    plugin's own ``/health`` endpoint."""
    return [
        {"result": "success", "condition": "dispatcher",
         "message": "compute delegates to plugin via sync_dispatcher"},
    ]


@particle_picking_router.get(
    "/backends",
    summary="List live particle-picking backends with their capabilities",
)
async def list_pp_backends():
    """Return all live plugins registered under the ``particle_picking``
    category. Includes each backend's capabilities so the UI can decide
    whether to show Preview & Tune (requires Capability.PREVIEW)."""
    _PP_CATEGORIES = {
        "particle_picking",
        "particle picking",
        "topaz_particle_picking",
        "topazparticlepicking",
    }
    registry = get_liveness_registry()
    entries = [
        e for e in registry.list_live()
        if (e.category or "").lower() in _PP_CATEGORIES
    ]
    result = []
    for e in entries:
        manifest = e.manifest
        caps = list(getattr(manifest, "capabilities", None) or [])
        cap_values = [c.value if hasattr(c, "value") else str(c) for c in caps]
        label = None
        if manifest:
            info = getattr(manifest, "info", None)
            label = getattr(info, "name", None) or getattr(manifest, "name", None)
        result.append({
            "backend_id": e.backend_id or e.plugin_id,
            "plugin_id": e.plugin_id,
            "label": label or e.plugin_id,
            "capabilities": cap_values,
            "has_preview": Capability.PREVIEW in (caps or []),
            "has_sync": Capability.SYNC in (caps or []),
            "http_endpoint": e.http_endpoint,
            "status": e.status,
        })
    # De-duplicate by backend_id. Heartbeats can create a lightweight
    # stub before the richer announce entry arrives, so keep the entry
    # with the most usable HTTP/capability metadata rather than the
    # first one returned by the registry.
    def _score_backend(item: dict) -> tuple[int, int, int, int]:
        return (
            1 if item.get("http_endpoint") else 0,
            len(item.get("capabilities") or []),
            1 if item.get("has_preview") else 0,
            1 if item.get("has_sync") else 0,
        )

    by_backend: dict[str, dict] = {}
    for item in result:
        backend_id = item["backend_id"]
        if backend_id not in by_backend or _score_backend(item) > _score_backend(by_backend[backend_id]):
            by_backend[backend_id] = item
    return list(by_backend.values())


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    image_path: str
    image_id: Optional[str] = None
    session_name: Optional[str] = None
    target_backend: str = "template-picker"
    ipp_name: str = "Auto-pick"
    engine_opts: Optional[Dict[str, Any]] = None


class DispatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued: bool
    target_backend: str
    message: str
    job_id: str
    task_id: str


@particle_picking_router.post(
    "/dispatch",
    response_model=DispatchResponse,
    summary="Dispatch a particle-picking task via RMQ (fire-and-forget)",
)
async def dispatch_particle_pick(
    req: DispatchRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Enqueue a particle-picking task on the RMQ bus. Supports all
    backends (template-picker, boxnet-picker, topaz) regardless of
    whether they expose HTTP. The result is saved asynchronously by
    TaskOutputProcessor when the plugin finishes.

    When image_id + session_name are provided (DB image), the endpoint
    resolves the MRC path automatically so the frontend doesn't need
    to know the server-side filesystem layout."""
    image_id_val: Optional[UUID] = None
    resolved_path = req.image_path

    if req.image_id:
        try:
            image_id_val = UUID(req.image_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid image_id UUID")

        # Resolve actual MRC path from DB image record + session.
        if req.session_name:
            image = db.query(Image).filter(Image.oid == image_id_val).first()
            if not image:
                raise HTTPException(status_code=404, detail="Image not found")
            if image.session_id and not check_session_access(user_id, image.session_id, action="write"):
                raise HTTPException(status_code=403, detail="Access denied to this image")
            resolved_path = _resolve_mrc_path(req.session_name, image.name)

    task_id = uuid.uuid4()
    job_envelope = job_manager.create_job(
        plugin_id=req.target_backend,
        name=f"{req.target_backend} pick {os.path.basename(resolved_path)}",
        settings={
            "image_path": resolved_path,
            "target_backend": req.target_backend,
            "ipp_name": req.ipp_name,
            "engine_opts": req.engine_opts or {},
        },
        task_ids=[task_id],
        image_ids=[image_id_val] if image_id_val else None,
        user_id=str(user_id) if user_id else None,
    )
    job_id = UUID(job_envelope["job_id"])

    loop = asyncio.get_running_loop()
    ok = await loop.run_in_executor(
        None,
        lambda: dispatch_particle_pick_task(
            resolved_path,
            image_id=image_id_val,
            session_name=req.session_name,
            job_id=job_id,
            task_id=task_id,
            target_backend=req.target_backend,
            ipp_name=req.ipp_name,
            engine_opts=req.engine_opts,
        ),
    )
    if not ok:
        job_manager.fail_job(str(job_id), error="Failed to enqueue task")
        raise HTTPException(status_code=503, detail="Failed to enqueue task — RMQ unavailable")
    return DispatchResponse(
        queued=True,
        target_backend=req.target_backend,
        message=f"Task queued for {req.target_backend}",
        job_id=str(job_id),
        task_id=str(task_id),
    )


@particle_picking_router.get("/schema/input", summary="Particle-picking input JSON schema")
async def template_pick_input_schema(backend: Optional[str] = None):
    """Return the JSON schema for the named backend's input model.
    Falls back to TemplatePickerInput when no live backend is found
    or the backend has no announced schema."""
    if backend:
        registry = get_liveness_registry()
        requested = _normalize_pp_category(backend)
        for entry in registry.list_live():
            if _normalize_pp_category(entry.category or "") not in {
                "particle_picking",
                "topaz_particle_picking",
                "topazparticlepicking",
            }:
                continue
            candidates = {
                entry.backend_id or "",
                entry.plugin_id or "",
                (entry.plugin_id or "").split("/")[-1],
            }
            if any(_normalize_pp_category(c) == requested for c in candidates) and entry.input_schema:
                return entry.input_schema
    return TemplatePickerInput.model_json_schema()


def _normalize_pp_category(value: str) -> str:
    return value.replace("-", "_").replace(" ", "_").lower()


@particle_picking_router.get("/schema/output", summary="Particle-picking output JSON schema")
async def template_pick_output_schema():
    return TemplatePickerOutput.model_json_schema()


# ---------------------------------------------------------------------------
# Session image listing — DB-only, no plugin involvement
# ---------------------------------------------------------------------------


@particle_picking_router.get(
    "/session-images",
    summary="List images in a session filtered by magnification",
)
async def list_session_images(
    session_name: str,
    magnification: int | None = None,
    tolerance: int = 0,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    msession = db.query(Msession).filter(
        Msession.name == session_name,
        Msession.GCRecord.is_(None),
    ).first()
    if not msession:
        raise HTTPException(status_code=404, detail=f"Session '{session_name}' not found")
    if not check_session_access(user_id, msession.oid, action="read"):
        raise HTTPException(status_code=403, detail="Access denied to this session")

    query = db.query(Image).filter(
        Image.session_id == msession.oid,
        Image.GCRecord.is_(None),
    )
    if magnification is not None:
        if tolerance > 0:
            query = query.filter(
                Image.magnification.between(magnification - tolerance, magnification + tolerance)
            )
        else:
            query = query.filter(Image.magnification == magnification)

    rows = query.order_by(Image.name).all()
    return [
        {
            "oid": str(r.oid),
            "name": r.name,
            "magnification": int(r.magnification) if r.magnification is not None else None,
            "dimension_x": int(r.dimension_x) if r.dimension_x is not None else None,
            "dimension_y": int(r.dimension_y) if r.dimension_y is not None else None,
            "pixel_size": float(r.pixel_size) if r.pixel_size is not None else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Run-on-image with persistence — sync /execute + DB save
# ---------------------------------------------------------------------------


class RunAndSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_name: str
    image_oid: str
    ipp_name: str = Field(default="Auto-pick", description="ImageMetaData.name for the saved record")
    picker_params: TemplatePickerInput


class RunAndSaveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ipp_oid: str
    ipp_name: str
    image_oid: str
    num_particles: int
    image_shape: list[int] | None = None


@particle_picking_router.post(
    "/run-and-save",
    response_model=RunAndSaveResponse,
    summary="Run template-picking on one session image and persist the result",
)
async def template_pick_run_and_save(
    req: RunAndSaveRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    image_oid = UUID(req.image_oid)
    image = db.query(Image).filter(Image.oid == image_oid).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not image.session_id or not check_session_access(user_id, image.session_id, action="write"):
        raise HTTPException(status_code=403, detail="Access denied to this image")

    mrc_path = _resolve_mrc_path(req.session_name, image.name)
    if not os.path.exists(mrc_path):
        raise HTTPException(status_code=404, detail="MRC file not found on disk")

    picker = req.picker_params.model_copy(update={"image_path": mrc_path})

    # Plugin /execute writes the picks to disk if engine_opts.output_dir
    # is set; for run-and-save we don't need disk artifacts — just the
    # particle list to drop into ImageMetaData.data_json. Plugin's
    # particles_json_path is read after the call.
    try:
        body = await _run_plugin_execute(picker)
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)

    # Plugin returns particles_json_path; load and translate to UI shape.
    raw_particles = _load_particles_from_plugin_output(body)
    threshold = picker.threshold
    now_ts = int(datetime.now().timestamp() * 1000)
    points = [
        {
            "x": p["x"],
            "y": p["y"],
            "id": f"auto-{now_ts}-{idx}",
            "type": "auto",
            "confidence": min(float(p.get("score", 0.0)), 1.0),
            "class": "1" if p.get("score", 0.0) >= threshold else "4",
            "timestamp": now_ts,
        }
        for idx, p in enumerate(raw_particles)
    ]

    image_shape = body.get("image_shape")
    loop = asyncio.get_running_loop()
    row = await loop.run_in_executor(
        None, _save_particle_picking, db, image_oid, req.ipp_name, points, image_shape,
    )

    return RunAndSaveResponse(
        ipp_oid=str(row.oid),
        ipp_name=row.name,
        image_oid=str(image_oid),
        num_particles=len(points),
        image_shape=image_shape,
    )


def _load_particles_from_plugin_output(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The plugin writes picks to ``particles_json_path``; read them
    back. Falls back to an empty list when the path is absent (the
    plugin was called without ``output_dir`` set)."""
    import json

    path = body.get("particles_json_path")
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:  # noqa: BLE001
        logger.exception("failed to read particles_json_path=%r", path)
    return []


# ---------------------------------------------------------------------------
# Batch picking — orchestration in CoreService, compute via plugin /execute
# ---------------------------------------------------------------------------


@particle_picking_router.post(
    "/batch",
    summary="Run template-picking on a list of session images (async, Socket.IO progress)",
)
async def template_pick_batch(
    req: BatchPickRequest,
    sid: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
):
    envelope = job_manager.create_job(
        plugin_id=_PLUGIN_ID,
        name=f"Batch particle picking ({len(req.images)} images)",
        settings={
            "session_name": req.session_name,
            "num_images": len(req.images),
            "ipp_name": req.ipp_name,
            "picker_params": req.picker_params.model_dump(mode="json"),
        },
        image_ids=[e.oid for e in req.images],
        user_id=str(user_id),
    )
    job_id = envelope["job_id"]
    asyncio.create_task(_run_batch_job(job_id, req, str(user_id), sid))
    return envelope


def _resolve_mrc_path(session_name: str, image_name: str) -> str:
    """Return the MRC path for dispatch to Docker plugins.

    Prefers a locally-confirmed path (so ``os.path.abspath`` normalises
    the separator on Linux).  When the CoreService runs on Windows without
    a direct GPFS mount the local check always fails; in that case the
    canonical ``/gpfs/home/{session}/original/{image}.mrc`` path is
    returned directly — it is valid inside every Docker plugin container
    that bind-mounts the GPFS root at ``/gpfs``.
    """
    session_variants = [session_name]
    lower_session = session_name.lower()
    if lower_session != session_name:
        session_variants.append(lower_session)
    stripped = image_name
    for ext in ('.mrc', '.mrcs', '.tif', '.tiff'):
        if stripped.lower().endswith(ext):
            stripped = stripped[: -len(ext)]
            break
    for session in session_variants:
        base = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session}/{ORIGINAL_IMAGES_SUB_URL}"
        for candidate in (f"{base}{image_name}", f"{base}{stripped}.mrc", f"{base}{stripped}.mrcs"):
            if os.path.exists(candidate):
                return os.path.abspath(candidate)
    # Local file not found (Windows host without GPFS mount).
    # Build the canonical path that Docker containers can access. The
    # imported session directories are normalized to lowercase.
    base = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{lower_session}/{ORIGINAL_IMAGES_SUB_URL}"
    return f"{base}{stripped}.mrc"


_PP_PLUGIN_OID: UUID | None = None
_PP_PLUGIN_LEGACY_NAME = "pp"
# PM1's catalog rows for the picker plugin live under this slug
# (set by the install pipeline's PluginRepository.upsert_catalog).
_PP_MANIFEST_PLUGIN_ID = "template-picker"


def _get_pp_plugin_oid(db: Session) -> UUID:
    """Return the Plugin.oid that owns ImageMetaData particle-picking rows.

    Reviewer G — PM1 reconciliation. Resolution order:

      1. PM1 catalog row by ``manifest_plugin_id='template-picker'``
         (written by the install pipeline; canonical post-PM1).
      2. Legacy ``name='pp'`` sentinel row (pre-PM1; still in
         databases that haven't re-installed the picker through
         the new pipeline).
      3. Create a new sentinel row if neither exists. New rows use
         the legacy name='pp' for back-compat with already-saved
         ImageMetaData rows whose plugin_id FK points there; a
         future data migration can re-FK to the catalog row and
         drop this fallback.

    ``ImageMetaData.plugin_id`` is a FK to ``Plugin.oid`` (UUID).
    """
    global _PP_PLUGIN_OID
    if _PP_PLUGIN_OID is not None:
        return _PP_PLUGIN_OID

    # 1. PM1 catalog row (canonical).
    catalog_row = (
        db.query(Plugin)
        .filter(
            Plugin.manifest_plugin_id == _PP_MANIFEST_PLUGIN_ID,
            Plugin.GCRecord.is_(None),
        )
        .first()
    )
    if catalog_row is not None:
        _PP_PLUGIN_OID = catalog_row.oid
        return _PP_PLUGIN_OID

    # 2. Legacy sentinel row.
    legacy_row = (
        db.query(Plugin)
        .filter(
            Plugin.name == _PP_PLUGIN_LEGACY_NAME,
            Plugin.GCRecord.is_(None),
        )
        .first()
    )
    if legacy_row is not None:
        _PP_PLUGIN_OID = legacy_row.oid
        return _PP_PLUGIN_OID

    # 3. Create the legacy sentinel — keeps already-saved
    # ImageMetaData rows pointing somewhere stable. The install
    # pipeline will write the canonical catalog row separately
    # when the picker is re-installed; a follow-up migration can
    # consolidate.
    row = Plugin(
        oid=uuid.uuid4(),
        name=_PP_PLUGIN_LEGACY_NAME,
        created_date=datetime.now(),
        version="1.0",
    )
    db.add(row)
    db.commit()
    _PP_PLUGIN_OID = row.oid
    return _PP_PLUGIN_OID


def _save_particle_picking(
    db: Session,
    image_oid: UUID,
    ipp_name: str,
    particles_payload: list[dict],
    image_shape: Optional[list[int]] = None,
) -> ImageMetaData:
    """Upsert the ImageMetaData row (type=5) that stores picked particles.

    ``image_shape`` (height, width of the source micrograph) is persisted
    in the ``data`` JSON column so the React canvas can size its viewBox
    to match pick coordinates on reload, instead of inferring from the
    pick bounding box (~5% off, drops picks at the edges)."""
    plugin_oid = _get_pp_plugin_oid(db)
    meta_data: Optional[str] = (
        json.dumps({"image_shape": [int(image_shape[0]), int(image_shape[1])]})
        if image_shape and len(image_shape) == 2
        else None
    )
    existing = (
        db.query(ImageMetaData)
        .filter(ImageMetaData.image_id == image_oid, ImageMetaData.name == ipp_name)
        .first()
    )
    if existing:
        existing.data_json = particles_payload
        if meta_data is not None:
            existing.data = meta_data
        existing.plugin_id = plugin_oid
        existing.last_modified_date = datetime.now()
        db.commit()
        return existing
    row = ImageMetaData(
        oid=uuid.uuid4(),
        name=ipp_name,
        created_date=datetime.now(),
        image_id=image_oid,
        plugin_id=plugin_oid,
        type=5,
        data=meta_data,
        data_json=particles_payload,
    )
    db.add(row)
    db.commit()
    return row


async def _run_batch_job(
    job_id: str,
    req: BatchPickRequest,
    user_id: str,
    sid: str | None,
):
    """Loop over images; per-image dispatch via plugin's sync /execute.

    Templates aren't preprocessed-once-then-reused like pre-PT-5;
    the plugin handles each image independently. Per-call HTTP
    overhead is ~5ms vs ~100ms+ FFT compute, so the difference
    is negligible. A future plugin-side template cache (keyed by
    file hash) eliminates even that.
    """
    from core.socketio_server import emit_job_update, emit_log

    try:
        running = job_manager.mark_running(job_id, progress=1)
        await emit_job_update(sid, running)
        await emit_log('info', 'batch-picking', f"Batch started: {len(req.images)} images")

        items: list[BatchItemResult] = []
        total = len(req.images)
        succeeded = 0
        failed = 0

        db: Session = next(get_db())
        try:
            for i, entry in enumerate(req.images):
                if job_manager.is_cancelled(job_id):
                    await emit_log('info', 'batch-picking', f"Batch cancelled at {i}/{total}")
                    cancelled = job_manager.cancel_job(job_id)
                    await emit_job_update(sid, cancelled)
                    return
                image_oid = UUID(entry.oid)
                image = db.query(Image).filter(Image.oid == image_oid).first()
                if not image or not image.session_id:
                    items.append(BatchItemResult(
                        image_oid=entry.oid, image_name=entry.name,
                        status="skipped", error="Image not found",
                    ))
                    failed += 1
                    continue

                if not check_session_access(user_id, image.session_id, action="write"):
                    items.append(BatchItemResult(
                        image_oid=entry.oid, image_name=entry.name,
                        status="skipped", error="Access denied",
                    ))
                    failed += 1
                    continue

                mrc_path = _resolve_mrc_path(req.session_name, entry.name)
                if not os.path.exists(mrc_path):
                    items.append(BatchItemResult(
                        image_oid=entry.oid, image_name=entry.name,
                        status="skipped", error="MRC file not found on disk",
                    ))
                    failed += 1
                    continue

                try:
                    picker = req.picker_params.model_copy(update={"image_path": mrc_path})
                    body = await _run_plugin_execute(picker)
                    raw_particles = _load_particles_from_plugin_output(body)
                    threshold = picker.threshold
                    now_ts = int(datetime.now().timestamp() * 1000)
                    points = [
                        {
                            "x": p["x"],
                            "y": p["y"],
                            "id": f"auto-{now_ts}-{idx}",
                            "type": "auto",
                            "confidence": min(float(p.get("score", 0.0)), 1.0),
                            "class": "1" if p.get("score", 0.0) >= threshold else "4",
                            "timestamp": now_ts,
                        }
                        for idx, p in enumerate(raw_particles)
                    ]

                    batch_image_shape = body.get("image_shape")
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, _save_particle_picking, db, image_oid, req.ipp_name, points, batch_image_shape,
                    )

                    items.append(BatchItemResult(
                        image_oid=entry.oid,
                        image_name=entry.name,
                        num_particles=len(points),
                        image_shape=batch_image_shape,
                        status="done",
                    ))
                    succeeded += 1
                except Exception as per_image_exc:  # noqa: BLE001
                    logger.exception("Batch pick failed on image %s", entry.name)
                    items.append(BatchItemResult(
                        image_oid=entry.oid, image_name=entry.name,
                        status="error", error=str(per_image_exc),
                    ))
                    failed += 1

                progress = int(5 + 90 * (i + 1) / total)
                progressed = job_manager.update_progress(
                    job_id, progress=progress, num_items=succeeded,
                )
                await emit_job_update(sid, progressed)
                await emit_log(
                    'info', 'batch-picking',
                    f"[{i + 1}/{total}] {entry.name}: {items[-1].status}"
                    + (f" ({items[-1].num_particles} particles)" if items[-1].status == "done" else ""),
                )
        finally:
            db.close()

        result = BatchPickResult(
            total=total, succeeded=succeeded, failed=failed, items=items,
        )
        completed = job_manager.complete_job(
            job_id, result=result.model_dump(), num_items=succeeded,
        )
        await emit_job_update(sid, completed)
        await emit_log(
            'info', 'batch-picking',
            f"Batch done — {succeeded}/{total} succeeded, {failed} failed",
        )
    except Exception as exc:
        logger.exception("Batch picking job failed")
        failed_env = job_manager.fail_job(job_id, error=str(exc))
        await emit_job_update(sid, failed_env)
        await emit_log('error', 'batch-picking', f"Batch failed: {exc}")


# ---------------------------------------------------------------------------
# COCO export — DB-only
# ---------------------------------------------------------------------------


_COCO_CATEGORIES = [
    {"id": 1, "name": "Good", "supercategory": "particle"},
    {"id": 2, "name": "Edge", "supercategory": "particle"},
    {"id": 3, "name": "Contamination", "supercategory": "particle"},
    {"id": 4, "name": "Uncertain", "supercategory": "particle"},
]


@particle_picking_router.get(
    "/records/{ipp_oid}/coco",
    summary="Export a particle-picking record as a COCO annotations JSON",
)
async def template_pick_record_coco(
    ipp_oid: str,
    radius: float = 15.0,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        oid = UUID(ipp_oid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid record id")

    ipp = db.query(ImageMetaData).filter(ImageMetaData.oid == oid).first()
    if not ipp:
        raise HTTPException(status_code=404, detail="Picking record not found")

    image = db.query(Image).filter(Image.oid == ipp.image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Parent image not found")
    if image.session_id and not check_session_access(user_id, image.session_id, action="read"):
        raise HTTPException(status_code=403, detail="Access denied to this image")

    points = ipp.data_json or []
    if not isinstance(points, list):
        points = []

    width = int(image.dimension_x) if image.dimension_x is not None else 0
    height = int(image.dimension_y) if image.dimension_y is not None else 0
    r = float(radius)
    diameter = 2.0 * r
    area = math.pi * r * r

    annotations: list[dict] = []
    for idx, p in enumerate(points, start=1):
        if not isinstance(p, dict):
            continue
        cx = float(p.get("x", 0.0))
        cy = float(p.get("y", 0.0))
        cls = str(p.get("class", "1"))
        category_id = int(cls) if cls.isdigit() else 1
        ann: dict = {
            "id": idx,
            "image_id": 1,
            "category_id": category_id,
            "bbox": [cx - r, cy - r, diameter, diameter],
            "area": area,
            "segmentation": [],
            "iscrowd": 0,
            "radius": r,
        }
        score = p.get("confidence")
        if score is not None:
            ann["score"] = float(score)
        pick_type = p.get("type")
        if pick_type:
            ann["pick_type"] = pick_type
        annotations.append(ann)

    return {
        "info": {
            "description": f"Magellon particle picking record: {ipp.name}",
            "source": "magellon",
            "ipp_oid": str(ipp.oid),
            "image_oid": str(image.oid),
            "image_name": image.name,
            "date_created": datetime.now().isoformat(),
            "version": "1.0",
        },
        "licenses": [],
        "images": [
            {
                "id": 1,
                "width": width,
                "height": height,
                "file_name": image.name or "",
            }
        ],
        "categories": _COCO_CATEGORIES,
        "annotations": annotations,
    }


# ---------------------------------------------------------------------------
# SAM2 interactive click-pick proxy
#
# Routes to the SAM2 plugin's custom /click-pick endpoint via the SYNC
# capability using target_backend="sam2-particle-picker".  The encoder
# embedding is cached inside the plugin (TTL 10 min, 4 images) so only
# the first click on each micrograph is slow (~3 s CPU / ~0.3 s GPU);
# all subsequent clicks on the same image return in under 500 ms.
# ---------------------------------------------------------------------------


class Sam2ClickPoint(BaseModel):
    x: float
    y: float
    label: int = 1  # 1=foreground, 0=background


class Sam2ClickRequest(BaseModel):
    image_path: str
    session_name: Optional[str] = None  # used for path resolution when image_path is a bare name
    click_points: List[Sam2ClickPoint]
    model_variant: str = "facebook/sam2.1-hiera-tiny"
    mask_threshold: float = 0.5


class Sam2ClickResult(BaseModel):
    centroid_x: float
    centroid_y: float
    mask_polygon: List[List[float]]
    confidence: float
    radius_estimate: float
    image_shape: List[int]


_SAM2_BACKEND_ID = "sam2-particle-picker"
_SAM2_CATEGORY = "particle_picking"


@particle_picking_router.post(
    "/sam2-click",
    response_model=Sam2ClickResult,
    summary="SAM2 interactive click-to-pick (proxied to the SAM2 plugin)",
)
async def sam2_click_pick(req: Sam2ClickRequest) -> Sam2ClickResult:
    """Proxy an interactive click to the SAM2 plugin's /click-pick endpoint.

    The image embedding is cached in the plugin so the first call on a
    micrograph embeds the image (~3 s CPU); subsequent clicks on the same
    micrograph complete in under 500 ms.

    Accepts either an absolute /gpfs/... path or a bare image name with
    ``session_name`` for server-side path resolution.
    """
    resolved_path = _resolve_preview_image_path(req.session_name, req.image_path)
    body = {
        "image_path": resolved_path,
        "click_points": [p.model_dump() for p in req.click_points],
        "model_variant": req.model_variant,
        "mask_threshold": req.mask_threshold,
    }
    try:
        loop = asyncio.get_running_loop()
        response_body = await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                _SAM2_CATEGORY,
                Capability.SYNC,
                "POST",
                "/click-pick",
                body=body,
                target_backend=_SAM2_BACKEND_ID,
                timeout_seconds=30.0,
            ),
        )
    except (BackendNotLive, CapabilityMissing, PluginCallFailed) as exc:
        raise _http_from_dispatch_error(exc)
    return Sam2ClickResult.model_validate(response_body)


__all__ = ["particle_picking_router"]
