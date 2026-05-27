"""Export-page particle extraction + 2D classification orchestration.

The export UI starts here after particle picking has already produced
ImageMetaData(type=5) rows. The controller turns one saved picking run into
a stack-maker batch manifest, dispatches stack-maker, waits for the
particle_stack artifact, then dispatches CAN classification against it.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from config import ORIGINAL_IMAGES_SUB_URL, app_settings
from core.sqlalchemy_row_level_security import check_session_access
from database import get_db, session_local
from dependencies.auth import get_current_user_id
from models.sqlalchemy_models import Artifact, Image, ImageJob, ImageMetaData, Msession
from plugins.controller import JobSubmitRequest, _find_broker_plugin, _submit_broker_job
from services.job_manager import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    job_manager,
)

logger = logging.getLogger(__name__)

particle_export_pipeline_router = APIRouter()

_ORCHESTRATOR_PLUGIN_ID = "particle-export-pipeline"
_PICKING_METADATA_TYPE = 5
_TERMINAL_CHILD_STATUSES = {"completed", "failed", "cancelled"}
_JOB_STATUS_LABELS = {
    STATUS_QUEUED: "queued",
    STATUS_RUNNING: "running",
    STATUS_COMPLETED: "completed",
    STATUS_FAILED: "failed",
    STATUS_CANCELLED: "cancelled",
}


class PickingRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    image_count: int
    particle_count: int
    class_counts: Dict[str, int] = Field(default_factory=dict)
    sample_image_name: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ParticleExportPipelineStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_name: str
    picking_run_name: str
    output_directory: Optional[str] = None
    include_classes: List[str] = Field(default_factory=lambda: ["1"])
    box_size: int = Field(default=256, ge=16, le=2048)
    edge_width: int = Field(default=2, ge=0, le=128)
    apix: Optional[float] = Field(default=None, gt=0)
    num_classes: int = Field(default=50, ge=2, le=500)
    num_presentations: int = Field(default=50000, ge=1000)
    align_iters: int = Field(default=2, ge=1)
    threads: int = Field(default=4, ge=1, le=64)
    can_threads: int = Field(default=4, ge=1, le=64)
    compute_backend: Literal["cpu", "torch-auto", "torch-cuda", "torch-mps", "torch-cpu"] = "torch-auto"
    max_particles: Optional[int] = Field(default=None, ge=1)
    invert: bool = False
    write_aligned_stack: bool = False


class ParticleExportPipelineStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    job_id: str
    status: str


def _safe_segment(value: str, fallback: str = "run") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return cleaned[:120] or fallback


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _pick_class(raw: Dict[str, Any]) -> str:
    value = raw.get("class")
    if value is None:
        value = raw.get("class_number")
    if value is None:
        return "1"
    return str(value)


def _finite_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _normalise_pick(raw: Dict[str, Any], include_classes: set[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    pick_class = _pick_class(raw)
    if include_classes and pick_class not in include_classes:
        return None

    center = raw.get("center")
    if isinstance(center, (list, tuple)) and len(center) >= 2:
        x = _finite_float(center[0])
        y = _finite_float(center[1])
    else:
        x = _finite_float(raw.get("x", raw.get("x_coordinate")))
        y = _finite_float(raw.get("y", raw.get("y_coordinate")))
    if x is None or y is None:
        return None

    score = _finite_float(raw.get("score"))
    if score is None:
        score = _finite_float(raw.get("confidence"))
    if score is None:
        score = 1.0

    out: Dict[str, Any] = {
        "center": [x, y],
        "x": x,
        "y": y,
        "score": score,
        "class": pick_class,
    }
    radius = _finite_float(raw.get("radius"))
    if radius is not None and radius > 0:
        out["radius"] = radius
    return out


def _normalise_picks(value: Any, include_classes: set[str]) -> List[Dict[str, Any]]:
    payload = _json_value(value)
    if isinstance(payload, dict):
        if isinstance(payload.get("particles"), list):
            payload = payload["particles"]
        elif isinstance(payload.get("picks"), list):
            payload = payload["picks"]
    if not isinstance(payload, list):
        return []
    picks: List[Dict[str, Any]] = []
    for item in payload:
        pick = _normalise_pick(item, include_classes)
        if pick is not None:
            picks.append(pick)
    return picks


def _class_counts(value: Any) -> Dict[str, int]:
    payload = _json_value(value)
    if isinstance(payload, dict):
        payload = payload.get("particles") or payload.get("picks") or []
    if not isinstance(payload, list):
        return {}
    counts: Dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        key = _pick_class(item)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _session_or_404(db: Session, session_name: str, user_id: UUID, action: str) -> Msession:
    session = (
        db.query(Msession)
        .filter(Msession.name == session_name, Msession.GCRecord.is_(None))
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not check_session_access(user_id, session.oid, action=action):
        raise HTTPException(status_code=403, detail="Access denied to this session")
    return session


def _picking_rows(db: Session, session_oid: UUID, picking_run_name: str | None = None):
    query = (
        db.query(ImageMetaData, Image)
        .join(Image, ImageMetaData.image_id == Image.oid)
        .filter(
            Image.session_id == session_oid,
            Image.GCRecord.is_(None),
            ImageMetaData.type == _PICKING_METADATA_TYPE,
            ImageMetaData.GCRecord.is_(None),
        )
    )
    if picking_run_name is not None:
        query = query.filter(ImageMetaData.name == picking_run_name)
    return query.all()


def _resolve_mrc_path(session_name: str, image: Image) -> str:
    """Resolve the source micrograph path using the picker controller convention."""
    if image.path:
        path = str(image.path)
        if os.path.isabs(path) and os.path.exists(path):
            return os.path.abspath(path)

    image_name = image.name or ""
    stripped = image_name
    for ext in (".mrc", ".mrcs", ".tif", ".tiff"):
        if stripped.lower().endswith(ext):
            stripped = stripped[: -len(ext)]
            break

    session_variants = [session_name]
    lower_session = session_name.lower()
    if lower_session != session_name:
        session_variants.append(lower_session)

    for candidate_session in session_variants:
        base = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{candidate_session}/{ORIGINAL_IMAGES_SUB_URL}"
        for candidate in (
            f"{base}{image_name}",
            f"{base}{stripped}.mrc",
            f"{base}{stripped}.mrcs",
        ):
            if os.path.exists(candidate):
                return os.path.abspath(candidate)

    base = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{lower_session}/{ORIGINAL_IMAGES_SUB_URL}"
    return f"{base}{stripped}.mrc"


def _default_output_root(session_name: str, picking_run_name: str) -> str:
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    return os.path.join(
        app_settings.directory_settings.MAGELLON_HOME_DIR,
        session_name.lower(),
        "export_pipeline",
        f"{_safe_segment(picking_run_name)}_{stamp}",
    )


def _write_manifest(
    db: Session,
    *,
    session: Msession,
    session_name: str,
    picking_run_name: str,
    output_root: str,
    include_classes: set[str],
) -> Dict[str, Any]:
    rows = _picking_rows(db, session.oid, picking_run_name)
    if not rows:
        raise RuntimeError(f"No particle-picking rows found for run {picking_run_name!r}")

    picks_dir = os.path.join(output_root, "picks")
    os.makedirs(picks_dir, exist_ok=True)

    items: List[Dict[str, str]] = []
    total_particles = 0
    image_ids: List[str] = []
    for metadata, image in rows:
        picks = _normalise_picks(metadata.data_json, include_classes)
        if not picks:
            continue

        image_name = image.name or str(image.oid)
        picks_path = os.path.join(picks_dir, f"{_safe_segment(image_name)}.json")
        with open(picks_path, "w", encoding="utf-8") as handle:
            json.dump(picks, handle, indent=2)

        micrograph_path = _resolve_mrc_path(session_name, image)
        items.append(
            {
                "micrograph_path": micrograph_path,
                "particles_path": picks_path,
                "micrograph_name": image_name,
            }
        )
        total_particles += len(picks)
        image_ids.append(str(image.oid))

    if not items:
        raise RuntimeError(
            "The selected picking run has no particles matching the selected classes"
        )

    manifest = {
        "session_name": session_name,
        "session_id": str(session.oid),
        "picking_run_name": picking_run_name,
        "include_classes": sorted(include_classes),
        "particle_count": total_particles,
        "items": items,
    }
    manifest_path = os.path.join(output_root, "stack_maker_batch_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return {
        "manifest_path": manifest_path,
        "items": items,
        "particle_count": total_particles,
        "image_count": len(items),
        "image_ids": image_ids,
    }


def _initial_stages() -> List[Dict[str, Any]]:
    return [
        {"key": "prepare", "label": "Prepare picks", "status": "queued", "progress": 0},
        {"key": "extract", "label": "Extract particle stack", "status": "queued", "progress": 0},
        {"key": "classify", "label": "2D classification", "status": "queued", "progress": 0},
        {"key": "finalize", "label": "Finalize outputs", "status": "queued", "progress": 0},
    ]


def _set_stage(
    stages: List[Dict[str, Any]],
    key: str,
    *,
    status: str,
    progress: Optional[int] = None,
    detail: Optional[str] = None,
) -> None:
    for stage in stages:
        if stage["key"] != key:
            continue
        stage["status"] = status
        if progress is not None:
            stage["progress"] = progress
        if detail is not None:
            stage["detail"] = detail
        return


def _set_child(
    child_jobs: List[Dict[str, Any]],
    key: str,
    **values: Any,
) -> None:
    for child in child_jobs:
        if child.get("key") == key:
            child.update({k: v for k, v in values.items() if v is not None})
            return
    child_jobs.append({"key": key, **{k: v for k, v in values.items() if v is not None}})


def _notify_progress(job_id: str, event: str, **extra: Any) -> None:
    try:
        from core.socketio_server import schedule_import_progress

        schedule_import_progress(str(job_id), {"job_id": str(job_id), "event": event, **extra})
    except Exception:
        logger.debug("Could not emit export pipeline progress", exc_info=True)


def _update_pipeline_state(
    job_id: str,
    *,
    progress: int,
    stage_key: str,
    stages: List[Dict[str, Any]],
    child_jobs: List[Dict[str, Any]],
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    with session_local() as db:
        job = db.query(ImageJob).filter(ImageJob.oid == uuid.UUID(str(job_id))).first()
        if not job:
            return
        processed = dict(job.processed_json or {})
        processed.update(
            {
                "progress": progress,
                "stage_key": stage_key,
                "stages": stages,
                "child_jobs": child_jobs,
            }
        )
        if result is not None:
            processed["result"] = result
        if error is not None:
            processed["error"] = error
        job.processed_json = processed
        db.commit()
    _notify_progress(job_id, "progress", progress=progress, stage_key=stage_key)


async def _wait_for_child_job(
    pipeline_job_id: str,
    child_job_id: str,
    *,
    child_key: str,
    stages: List[Dict[str, Any]],
    child_jobs: List[Dict[str, Any]],
    stage_key: str,
    timeout_seconds: int,
    base_progress: int,
    end_progress: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_snapshot: Optional[tuple[str, int]] = None
    while True:
        envelope = job_manager.get_job(str(child_job_id), include_result=True)
        status = str(envelope.get("status") or "unknown")
        child_progress = int(envelope.get("progress") or 0)
        snapshot = (status, child_progress)
        if snapshot != last_snapshot:
            _set_child(
                child_jobs,
                child_key,
                job_id=child_job_id,
                status=status,
                progress=child_progress,
            )
            if status not in _TERMINAL_CHILD_STATUSES:
                stage_progress = max(5, min(95, child_progress))
                overall = base_progress + int(
                    ((end_progress - base_progress) * stage_progress) / 100
                )
                _set_stage(stages, stage_key, status="running", progress=stage_progress)
            else:
                overall = base_progress
            _update_pipeline_state(
                pipeline_job_id,
                progress=overall,
                stage_key=stage_key,
                stages=stages,
                child_jobs=child_jobs,
            )
            last_snapshot = snapshot

        if status == "completed":
            _set_child(child_jobs, child_key, status=status)
            _set_stage(stages, stage_key, status="completed", progress=100)
            _update_pipeline_state(
                pipeline_job_id,
                progress=end_progress,
                stage_key=stage_key,
                stages=stages,
                child_jobs=child_jobs,
            )
            return
        if status in _TERMINAL_CHILD_STATUSES:
            raise RuntimeError(f"{child_key} job {child_job_id} {status}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"Timed out waiting for {child_key} job {child_job_id}")
        await asyncio.sleep(5)


def _artifact_by_id(db: Session, artifact_id: str) -> Optional[Artifact]:
    try:
        oid = uuid.UUID(str(artifact_id))
    except ValueError:
        return None
    return (
        db.query(Artifact)
        .filter(Artifact.oid == oid, Artifact.deleted_at.is_(None))
        .first()
    )


async def _wait_for_artifact(
    *,
    producing_job_id: str,
    kind: str,
    cached_artifact_id: Optional[str] = None,
    source_artifact_id: Optional[str] = None,
    timeout_seconds: int = 60,
) -> Artifact:
    deadline = time.monotonic() + timeout_seconds
    while True:
        with session_local() as db:
            artifact = _artifact_by_id(db, cached_artifact_id) if cached_artifact_id else None
            if artifact is None:
                query = (
                    db.query(Artifact)
                    .filter(
                        Artifact.producing_job_id == uuid.UUID(str(producing_job_id)),
                        Artifact.kind == kind,
                        Artifact.deleted_at.is_(None),
                    )
                    .order_by(Artifact.created_date.desc())
                )
                if source_artifact_id:
                    query = query.filter(Artifact.source_artifact_id == uuid.UUID(str(source_artifact_id)))
                artifact = query.first()
            if artifact is not None:
                db.expunge(artifact)
                return artifact
        if time.monotonic() > deadline:
            raise RuntimeError(f"No {kind} artifact found for job {producing_job_id}")
        await asyncio.sleep(2)


async def _dispatch_stack_maker(
    *,
    manifest_info: Dict[str, Any],
    output_root: str,
    request: ParticleExportPipelineStartRequest,
    session: Msession,
    user_id: str,
) -> Dict[str, Any]:
    contract = _find_broker_plugin("stack-maker")
    if contract is None:
        raise RuntimeError("stack-maker plugin is not live")

    extraction_dir = os.path.join(output_root, "extraction")
    os.makedirs(extraction_dir, exist_ok=True)
    first_item = manifest_info["items"][0]
    payload = {
        "image_id": manifest_info["image_ids"][0] if manifest_info["image_ids"] else None,
        "image_name": first_item.get("micrograph_name"),
        "image_path": first_item["micrograph_path"],
        "micrograph_path": first_item["micrograph_path"],
        "particles_path": first_item["particles_path"],
        "box_size": request.box_size,
        "edge_width": request.edge_width,
        "apix": request.apix,
        "output_dir": extraction_dir,
        "engine_opts": {
            "batch_manifest_path": manifest_info["manifest_path"],
            "output_stem": f"{_safe_segment(request.session_name)}_{_safe_segment(request.picking_run_name)}_particles",
            "allow_partial": True,
        },
    }
    return await _submit_broker_job(
        "stack-maker",
        contract,
        JobSubmitRequest(
            input=payload,
            name=f"Extract particles: {request.session_name} / {request.picking_run_name}",
            image_id=manifest_info["image_ids"][0] if manifest_info["image_ids"] else None,
            user_id=user_id,
            msession_id=str(session.oid),
            target_backend="stack-maker",
        ),
    )


async def _dispatch_can_classifier(
    *,
    stack_artifact: Artifact,
    output_root: str,
    request: ParticleExportPipelineStartRequest,
    session: Msession,
    user_id: str,
) -> Dict[str, Any]:
    contract = _find_broker_plugin("can-classifier")
    if contract is None:
        raise RuntimeError("can-classifier plugin is not live")

    classification_dir = os.path.join(output_root, "class2d")
    os.makedirs(classification_dir, exist_ok=True)
    payload = {
        "particle_stack_id": str(stack_artifact.oid),
        "mrcs_path": stack_artifact.mrcs_path,
        "star_path": stack_artifact.star_path,
        "output_dir": classification_dir,
        "apix": request.apix if request.apix is not None else stack_artifact.apix,
        "num_classes": request.num_classes,
        "num_presentations": request.num_presentations,
        "align_iters": request.align_iters,
        "threads": request.threads,
        "can_threads": request.can_threads,
        "compute_backend": request.compute_backend,
        "max_particles": request.max_particles,
        "invert": request.invert,
        "write_aligned_stack": request.write_aligned_stack,
        "engine_opts": {},
    }
    return await _submit_broker_job(
        "can-classifier",
        contract,
        JobSubmitRequest(
            input=payload,
            name=f"2D classification: {request.session_name} / {request.picking_run_name}",
            user_id=user_id,
            msession_id=str(session.oid),
            target_backend="can-classifier",
        ),
    )


async def _run_pipeline(job_id: str, request_data: Dict[str, Any], user_id: str) -> None:
    request = ParticleExportPipelineStartRequest.model_validate(request_data)
    stages = _initial_stages()
    child_jobs: List[Dict[str, Any]] = []
    output_root = request.output_directory or _default_output_root(
        request.session_name,
        request.picking_run_name,
    )

    try:
        job_manager.mark_running(job_id, progress=1)
        _set_stage(stages, "prepare", status="running", progress=10)
        _update_pipeline_state(
            job_id,
            progress=5,
            stage_key="prepare",
            stages=stages,
            child_jobs=child_jobs,
        )

        with session_local() as db:
            session = (
                db.query(Msession)
                .filter(Msession.name == request.session_name, Msession.GCRecord.is_(None))
                .first()
            )
            if not session:
                raise RuntimeError("Session not found")
            manifest_info = _write_manifest(
                db,
                session=session,
                session_name=request.session_name,
                picking_run_name=request.picking_run_name,
                output_root=output_root,
                include_classes=set(request.include_classes or []),
            )
            db.expunge(session)

        _set_stage(
            stages,
            "prepare",
            status="completed",
            progress=100,
            detail=(
                f"{manifest_info['particle_count']} particles from "
                f"{manifest_info['image_count']} micrographs"
            ),
        )
        _update_pipeline_state(
            job_id,
            progress=15,
            stage_key="extract",
            stages=stages,
            child_jobs=child_jobs,
        )

        _set_stage(stages, "extract", status="running", progress=5)
        extraction = await _dispatch_stack_maker(
            manifest_info=manifest_info,
            output_root=output_root,
            request=request,
            session=session,
            user_id=user_id,
        )
        extraction_job_id = extraction["job_id"]
        _set_child(
            child_jobs,
            "extraction",
            label="Stack Maker",
            plugin_id="stack-maker",
            job_id=extraction_job_id,
            status=extraction.get("status", "queued"),
        )
        _update_pipeline_state(
            job_id,
            progress=25,
            stage_key="extract",
            stages=stages,
            child_jobs=child_jobs,
        )
        await _wait_for_child_job(
            job_id,
            extraction_job_id,
            child_key="extraction",
            stages=stages,
            child_jobs=child_jobs,
            stage_key="extract",
            timeout_seconds=3600,
            base_progress=35,
            end_progress=55,
        )
        stack_artifact = await _wait_for_artifact(
            producing_job_id=extraction_job_id,
            kind="particle_stack",
            cached_artifact_id=extraction.get("cached_artifact_id"),
        )
        _set_child(child_jobs, "extraction", artifact_id=str(stack_artifact.oid))
        _set_stage(
            stages,
            "extract",
            status="completed",
            progress=100,
            detail=f"{stack_artifact.particle_count or manifest_info['particle_count']} boxed particles",
        )

        _set_stage(stages, "classify", status="running", progress=5)
        _update_pipeline_state(
            job_id,
            progress=60,
            stage_key="classify",
            stages=stages,
            child_jobs=child_jobs,
        )
        classification = await _dispatch_can_classifier(
            stack_artifact=stack_artifact,
            output_root=output_root,
            request=request,
            session=session,
            user_id=user_id,
        )
        classification_job_id = classification["job_id"]
        _set_child(
            child_jobs,
            "classification",
            label="CAN Classifier",
            plugin_id="can-classifier",
            job_id=classification_job_id,
            status=classification.get("status", "queued"),
        )
        _update_pipeline_state(
            job_id,
            progress=70,
            stage_key="classify",
            stages=stages,
            child_jobs=child_jobs,
        )
        await _wait_for_child_job(
            job_id,
            classification_job_id,
            child_key="classification",
            stages=stages,
            child_jobs=child_jobs,
            stage_key="classify",
            timeout_seconds=7200,
            base_progress=80,
            end_progress=92,
        )
        class_artifact = await _wait_for_artifact(
            producing_job_id=classification_job_id,
            kind="class_averages",
            cached_artifact_id=classification.get("cached_artifact_id"),
            source_artifact_id=str(stack_artifact.oid),
        )
        _set_child(child_jobs, "classification", artifact_id=str(class_artifact.oid))

        _set_stage(stages, "finalize", status="running", progress=50)
        result = {
            "output_root": output_root,
            "manifest_path": manifest_info["manifest_path"],
            "particle_stack_artifact_id": str(stack_artifact.oid),
            "particle_stack_job_id": extraction_job_id,
            "particle_count": stack_artifact.particle_count or manifest_info["particle_count"],
            "mrcs_path": stack_artifact.mrcs_path,
            "star_path": stack_artifact.star_path,
            "class_averages_artifact_id": str(class_artifact.oid),
            "classification_job_id": classification_job_id,
            "class_averages_path": class_artifact.mrcs_path,
            "classification": class_artifact.data_json or {},
        }
        _set_stage(stages, "finalize", status="completed", progress=100)
        _update_pipeline_state(
            job_id,
            progress=99,
            stage_key="finalize",
            stages=stages,
            child_jobs=child_jobs,
            result=result,
        )
        job_manager.complete_job(job_id, result=result, num_items=manifest_info["particle_count"])
        _notify_progress(job_id, "completed", progress=100)
    except Exception as exc:  # noqa: BLE001 - background job must settle its row
        logger.exception("Particle export pipeline job %s failed", job_id)
        active_key = "finalize"
        for stage in stages:
            if stage.get("status") == "running":
                active_key = str(stage.get("key") or active_key)
                _set_stage(stages, active_key, status="failed", detail=str(exc))
                break
        failed_progress = {
            "prepare": 5,
            "extract": 55,
            "classify": 92,
            "finalize": 99,
        }.get(active_key, 0)
        _update_pipeline_state(
            job_id,
            progress=failed_progress,
            stage_key=active_key,
            stages=stages,
            child_jobs=child_jobs,
            error=str(exc),
        )
        job_manager.fail_job(job_id, error=str(exc))
        _notify_progress(job_id, "failed", message=str(exc))


def _run_pipeline_thread(job_id: str, request_data: Dict[str, Any], user_id: str) -> None:
    asyncio.run(_run_pipeline(job_id, request_data, user_id))


@particle_export_pipeline_router.get("/particle-pipeline/picking-runs", response_model=List[PickingRunSummary])
def list_particle_picking_runs(
    session_name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    session = _session_or_404(db, session_name, user_id, "read")
    grouped: Dict[str, Dict[str, Any]] = {}
    for metadata, image in _picking_rows(db, session.oid):
        if not metadata.name:
            continue
        bucket = grouped.setdefault(
            metadata.name,
            {
                "name": metadata.name,
                "image_count": 0,
                "particle_count": 0,
                "class_counts": {},
                "sample_image_name": image.name,
                "created_at": metadata.created_date,
                "updated_at": metadata.last_modified_date or metadata.created_date,
            },
        )
        bucket["image_count"] += 1
        counts = _class_counts(metadata.data_json)
        row_total = sum(counts.values())
        if row_total == 0:
            row_total = len(_normalise_picks(metadata.data_json, set()))
        bucket["particle_count"] += row_total
        for key, value in counts.items():
            bucket["class_counts"][key] = bucket["class_counts"].get(key, 0) + value
        if metadata.created_date and (
            bucket["created_at"] is None or metadata.created_date < bucket["created_at"]
        ):
            bucket["created_at"] = metadata.created_date
        updated = metadata.last_modified_date or metadata.created_date
        if updated and (bucket["updated_at"] is None or updated > bucket["updated_at"]):
            bucket["updated_at"] = updated

    summaries = []
    for row in grouped.values():
        summaries.append(
            PickingRunSummary(
                name=row["name"],
                image_count=row["image_count"],
                particle_count=row["particle_count"],
                class_counts=row["class_counts"],
                sample_image_name=row["sample_image_name"],
                created_at=row["created_at"].isoformat() if row["created_at"] else None,
                updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
            )
        )
    summaries.sort(key=lambda item: (item.updated_at or "", item.name), reverse=True)
    return summaries


@particle_export_pipeline_router.post("/particle-pipeline/start", response_model=ParticleExportPipelineStartResponse)
def start_particle_export_pipeline(
    request: ParticleExportPipelineStartRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    session = _session_or_404(db, request.session_name, user_id, "read")
    if not _picking_rows(db, session.oid, request.picking_run_name):
        raise HTTPException(status_code=404, detail="Selected particle-picking run was not found")

    output_root = request.output_directory or _default_output_root(
        request.session_name,
        request.picking_run_name,
    )
    settings = request.model_dump(mode="json")
    settings["output_directory"] = output_root
    envelope = job_manager.create_job(
        plugin_id=_ORCHESTRATOR_PLUGIN_ID,
        name=f"Particle export: {request.session_name} / {request.picking_run_name}",
        settings=settings,
        user_id=str(user_id),
        msession_id=str(session.oid),
    )
    background_tasks.add_task(
        _run_pipeline_thread,
        envelope["job_id"],
        settings,
        str(user_id),
    )
    return ParticleExportPipelineStartResponse(
        message="Particle extraction and 2D classification scheduled",
        job_id=envelope["job_id"],
        status="scheduled",
    )


@particle_export_pipeline_router.get("/particle-pipeline/jobs/active")
def get_active_particle_export_pipeline_job(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    job = (
        db.query(ImageJob)
        .filter(
            ImageJob.plugin_id == _ORCHESTRATOR_PLUGIN_ID,
            ImageJob.status_id.in_([STATUS_QUEUED, STATUS_RUNNING]),
        )
        .order_by(ImageJob.created_date.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No active particle export pipeline job")
    return {
        "job_id": str(job.oid),
        "name": job.name,
        "status": _JOB_STATUS_LABELS.get(job.status_id or 0, "unknown"),
        "created_at": job.created_date.isoformat() if job.created_date else None,
    }


@particle_export_pipeline_router.get("/particle-pipeline/jobs/{job_id}/summary")
def get_particle_export_pipeline_summary(
    job_id: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    try:
        oid = uuid.UUID(str(job_id))
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid job_id")

    job = db.query(ImageJob).filter(ImageJob.oid == oid).first()
    if not job or job.plugin_id != _ORCHESTRATOR_PLUGIN_ID:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.msession_id:
        try:
            session_oid = UUID(str(job.msession_id))
        except ValueError:
            session_oid = None
        if session_oid and not check_session_access(user_id, session_oid, action="read"):
            raise HTTPException(status_code=403, detail="Access denied to this job")

    processed = job.processed_json or {}
    status = _JOB_STATUS_LABELS.get(job.status_id or 0, "unknown")
    return {
        "job_id": str(job.oid),
        "name": job.name,
        "status": status,
        "derived_status": status,
        "progress": int(processed.get("progress") or 0),
        "stage_key": processed.get("stage_key"),
        "stages": processed.get("stages") or _initial_stages(),
        "child_jobs": processed.get("child_jobs") or [],
        "settings": job.settings or {},
        "result": processed.get("result"),
        "error": processed.get("error"),
        "created_at": job.created_date.isoformat() if job.created_date else None,
        "started_at": job.start_date.isoformat() if job.start_date else None,
        "ended_at": job.end_date.isoformat() if job.end_date else None,
    }
