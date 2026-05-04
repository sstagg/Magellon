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
import logging
import math
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from config import ORIGINAL_IMAGES_SUB_URL, app_settings
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
# Translation: React's TemplatePickerInput → SDK's CryoEmImageInput shape
# ---------------------------------------------------------------------------


def _engine_opts_from_input(req: TemplatePickerInput) -> Dict[str, Any]:
    """Pack the React-side TemplatePickerInput fields into ``engine_opts``
    keys the plugin reads. Unset fields are omitted so the plugin's own
    defaults apply."""
    opts: Dict[str, Any] = {
        "templates": list(req.template_paths),
        "diameter_angstrom": req.diameter_angstrom,
        "pixel_size_angstrom": req.image_pixel_size,
        "template_pixel_size_angstrom": req.template_pixel_size,
        "threshold": req.threshold,
        "max_peaks": req.max_peaks,
        "overlap_multiplier": req.overlap_multiplier,
        "max_blob_size_multiplier": req.max_blob_size_multiplier,
        "min_blob_roundness": req.min_blob_roundness,
        "peak_position": req.peak_position,
        "bin": req.bin_factor,
        "invert_templates": req.invert_templates,
    }
    if req.max_threshold is not None:
        opts["max_threshold"] = req.max_threshold
    if req.lowpass_resolution is not None:
        opts["lowpass_resolution"] = req.lowpass_resolution
    if req.angle_ranges is not None:
        opts["angle_ranges"] = [
            {"start": ar.start, "end": ar.end, "step": ar.step}
            for ar in req.angle_ranges
        ]
    if req.output_dir:
        opts["output_dir"] = req.output_dir
    return opts


def _plugin_payload(req: TemplatePickerInput) -> Dict[str, Any]:
    """Build the full POST body for the plugin's SYNC /execute and
    PREVIEW /preview endpoints — both accept ``CryoEmImageInput``."""
    return {
        "image_path": req.image_path,
        "engine_opts": _engine_opts_from_input(req),
    }


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
# ---------------------------------------------------------------------------


@particle_picking_router.post(
    "/preview",
    response_model=PreviewResult,
    summary="Compute correlation maps and return initial picks + score map",
)
async def template_pick_preview(input_data: TemplatePickerInput) -> PreviewResult:
    try:
        loop = asyncio.get_running_loop()
        body = await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                _CATEGORY, Capability.PREVIEW, "POST", "/preview",
                body=_plugin_payload(input_data),
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
    preview_id: str, params: RetuneRequest,
) -> RetuneResult:
    try:
        loop = asyncio.get_running_loop()
        body = await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                _CATEGORY, Capability.PREVIEW, "POST",
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
async def template_pick_preview_delete(preview_id: str):
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: dispatch_capability(
                _CATEGORY, Capability.PREVIEW, "DELETE",
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


@particle_picking_router.get("/schema/input", summary="Particle-picking input JSON schema")
async def template_pick_input_schema():
    return TemplatePickerInput.model_json_schema()


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
    if not mrc_path:
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

    loop = asyncio.get_running_loop()
    row = await loop.run_in_executor(
        None, _save_particle_picking, db, image_oid, req.ipp_name, points,
    )

    return RunAndSaveResponse(
        ipp_oid=str(row.oid),
        ipp_name=row.name,
        image_oid=str(image_oid),
        num_particles=len(points),
        image_shape=body.get("image_shape"),
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


def _resolve_mrc_path(session_name: str, image_name: str) -> str | None:
    base = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{ORIGINAL_IMAGES_SUB_URL}"
    stripped = image_name
    for ext in ('.mrc', '.mrcs', '.tif', '.tiff'):
        if stripped.lower().endswith(ext):
            stripped = stripped[: -len(ext)]
            break
    for candidate in (f"{base}{image_name}", f"{base}{stripped}.mrc", f"{base}{stripped}.mrcs"):
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None


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
) -> ImageMetaData:
    """Upsert the ImageMetaData row (type=5) that stores picked particles."""
    plugin_oid = _get_pp_plugin_oid(db)
    existing = (
        db.query(ImageMetaData)
        .filter(ImageMetaData.image_id == image_oid, ImageMetaData.name == ipp_name)
        .first()
    )
    if existing:
        existing.data_json = particles_payload
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
                if not mrc_path:
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

                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        None, _save_particle_picking, db, image_oid, req.ipp_name, points,
                    )

                    items.append(BatchItemResult(
                        image_oid=entry.oid,
                        image_name=entry.name,
                        num_particles=len(points),
                        image_shape=body.get("image_shape"),
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


__all__ = ["particle_picking_router"]
