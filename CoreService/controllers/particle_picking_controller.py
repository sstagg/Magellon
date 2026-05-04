"""Particle-picking HTTP surface (PI-4 created; PI-5 cut over).

Lifted from the deleted ``plugins.pp.controller`` module. Same
handler bodies, same TTL cache, same DB writes — re-rooted at
``/particle-picking/*`` with all imports flipped to
``services.particle_picking.*``.

The /info / /health / /requirements metadata routes are kept for
back-compat with the React form schema; their bodies no longer
need a ``PluginBase`` instance — they read from module-level
constants instead.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import math
import os
import uuid
from datetime import datetime
from uuid import UUID

import numpy as np
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from config import ORIGINAL_IMAGES_SUB_URL, app_settings
from core.sqlalchemy_row_level_security import check_session_access
from database import get_db
from dependencies.auth import get_current_user_id
from models.sqlalchemy_models import Image, ImageMetaData, Msession, Plugin
from services.particle_picking.algorithm import (
    _extract_particles_from_map,
    _merge_particles,
    _remove_border_particles,
    pick_particles,
)
from services.particle_picking.compute import (
    _bin_image,
    _lowpass_gaussian,
    _read_mrc,
    _rescale_template,
    pick_in_image,
    preprocess_templates,
    run_template_picker,
)
from services.particle_picking.models import (
    BatchItemResult,
    BatchPickRequest,
    BatchPickResult,
    ParticlePick,
    PreviewResult,
    RetuneRequest,
    RetuneResult,
    TemplatePickerInput,
    TemplatePickerOutput,
)
from services.job_manager import job_manager

logger = logging.getLogger(__name__)

particle_picking_router = APIRouter()

# Preview cache: 10-minute TTL, capped at 50 entries so concurrent
# users don't balloon memory. Abandoned previews self-evict.
_PREVIEW_TTL_SECONDS = 600
_PREVIEW_MAX_ENTRIES = 50
_previews: TTLCache[str, dict] = TTLCache(maxsize=_PREVIEW_MAX_ENTRIES, ttl=_PREVIEW_TTL_SECONDS)

# Stable plugin_id used by JobManager rows.
_PLUGIN_ID = "particle-picking/template-picker"


# ---------------------------------------------------------------------------
# Synchronous pick
# ---------------------------------------------------------------------------


@particle_picking_router.post(
    "/",
    response_model=TemplatePickerOutput,
    summary="Run template-based particle picking (synchronous)",
)
async def template_pick(input_data: TemplatePickerInput) -> TemplatePickerOutput:
    try:
        return run_template_picker(input_data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Template picker failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Preview / retune flow
# ---------------------------------------------------------------------------


@particle_picking_router.post(
    "/preview",
    response_model=PreviewResult,
    summary="Compute correlation maps and return initial picks + score map",
)
async def template_pick_preview(input_data: TemplatePickerInput):
    """Phase 1: run the expensive FFT correlation once, cache score maps."""
    try:
        image = _read_mrc(input_data.image_path)
        binned = _bin_image(image, input_data.bin_factor)
        target_apix = input_data.image_pixel_size * input_data.bin_factor
        filtered_image = _lowpass_gaussian(binned, target_apix, input_data.lowpass_resolution)

        processed_templates = []
        for path in input_data.template_paths:
            tmpl = _read_mrc(path)
            if input_data.invert_templates:
                tmpl = -1.0 * tmpl
            scaled = _rescale_template(tmpl, input_data.template_pixel_size, target_apix)
            filtered = _lowpass_gaussian(scaled, target_apix, input_data.lowpass_resolution)
            processed_templates.append(filtered.astype(np.float32))

        if input_data.angle_ranges is not None:
            if len(input_data.angle_ranges) == 1 and len(processed_templates) > 1:
                ar = input_data.angle_ranges[0]
                angle_ranges = [(ar.start, ar.end, ar.step)] * len(processed_templates)
            elif len(input_data.angle_ranges) == len(processed_templates):
                angle_ranges = [(ar.start, ar.end, ar.step) for ar in input_data.angle_ranges]
            else:
                raise ValueError("angle_ranges must have 1 entry or one per template")
        else:
            angle_ranges = [(0.0, 360.0, 10.0)] * len(processed_templates)

        result = pick_particles(
            image=filtered_image,
            templates=processed_templates,
            params={
                "diameter_angstrom": input_data.diameter_angstrom,
                "pixel_size_angstrom": target_apix,
                "bin": 1.0,
                "threshold": input_data.threshold,
                "max_threshold": input_data.max_threshold,
                "max_peaks": input_data.max_peaks,
                "overlap_multiplier": input_data.overlap_multiplier,
                "max_blob_size_multiplier": input_data.max_blob_size_multiplier,
                "min_blob_roundness": input_data.min_blob_roundness,
                "peak_position": input_data.peak_position,
                "angle_ranges": angle_ranges,
            },
        )

        preview_id = str(uuid.uuid4())
        radius_pixels = input_data.diameter_angstrom / target_apix / 2.0
        _previews[preview_id] = {
            "template_results": result["template_results"],
            "image_shape": filtered_image.shape,
            "radius_pixels": radius_pixels,
            "created_at": datetime.now(),
        }

        merged_map = result["merged_score_map"]
        score_min = float(np.min(merged_map))
        score_max = float(np.max(merged_map))
        score_map_b64 = _score_map_to_base64_png(merged_map)

        particles = [ParticlePick(**p) for p in result["particles"]]

        return PreviewResult(
            preview_id=preview_id,
            particles=particles,
            num_particles=len(particles),
            num_templates=len(processed_templates),
            target_pixel_size=target_apix,
            image_binning=input_data.bin_factor,
            image_shape=[int(filtered_image.shape[0]), int(filtered_image.shape[1])],
            score_map_png_base64=score_map_b64,
            score_range=[score_min, score_max],
        )

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Preview failed")
        raise HTTPException(status_code=500, detail=str(exc))


@particle_picking_router.post(
    "/preview/{preview_id}/retune",
    response_model=RetuneResult,
    summary="Re-extract particles with new tunable params (no recompute)",
)
async def template_pick_retune(preview_id: str, params: RetuneRequest):
    """Phase 2: re-threshold the cached score maps with new params. Instant."""
    preview = _previews.get(preview_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Preview not found or expired")

    radius_pixels = preview["radius_pixels"]
    image_shape = preview["image_shape"]

    all_particles = []
    for item in preview["template_results"]:
        particles = _extract_particles_from_map(
            score_map=item["score_map"],
            angle_map=item["angle_map"],
            template_index=int(item["template_index"]),
            threshold=params.threshold,
            radius_pixels=radius_pixels,
            max_peaks=params.max_peaks,
            overlap_multiplier=params.overlap_multiplier,
            max_blob_size_multiplier=params.max_blob_size_multiplier,
            min_blob_roundness=params.min_blob_roundness,
            peak_position=params.peak_position,
        )
        particles = _remove_border_particles(
            particles=particles,
            diameter_pixels=radius_pixels * 2.0,
            image_width=image_shape[1],
            image_height=image_shape[0],
        )
        all_particles.extend(particles)

    merged = _merge_particles(
        particles=all_particles,
        radius_pixels=radius_pixels,
        overlap_multiplier=params.overlap_multiplier,
        max_peaks=params.max_peaks,
        max_threshold=params.max_threshold,
    )

    picks = [ParticlePick(**p) for p in merged]
    return RetuneResult(particles=picks, num_particles=len(picks))


@particle_picking_router.delete(
    "/preview/{preview_id}",
    summary="Discard a preview and free memory",
)
async def template_pick_preview_delete(preview_id: str):
    if _previews.pop(preview_id, None) is not None:
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Preview not found")


# ---------------------------------------------------------------------------
# Async job flow
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
    from core.socketio_server import emit_job_update, emit_log
    from plugins.progress import JobCancelledError, JobReporter

    loop = asyncio.get_running_loop()
    reporter = JobReporter(job_id=job_id, sid=sid, plugin_label='picking', loop=loop)

    try:
        running = job_manager.mark_running(job_id, progress=0)
        await emit_job_update(sid, running)
        await emit_log('info', 'picking', f"Particle picking started: {input_data.image_path}")

        result = await loop.run_in_executor(
            None, lambda: run_template_picker(input_data, reporter=reporter)
        )

        completed = job_manager.complete_job(
            job_id,
            result=result.model_dump(),
            num_items=result.num_particles,
        )
        await emit_job_update(sid, completed)
        await emit_log('info', 'picking',
                        f"Particle picking completed — {result.num_particles} particles found")
    except JobCancelledError:
        cancelled = job_manager.cancel_job(job_id)
        await emit_job_update(sid, cancelled)
        await emit_log('info', 'picking', f"Particle picking cancelled (job {job_id})")
    except Exception as exc:
        failed = job_manager.fail_job(job_id, error=str(exc))
        await emit_job_update(sid, failed)
        await emit_log('error', 'picking', f"Particle picking failed: {exc}")
        logger.exception("Async particle picking failed: %s", exc)


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------


@particle_picking_router.get("/jobs", summary="List particle-picking jobs")
async def list_jobs():
    return job_manager.list_jobs(plugin_id=_PLUGIN_ID)


@particle_picking_router.get("/jobs/{job_id}", summary="Get particle-picking job details")
async def get_job(job_id: str):
    try:
        return job_manager.get_job(job_id)
    except (LookupError, ValueError):
        # ValueError: job_manager validates id as UUID and raises on
        # malformed strings — surface as 404 rather than 500.
        raise HTTPException(status_code=404, detail="Job not found")


# ---------------------------------------------------------------------------
# Metadata — module-level constants now (no PluginBase shell to ask)
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
    """Probe optional libs whose presence determines whether the
    feature works. Same shape (list of dicts with result/condition/
    message) as the legacy PluginBase output so the React form
    doesn't have to special-case."""
    results = []
    for name, install_hint in (
        ("mrcfile", "pip install mrcfile"),
        ("scipy", "pip install scipy"),
        ("PIL", "pip install pillow"),
    ):
        try:
            __import__(name)
            results.append({
                "result": "success",
                "condition": name,
                "message": f"{name} is available",
            })
        except ImportError:
            results.append({
                "result": "failure",
                "condition": name,
                "message": f"{name} is not installed",
                "instructions": install_hint,
            })
    return results


@particle_picking_router.get("/schema/input", summary="Particle-picking input JSON schema")
async def template_pick_input_schema():
    return TemplatePickerInput.model_json_schema()


@particle_picking_router.get("/schema/output", summary="Particle-picking output JSON schema")
async def template_pick_output_schema():
    return TemplatePickerOutput.model_json_schema()


# ---------------------------------------------------------------------------
# Session image listing — drives the "Run Batch" dialog
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
# Run-on-image with persistence
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
    target_apix = picker.image_pixel_size * picker.bin_factor

    loop = asyncio.get_event_loop()
    processed_templates, angle_ranges = await loop.run_in_executor(
        None, preprocess_templates, picker, target_apix,
    )
    raw_particles, img_shape = await loop.run_in_executor(
        None,
        pick_in_image,
        mrc_path, processed_templates, angle_ranges, picker, target_apix,
    )

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

    row = await loop.run_in_executor(
        None, _save_particle_picking, db, image_oid, req.ipp_name, points,
    )

    return RunAndSaveResponse(
        ipp_oid=str(row.oid),
        ipp_name=row.name,
        image_oid=str(image_oid),
        num_particles=len(points),
        image_shape=list(img_shape),
    )


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
_PP_PLUGIN_NAME = "pp"


def _get_pp_plugin_oid(db: Session) -> UUID:
    """Return the Plugin.oid for the 'pp' plugin row, creating if needed.

    ``ImageMetaData.plugin_id`` is a FK to ``Plugin.oid`` (UUID). We
    keep one Plugin row with name='pp' to satisfy the FK and tag every
    particle-picking record with it. Name kept as 'pp' for back-compat
    with already-saved rows.
    """
    global _PP_PLUGIN_OID
    if _PP_PLUGIN_OID is not None:
        return _PP_PLUGIN_OID

    existing = (
        db.query(Plugin)
        .filter(Plugin.name == _PP_PLUGIN_NAME, Plugin.GCRecord.is_(None))
        .first()
    )
    if existing:
        _PP_PLUGIN_OID = existing.oid
        return _PP_PLUGIN_OID

    row = Plugin(
        oid=uuid.uuid4(),
        name=_PP_PLUGIN_NAME,
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
    from core.socketio_server import emit_job_update, emit_log

    try:
        running = job_manager.mark_running(job_id, progress=1)
        await emit_job_update(sid, running)
        await emit_log('info', 'batch-picking', f"Batch started: {len(req.images)} images")

        loop = asyncio.get_event_loop()

        picker = req.picker_params
        target_apix = picker.image_pixel_size * picker.bin_factor
        processed_templates, angle_ranges = await loop.run_in_executor(
            None, preprocess_templates, picker, target_apix,
        )
        await emit_log('info', 'batch-picking', f"Preprocessed {len(processed_templates)} template(s)")

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
                    raw_particles, img_shape = await loop.run_in_executor(
                        None,
                        pick_in_image,
                        mrc_path, processed_templates, angle_ranges, picker, target_apix,
                    )

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

                    await loop.run_in_executor(
                        None, _save_particle_picking, db, image_oid, req.ipp_name, points,
                    )

                    items.append(BatchItemResult(
                        image_oid=entry.oid,
                        image_name=entry.name,
                        num_particles=len(points),
                        image_shape=list(img_shape),
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
# COCO export
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
# Helpers
# ---------------------------------------------------------------------------


def _score_map_to_base64_png(score_map: np.ndarray) -> str:
    """Convert a 2D float score map to a base64-encoded PNG."""
    from PIL import Image as PILImage

    data = score_map.astype(np.float32)
    finite = np.isfinite(data)
    if finite.any():
        lo = float(np.percentile(data[finite], 1.0))
        hi = float(np.percentile(data[finite], 99.0))
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo:
        hi = lo + 1e-6

    clipped = np.clip(data, lo, hi)
    normalized = ((clipped - lo) / (hi - lo) * 255).astype(np.uint8)

    img = PILImage.fromarray(normalized, mode="L")
    max_dim = 1024
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), PILImage.BILINEAR)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


__all__ = ["particle_picking_router"]
