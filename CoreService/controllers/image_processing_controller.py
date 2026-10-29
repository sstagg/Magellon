import logging
import os
import shutil
import tempfile
import uuid
from typing import Dict
from uuid import UUID

import mrcfile
import numpy as np
import io
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel
from starlette.responses import FileResponse
from typing import Optional

from config import MAGELLON_HOME_DIR, app_settings
from controllers.image_processing_tools import lowpass_filter
from core.exceptions import TaskDispatchError
from models.pydantic_models import LeginonFrameTransferJobBase, LeginonFrameTransferJobDto, \
    EpuImportJobBase, EpuImportJobDto
from services.importers.EPUImporter import EPUImporter
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService
from sqlalchemy.orm import Session
from database import get_db, session_local
from services.mrc_image_service import MrcImageService
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_permission
from core.session_ownership import set_import_owner
from services import import_runners

logger = logging.getLogger(__name__)
image_processing_router = APIRouter()

mrc_service = MrcImageService()
lft_service = LeginonFrameTransferJobService()


@image_processing_router.post("/png_of_mrc_dir",
                              summary="Reads each MRC file from the input directory, converts it to a PNG image, "
                                      "and saves the resulting image to the output directory (if provided). If the "
                                      "out_dir argument is not specified, the PNG files are saved in the same "
                                      "directory as the MRC files. ")
async def png_of_mrc_dir(
    in_dir: str,
    out_dir: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Convert directory of MRC files to PNG images.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    **Warning:** Direct file path access - ensure paths are validated
    """
    logger.warning(f"User {user_id} converting MRC directory to PNG: in_dir={in_dir}, out_dir={out_dir}")
    try:
        mrc_service.convert_mrc_dir_to_png(in_dir=in_dir, out_dir=out_dir)
        logger.info(f"User {user_id} successfully converted MRC directory to PNG")
        return {"message": "MRC files successfully converted to PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to convert MRC directory: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/png_of_mrc_file",
                              summary="gets a mrc file, converts it to a PNG image, and saves the resulting image to "
                                      "the output directory (if provided). If the out_dir argument is not specified, "
                                      "the PNG files are saved in the same directory as the MRC files. ")
async def png_of_mrc_file(
    abs_file_path: str,
    out_dir: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Convert single MRC file to PNG image.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.info(f"User {user_id} converting MRC file to PNG: {abs_file_path}")
    try:
        mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
        logger.info(f"User {user_id} successfully converted MRC file to PNG")
        return {"message": "MRC file successfully converted to PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to convert MRC file: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/fft_of_mrc_dir",
                              summary="Reads each MRC file from the input directory, converts it to a fft PNG image, "
                                      "and saves the resulting image to the output directory (if provided). If the "
                                      "out_dir argument is not specified, the PNG files are saved in the same "
                                      "directory as the MRC files. ")
async def fft_of_mrc_dir(
    in_dir: str,
    out_dir: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Generate FFT for directory of MRC files.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.warning(f"User {user_id} computing FFT for MRC directory: in_dir={in_dir}, out_dir={out_dir}")
    try:
        mrc_service.compute_dir_fft(in_dir=in_dir, out_dir=out_dir)
        logger.info(f"User {user_id} successfully computed FFT for MRC directory")
        return {"message": "MRC files successfully converted to FFT PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to compute FFT for directory: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/fft_of_mrc_file",
                              summary="gets a mrc file, converts it to a fft PNG image, and saves the resulting image "
                                      "to the output directory (if provided). If the out_dir argument is not "
                                      "specified, the PNG files are saved in the same directory as the MRC files. ")
async def fft_of_mrc_file(
    abs_file_path: str,
    abs_out_file_name: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Generate FFT for single MRC file.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.info(f"User {user_id} computing FFT for MRC file: {abs_file_path}")
    try:
        mrc_service.compute_mrc_fft(mrc_abs_path=abs_file_path, abs_out_file_name=abs_out_file_name)
        logger.info(f"User {user_id} successfully computed FFT for MRC file")
        return {"message": "MRC file successfully converted to fft PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to compute FFT: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


class FftDispatchRequest(BaseModel):
    image_path: str
    target_path: Optional[str] = None
    job_id: Optional[UUID] = None
    image_id: Optional[UUID] = None


class FftDispatchResponse(BaseModel):
    job_id: UUID
    task_id: UUID
    queue_name: str
    image_path: str
    target_path: str
    status: str = "dispatched"


class FftBatchDispatchRequest(BaseModel):
    image_paths: list[str]
    job_id: Optional[UUID] = None
    name: Optional[str] = None


class FftBatchDispatchResponse(BaseModel):
    job_id: UUID
    task_ids: list[UUID]
    queue_name: str
    target_paths: list[str]
    status: str = "dispatched"


def _fft_target_for(image_path: str, override: Optional[str] = None) -> str:
    if override:
        return override
    base = os.path.splitext(os.path.basename(image_path))[0] + "_FFT.png"
    return os.path.join(os.path.dirname(image_path), base)


@image_processing_router.post(
    "/fft/dispatch",
    response_model=FftDispatchResponse,
    summary="Dispatch an FFT task to the fft plugin over RMQ. Persists "
            "the job + task via JobManager, then publishes. Returns "
            "job_id+task_id so the UI can subscribe to job:<uuid> and "
            "watch step events stream back.",
)
async def fft_dispatch(
    request: FftDispatchRequest,
    _: None = Depends(require_permission('image_processing', 'write')),
    user_id: UUID = Depends(get_current_user_id),
):
    """Single-image FFT dispatch.

    Creates a 1-task ImageJob via JobManager (so the DB has authoritative
    job state from the moment of dispatch), then publishes one TaskMessage
    onto ``fft_tasks_queue``. The step-event projector flips that row
    through running → completed/failed as envelopes flow back.

    For dispatching N images under one job, use ``/fft/batch_dispatch``.
    """
    from core.helper import dispatch_fft_task
    from services.job_manager import job_manager

    task_id = uuid.uuid4()
    target_path = _fft_target_for(request.image_path, request.target_path)

    job_envelope = job_manager.create_job(
        plugin_id="magellon_fft_plugin",
        name=f"FFT {os.path.basename(request.image_path)}",
        settings={"image_path": request.image_path, "target_path": target_path},
        task_ids=[task_id],
        user_id=str(user_id) if user_id else None,
        job_id=request.job_id,
    )
    job_id = uuid.UUID(job_envelope["job_id"])

    logger.info(
        "User %s dispatching FFT task %s in job %s for image %s",
        user_id, task_id, job_id, request.image_path,
    )
    try:
        ok = dispatch_fft_task(
            image_path=request.image_path,
            target_path=target_path,
            job_id=job_id,
            task_id=task_id,
            image_id=request.image_id,
        )
    except TaskDispatchError:
        ok = False
    if not ok:
        # DB has a QUEUED job that will never run — flip it to failed
        # so the UI doesn't see a permanently-pending row.
        job_manager.fail_job(str(job_id), error="Failed to publish FFT task to RMQ")
        raise HTTPException(status_code=502, detail="Failed to publish FFT task to RMQ")

    return FftDispatchResponse(
        job_id=job_id,
        task_id=task_id,
        queue_name="fft_tasks_queue",
        image_path=request.image_path,
        target_path=target_path,
    )


@image_processing_router.post(
    "/fft/batch_dispatch",
    response_model=FftBatchDispatchResponse,
    summary="Dispatch N FFT tasks under a single job. Persists one "
            "ImageJob with N ImageJobTask rows via JobManager, then "
            "publishes N TaskDtos. Returns job_id + task_ids; subscribe "
            "to job:<job_id> for the aggregate progress stream.",
)
async def fft_batch_dispatch(
    request: FftBatchDispatchRequest,
    _: None = Depends(require_permission('image_processing', 'write')),
    user_id: UUID = Depends(get_current_user_id),
):
    from core.helper import dispatch_fft_task
    from services.job_manager import job_manager

    if not request.image_paths:
        raise HTTPException(status_code=400, detail="image_paths must be non-empty")

    n = len(request.image_paths)
    task_ids = [uuid.uuid4() for _ in range(n)]
    target_paths = [_fft_target_for(p) for p in request.image_paths]

    job_envelope = job_manager.create_job(
        plugin_id="magellon_fft_plugin",
        name=request.name or f"FFT batch x{n}",
        settings={"image_paths": request.image_paths, "target_paths": target_paths},
        task_ids=task_ids,
        user_id=str(user_id) if user_id else None,
        job_id=request.job_id,
    )
    job_id = uuid.UUID(job_envelope["job_id"])

    failures: list[str] = []
    for img, tgt, tid in zip(request.image_paths, target_paths, task_ids):
        try:
            ok = dispatch_fft_task(
                image_path=img,
                target_path=tgt,
                job_id=job_id,
                task_id=tid,
            )
        except TaskDispatchError:
            ok = False
        if not ok:
            failures.append(str(tid))

    if failures:
        job_manager.fail_job(
            str(job_id),
            error=f"Failed to publish {len(failures)}/{n} task(s): {failures}",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to publish {len(failures)}/{n} FFT task(s)",
        )

    logger.info(
        "User %s dispatched FFT batch job=%s tasks=%d", user_id, job_id, n,
    )
    return FftBatchDispatchResponse(
        job_id=job_id,
        task_ids=task_ids,
        queue_name="fft_tasks_queue",
        target_paths=target_paths,
    )


# ---------------------------------------------------------------------------
# Ptolemy (square / hole detection) — manual dispatch endpoints
# ---------------------------------------------------------------------------
# Unlike CTF / MotionCor, ptolemy is not dispatched from the bulk import
# pipeline — it applies only to atlas-scale or grid-overview images.
# These endpoints let operators fan out square or hole detection on
# specific images without waiting for pipeline automation to pick them up.

class PtolemyDispatchRequest(BaseModel):
    image_path: str
    job_id: Optional[UUID] = None
    image_id: Optional[UUID] = None
    session_name: Optional[str] = None


class PtolemyDispatchResponse(BaseModel):
    job_id: UUID
    task_id: UUID
    queue_name: str
    image_path: str
    category: str
    status: str = "dispatched"


def _ptolemy_dispatch(
    request: PtolemyDispatchRequest,
    *,
    category_label: str,
    plugin_id: str,
    queue_name: str,
    user_id: UUID,
) -> PtolemyDispatchResponse:
    """Shared body for the two ptolemy dispatch endpoints.

    Creates a 1-task ImageJob via JobManager (so DB has authoritative
    state from the moment of dispatch), then publishes the TaskMessage
    onto the category's RMQ queue.
    """
    from core.helper import (
        dispatch_hole_detection_task,
        dispatch_square_detection_task,
    )
    from services.job_manager import job_manager

    task_id = uuid.uuid4()

    job_envelope = job_manager.create_job(
        plugin_id=plugin_id,
        name=f"{category_label} {os.path.basename(request.image_path)}",
        settings={"image_path": request.image_path},
        task_ids=[task_id],
        user_id=str(user_id) if user_id else None,
        job_id=request.job_id,
    )
    job_id = uuid.UUID(job_envelope["job_id"])

    logger.info(
        "User %s dispatching %s task %s in job %s for image %s",
        user_id, category_label, task_id, job_id, request.image_path,
    )

    dispatch_fn = (
        dispatch_square_detection_task
        if category_label == "SquareDetection"
        else dispatch_hole_detection_task
    )
    try:
        ok = dispatch_fn(
            image_path=request.image_path,
            job_id=job_id,
            task_id=task_id,
            image_id=request.image_id,
            session_name=request.session_name,
        )
    except TaskDispatchError:
        ok = False
    if not ok:
        job_manager.fail_job(
            str(job_id), error=f"Failed to publish {category_label} task to RMQ",
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to publish {category_label} task to RMQ",
        )

    return PtolemyDispatchResponse(
        job_id=job_id,
        task_id=task_id,
        queue_name=queue_name,
        image_path=request.image_path,
        category=category_label,
    )


@image_processing_router.post(
    "/ptolemy/square/dispatch",
    response_model=PtolemyDispatchResponse,
    summary="Dispatch a ptolemy square-detection task (low-mag MRC) via RMQ. "
            "Creates a JobManager-backed job + one task, returns job_id and "
            "task_id for step-event subscription.",
)
async def ptolemy_square_dispatch(
    request: PtolemyDispatchRequest,
    _: None = Depends(require_permission('image_processing', 'write')),
    user_id: UUID = Depends(get_current_user_id),
):
    return _ptolemy_dispatch(
        request,
        category_label="SquareDetection",
        plugin_id="magellon_ptolemy_plugin",
        queue_name="square_detection_tasks_queue",
        user_id=user_id,
    )


@image_processing_router.post(
    "/ptolemy/hole/dispatch",
    response_model=PtolemyDispatchResponse,
    summary="Dispatch a ptolemy hole-detection task (med-mag MRC) via RMQ. "
            "Creates a JobManager-backed job + one task, returns job_id and "
            "task_id for step-event subscription.",
)
async def ptolemy_hole_dispatch(
    request: PtolemyDispatchRequest,
    _: None = Depends(require_permission('image_processing', 'write')),
    user_id: UUID = Depends(get_current_user_id),
):
    return _ptolemy_dispatch(
        request,
        category_label="HoleDetection",
        plugin_id="magellon_ptolemy_plugin",
        queue_name="hole_detection_tasks_queue",
        user_id=user_id,
    )


# ---------------------------------------------------------------------------
# Ptolemy — job status + detection results read endpoints
# ---------------------------------------------------------------------------

@image_processing_router.get(
    "/jobs/{job_id}",
    summary="Poll the status of a dispatched detection (or FFT) job. "
            "Returns the job envelope from JobManager (status, progress, error).",
)
async def get_image_job_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    from services.job_manager import job_manager
    try:
        return job_manager.get_job(str(job_id))
    except LookupError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")


class DetectionResultResponse(BaseModel):
    category: str
    detections: list
    image_shape: Optional[list] = None
    grid_angle: Optional[float] = None
    grid_pitch: Optional[float] = None


@image_processing_router.get(
    "/{image_id}/detections",
    response_model=DetectionResultResponse,
    summary="Fetch the most recent stored detection result (square or hole) "
            "for a given image. Returns detections in MRC pixel coordinates "
            "plus the image dimensions needed for scaling overlays.",
)
def get_image_detections(
    image_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    import json as _json
    from models.sqlalchemy_models import ImageMetaData as _IMD

    row = (
        db.query(_IMD)
        .filter(
            _IMD.image_id == image_id,
            _IMD.name.in_(["SquareDetection Data", "HoleDetection Data"]),
        )
        .order_by(_IMD.oid.desc())
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No detection results found for image {image_id}",
        )

    raw = row.data
    try:
        if isinstance(raw, (bytes, bytearray)):
            payload = _json.loads(raw.decode("utf-8"))
        else:
            payload = _json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    category = row.name.replace(" Data", "") if row.name else "Unknown"
    return DetectionResultResponse(
        category=category,
        detections=payload.get("detections", []),
        image_shape=payload.get("image_shape"),
        grid_angle=payload.get("grid_angle"),
        grid_pitch=payload.get("grid_pitch"),
    )


# ---------------------------------------------------------------------------
# Topaz (particle picking + denoising) — manual dispatch endpoints
# ---------------------------------------------------------------------------

class TopazPickDispatchRequest(BaseModel):
    image_path: str
    job_id: Optional[UUID] = None
    image_id: Optional[UUID] = None
    session_name: Optional[str] = None
    model: str = "resnet16"
    radius: int = 14
    threshold: float = -3.0
    scale: int = 8


class TopazDenoiseDispatchRequest(BaseModel):
    image_path: str
    output_file: Optional[str] = None
    job_id: Optional[UUID] = None
    image_id: Optional[UUID] = None
    session_name: Optional[str] = None
    model: str = "unet"
    patch_size: int = 1024
    padding: int = 128


class TopazDispatchResponse(BaseModel):
    job_id: UUID
    task_id: UUID
    queue_name: str
    image_path: str
    category: str
    status: str = "dispatched"


@image_processing_router.post(
    "/topaz/pick/dispatch",
    response_model=TopazDispatchResponse,
    summary="Dispatch a topaz particle-picking task (high-mag MRC) via RMQ. "
            "Returns job_id + task_id for step-event subscription.",
)
async def topaz_pick_dispatch(
    request: TopazPickDispatchRequest,
    _: None = Depends(require_permission('image_processing', 'write')),
    user_id: UUID = Depends(get_current_user_id),
):
    from core.helper import dispatch_topaz_pick_task
    from services.job_manager import job_manager

    task_id = uuid.uuid4()
    job_envelope = job_manager.create_job(
        plugin_id="magellon_topaz_plugin",
        name=f"Topaz pick {os.path.basename(request.image_path)}",
        settings={"image_path": request.image_path,
                  "model": request.model, "radius": request.radius,
                  "threshold": request.threshold, "scale": request.scale},
        task_ids=[task_id],
        user_id=str(user_id) if user_id else None,
        job_id=request.job_id,
    )
    job_id = uuid.UUID(job_envelope["job_id"])

    logger.info(
        "User %s dispatching topaz pick task %s in job %s for image %s",
        user_id, task_id, job_id, request.image_path,
    )
    try:
        ok = dispatch_topaz_pick_task(
            image_path=request.image_path,
            model=request.model,
            radius=request.radius,
            threshold=request.threshold,
            scale=request.scale,
            job_id=job_id,
            task_id=task_id,
            image_id=request.image_id,
            session_name=request.session_name,
        )
    except TaskDispatchError:
        ok = False
    if not ok:
        job_manager.fail_job(str(job_id), error="Failed to publish topaz pick task to RMQ")
        raise HTTPException(status_code=502, detail="Failed to publish topaz pick task to RMQ")

    return TopazDispatchResponse(
        job_id=job_id, task_id=task_id,
        queue_name="topaz_pick_tasks_queue",
        image_path=request.image_path,
        category="TopazParticlePicking",
    )


@image_processing_router.post(
    "/topaz/denoise/dispatch",
    response_model=TopazDispatchResponse,
    summary="Dispatch a micrograph-denoise task (Topaz UNet) via RMQ. "
            "Returns job_id + task_id for step-event subscription.",
)
async def topaz_denoise_dispatch(
    request: TopazDenoiseDispatchRequest,
    _: None = Depends(require_permission('image_processing', 'write')),
    user_id: UUID = Depends(get_current_user_id),
):
    from core.helper import dispatch_micrograph_denoise_task
    from services.job_manager import job_manager

    task_id = uuid.uuid4()
    job_envelope = job_manager.create_job(
        plugin_id="magellon_topaz_plugin",
        name=f"Denoise {os.path.basename(request.image_path)}",
        settings={"image_path": request.image_path,
                  "output_file": request.output_file,
                  "model": request.model,
                  "patch_size": request.patch_size},
        task_ids=[task_id],
        user_id=str(user_id) if user_id else None,
        job_id=request.job_id,
    )
    job_id = uuid.UUID(job_envelope["job_id"])

    logger.info(
        "User %s dispatching denoise task %s in job %s for image %s",
        user_id, task_id, job_id, request.image_path,
    )
    try:
        ok = dispatch_micrograph_denoise_task(
            image_path=request.image_path,
            output_file=request.output_file,
            model=request.model,
            patch_size=request.patch_size,
            padding=request.padding,
            job_id=job_id,
            task_id=task_id,
            image_id=request.image_id,
            session_name=request.session_name,
        )
    except TaskDispatchError:
        ok = False
    if not ok:
        job_manager.fail_job(str(job_id), error="Failed to publish denoise task to RMQ")
        raise HTTPException(status_code=502, detail="Failed to publish denoise task to RMQ")

    return TopazDispatchResponse(
        job_id=job_id, task_id=task_id,
        queue_name="micrograph_denoise_tasks_queue",
        image_path=request.image_path,
        category="MicrographDenoising",
    )


@image_processing_router.post("/ctf")
async def calculate_ctf(
    abs_file_path: str,
    abs_out_file_name: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Calculate the CTF of an image.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.info(f"User {user_id} calculating CTF for file: {abs_file_path}")
    try:
        mrc_service.calculate_and_save_ctf(mrc_path=abs_file_path, save_path=abs_out_file_name)
        logger.info(f"User {user_id} successfully calculated CTF")
        return {"message": "CTF calculated successfully!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to calculate CTF: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


# @image_processing_router.post("/epu_images_job")
# def process_epu_import(input_data: EPUFrameTransferJobBase, db: Session = Depends(get_db)):
#     epu_frame_transfer_process(input_data, db)


class LeginonImportResponse(BaseModel):
    status: str
    message: str
    job_id: uuid.UUID = None


class _UploadProxy:
    """Thin UploadFile-compatible wrapper so file bytes survive past the request."""
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.file = io.BytesIO(content)


class _ImportFailedBeforeJob(RuntimeError):
    """An import failed before its image_job row existed; raised so the import
    queue (services/import_queue.py) records the reason for the UI."""


def _run_leginon_import(job_dto, user_id: UUID) -> None:
    set_import_owner(user_id)  # sessions created by this import belong to the importer
    def _notify(event: str, **extra):
        try:
            # Relay-aware: works in the web backend and in import workers.
            from services.import_progress import publish as schedule_import_progress
            schedule_import_progress(str(job_dto.job_id), {"job_id": str(job_dto.job_id), "event": event, **extra})
        except Exception:
            pass

    db = session_local()
    try:
        logger.warning("[Leginon] background import started: job=%s user=%s session=%s", job_dto.job_id, user_id, job_dto.magellon_session_name)
        _notify("started")
        svc = LeginonFrameTransferJobService()
        svc.setup_data(job_dto)
        result = svc.process(db) or {}
        # The service reports failure by returning it, not raising.
        error = result.get("error") or (result.get("message") if result.get("status") == "failure" else None)
        from services.job_manager import job_manager as _jm
        if error:
            _notify("failed", message=error)
            try:
                _jm.fail_job(str(job_dto.job_id), error=error)
            except LookupError:
                # Failed before its job row existed: raise so the import
                # queue records the reason for the progress window.
                raise _ImportFailedBeforeJob(error)
            logger.warning("[Leginon] import failed: job=%s: %s", job_dto.job_id, error)
            return
        _notify("dispatched", session_name=job_dto.magellon_session_name)
        try:
            # Keeps the job running until its CTF / MotionCor tasks report,
            # then it settles (completed, possibly with problems).
            _jm.complete_job(str(job_dto.job_id), result={"session_name": job_dto.magellon_session_name})
        except LookupError:
            pass  # e.g. "No images found in Leginon": nothing was created
        logger.info("[Leginon] background import dispatched: job=%s", job_dto.job_id)
    except _ImportFailedBeforeJob:
        raise
    except Exception as exc:
        logger.exception("[Leginon] unhandled exception in background import for job=%s", job_dto.job_id)
        _notify("failed", message="Unhandled exception during Leginon import")
        try:
            from services.job_manager import job_manager as _jm
            _jm.fail_job(str(job_dto.job_id), error=f"Unhandled exception during Leginon import: {exc}")
        except LookupError:
            raise _ImportFailedBeforeJob(f"Unhandled exception during Leginon import: {exc}")
    finally:
        db.close()


# Where the lab keeps a Leginon session's data, below the GPFS root: images in
# leginondata/<session>, movies (and the gain reference) in framesdata/<session>.
LEGINON_IMAGES_BASE = "leginondata"
LEGINON_FRAMES_BASE = "framesdata"
_GAIN_EXTENSIONS = (".mrc", ".tif", ".tiff", ".dm4", ".gain")


def _guess_leginon_folders(gpfs_root: str, session: str) -> dict:
    """A session's images folder, frames folder and gain file, as paths below
    the GPFS root (None where nothing fits). The import looks for the files in
    subfolders too, so the folders are the session's own. The user can change them."""
    def rel(path):
        return os.path.relpath(path, gpfs_root).replace(os.sep, "/")

    def first_dir(*candidates):
        return next((c for c in candidates if os.path.isdir(c)), None)

    images_root = os.path.join(gpfs_root, LEGINON_IMAGES_BASE, session)
    images = first_dir(images_root)

    frames_root = os.path.join(gpfs_root, LEGINON_FRAMES_BASE, session)
    frames = first_dir(frames_root)

    # A file named like a gain reference in the session folder, else one folder below.
    gain = None
    if os.path.isdir(frames_root):
        def gains_in(folder):
            with os.scandir(folder) as entries:
                return sorted(e.path for e in entries if e.is_file()
                              and "gain" in e.name.lower() and e.name.lower().endswith(_GAIN_EXTENSIONS))
        found = gains_in(frames_root)
        if not found:
            with os.scandir(frames_root) as entries:
                for sub in sorted(e.path for e in entries if e.is_dir()):
                    found = gains_in(sub)
                    if found:
                        break
        gain = found[0] if found else None

    return {"images_directory": rel(images) if images else None,
            "frames_directory": rel(frames) if frames else None,
            "gain_path": rel(gain) if gain else None}


@image_processing_router.get("/leginon_folders")
def leginon_folders(
    session_name: str,
    _: None = Depends(require_permission('msession', 'create')),
):
    """Suggested folders and gain file for a Leginon session (Leginon import form)."""
    session = session_name.strip()
    if not session or "/" in session or "\\" in session or session.startswith("."):
        raise HTTPException(status_code=422, detail="Enter a Leginon session name.")
    from controllers.import_controller import _resolve_gpfs_path
    return _guess_leginon_folders(_resolve_gpfs_path("/gpfs"), session)


@image_processing_router.post("/import_leginon_job")
def process_image_job(
    background_tasks: BackgroundTasks,
    magellon_project_name: str = Form(...),
    magellon_session_name: str = Form(...),
    session_name: str = Form(...),
    data_directory: Optional[str] = Form(None),
    images_directory: Optional[str] = Form(None),
    frames_directory: Optional[str] = Form(None),
    gain_path: Optional[str] = Form(None),
    camera_directory: Optional[str] = Form(None),
    copy_images: bool = Form(False),
    retries: int = Form(0),

    leginon_mysql_host: Optional[str] = Form(None),
    leginon_mysql_port: Optional[int] = Form(None),
    leginon_mysql_db: Optional[str] = Form(None),
    leginon_mysql_user: Optional[str] = Form(None),
    leginon_mysql_pass: Optional[str] = Form(None),

    replace_type: str = Form("none"),
    replace_pattern: Optional[str] = Form(None),
    replace_with: Optional[str] = Form(None),

    defects_file: Optional[UploadFile] = File(None),
    gains_file: Optional[UploadFile] = File(None),

    _: None = Depends(require_permission('msession', 'create')),
    user_id: UUID = Depends(get_current_user_id)
):
    # Read uploaded file bytes now — UploadFile streams close after the request returns.
    defects_proxy = _UploadProxy(defects_file.filename, defects_file.file.read()) if defects_file else None
    gains_proxy = _UploadProxy(gains_file.filename, gains_file.file.read()) if gains_file else None

    # Data folder (or, for older clients, a frames folder) as the backend
    # sees it; a folder that doesn't exist is rejected before queuing.
    from controllers.import_controller import _resolve_gpfs_path
    if images_directory:
        # Images and movies in separate folders, and the gain file as a path
        # or uploaded: all three are required.
        if not (frames_directory or "").strip():
            raise HTTPException(status_code=422, detail="Choose the session's frames folder.")
        if not ((gain_path or "").strip() or gains_file):
            raise HTTPException(status_code=422, detail="Give the gain file's path, or upload it.")
        images_directory = _resolve_gpfs_path(images_directory.strip())
        if not os.path.isdir(images_directory):
            raise HTTPException(status_code=404, detail=f"Images folder not found: {images_directory}")
        frames_directory = _resolve_gpfs_path(frames_directory.strip())
        if not os.path.isdir(frames_directory):
            raise HTTPException(status_code=404, detail=f"Frames folder not found: {frames_directory}")
        gain_path = None if gains_file else _resolve_gpfs_path(gain_path.strip())
        if gain_path and not os.path.isfile(gain_path):
            raise HTTPException(status_code=404, detail=f"Gain file not found: {gain_path}")
        data_directory = None
    elif data_directory:
        data_directory = _resolve_gpfs_path(data_directory.strip())
        if not os.path.isdir(data_directory):
            raise HTTPException(status_code=404, detail=f"Data folder not found: {data_directory}")
        # The folder must hold original/ (images), frames/ (movies) and
        # gains/ (gain reference). An uploaded gain file stands in for gains/.
        required = ["original", "frames"] + ([] if gains_file else ["gains"])
        missing = [f"{name}/" for name in required if not os.path.isdir(os.path.join(data_directory, name))]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=(f"The data folder must contain original/, frames/ and gains/. "
                        f"Missing in {data_directory}: {', '.join(missing)}"))
    elif not camera_directory:
        raise HTTPException(status_code=422, detail="Choose the session's images folder.")
    magellon_session_name = magellon_session_name.strip()
    session_name = session_name.strip()

    # The Leginon DB connection is server config (LEGINON_DB_* in Docker/.env);
    # form values only override it when explicitly sent.
    leginon_db = app_settings.leginon_db_settings

    job_id = uuid.uuid4()
    job_dto = LeginonFrameTransferJobDto(
        magellon_project_name=magellon_project_name,
        magellon_session_name=magellon_session_name,
        camera_directory=camera_directory,
        data_directory=data_directory,
        images_directory=images_directory,
        frames_directory=frames_directory if images_directory else None,
        gain_path=gain_path if images_directory else None,
        session_name=session_name,
        copy_images=copy_images,
        retries=retries,
        leginon_mysql_host=leginon_mysql_host or leginon_db.HOST,
        leginon_mysql_port=leginon_mysql_port or leginon_db.PORT,
        leginon_mysql_db=leginon_mysql_db or leginon_db.DATABASE,
        leginon_mysql_user=leginon_mysql_user or leginon_db.USER,
        leginon_mysql_pass=leginon_mysql_pass or leginon_db.PASSWORD,
        replace_type=replace_type,
        replace_pattern=replace_pattern,
        replace_with=replace_with,
        job_id=job_id,
        target_directory=os.path.join(MAGELLON_HOME_DIR, magellon_session_name),
        task_list=[],
    )
    # Attached after validation (the fields are typed UploadFile; the proxies
    # hold the bytes read above), as the import worker does.
    job_dto.defects_file = defects_proxy
    job_dto.gains_file = gains_proxy

    logger.warning("[Leginon] scheduling background import: job=%s user=%s session=%s", job_id, user_id, magellon_session_name)
    import_runners.enqueue_leginon(job_dto, user_id)
    return {"message": "Import scheduled", "job_id": str(job_id), "imported_by": str(user_id)}




def _run_epu_job_import(job_dto: EpuImportJobDto, user_id: UUID) -> None:
    set_import_owner(user_id)  # sessions created by this import belong to the importer
    def _notify(event: str, **extra):
        try:
            # Relay-aware: works in the web backend and in import workers.
            from services.import_progress import publish as schedule_import_progress
            schedule_import_progress(str(job_dto.job_id), {"job_id": str(job_dto.job_id), "event": event, **extra})
        except Exception:
            pass

    db = session_local()
    try:
        logger.warning("[EPU-old] background import started: job=%s user=%s session=%s", job_dto.job_id, user_id, job_dto.magellon_session_name)
        _notify("started")
        epu_importer = EPUImporter()
        epu_importer.setup_data(job_dto)
        result = epu_importer.process(db)
        _notify("dispatched", session_name=job_dto.session_name)
        logger.info("[EPU-old] background import completed: job=%s", job_dto.job_id)
    except Exception:
        logger.exception("[EPU-old] unhandled exception in background import for job=%s", job_dto.job_id)
        _notify("failed", message="Unhandled exception during EPU import")
    finally:
        db.close()


@image_processing_router.post("/import_epu_job")
def import_epu_job(
    input_data: EpuImportJobBase,
    background_tasks: BackgroundTasks,
    _: None = Depends(require_permission('msession', 'create')),
    user_id: UUID = Depends(get_current_user_id)
):
    job_id = uuid.uuid4()
    job_dto = EpuImportJobDto(
        magellon_project_name=input_data.magellon_project_name,
        magellon_session_name=input_data.magellon_session_name,
        camera_directory=input_data.camera_directory,
        session_name=input_data.session_name,
        copy_images=input_data.copy_images,
        retries=input_data.retries,
        epu_dir_path=input_data.epu_dir_path,
        replace_type=input_data.replace_type,
        replace_pattern=input_data.replace_pattern,
        replace_with=input_data.replace_with,
        job_id=job_id,
        target_directory=os.path.join(MAGELLON_HOME_DIR, input_data.session_name),
        task_list=[]
    )
    logger.warning("[EPU-old] scheduling background import: job=%s user=%s session=%s", job_id, user_id, input_data.magellon_session_name)
    import_runners.enqueue_epu_job(job_dto, job_id, user_id)
    return {"message": "Import scheduled", "job_id": str(job_id), "imported_by": str(user_id)}


def do_low_pass_filter(file_path: str, output_path: str, p_resolution:float) -> Dict:
    """
    Process MRC file with Gaussian low-pass filtering.

    Args:
        file_path: Path to the input MRC file
        output_path: Path where the processed MRC file will be saved
        p_resolution: Target resolution in angstroms

    Returns:
        Dict with processing results including status and file paths
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    logger.info(f"Processing {file_path}")
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with mrcfile.open(file_path, permissive=True) as mrc:
            image = np.array(mrc.data, copy=True)
            voxel_size = mrc.voxel_size  # Preserve header information
            pixel_size = voxel_size['x']  # assuming uniform pixel size
            logger.debug(f"Pixel size: {pixel_size}Å, Image dtype: {image.dtype}")

            # Get header information to preserve
            nx = mrc.header.nx
            ny = mrc.header.ny
            nz = mrc.header.nz

        # Apply low-pass filter
        filtered = lowpass_filter(image, p_resolution, pixel_size)

        # Save processed image
        with mrcfile.new(output_path, overwrite=True) as mrc_processed:
            mrc_processed.set_data(filtered)
            mrc_processed.voxel_size = voxel_size
            mrc_processed.header.nx = nx
            mrc_processed.header.ny = ny
            mrc_processed.header.nz = nz

        return {
            "status": "success",
            "input_file": file_path,
            "output_file": output_path,
            "resolution": p_resolution,
            "pixel_size": float(pixel_size)
        }

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")



@image_processing_router.post("/low-pass-from-path/", summary="Process an MRC file using file paths")
async def do_low_pass_from_path(
    input_path: str,
    output_path: str,
    p_resolution: float,
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
) -> Dict:
    """
    Process an MRC file with Gaussian low-pass filtering.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions

    Args:
        input_path: Path to the input MRC file
        output_path: Path where the processed MRC file will be saved
        p_resolution: Target resolution in angstroms

    Returns:
        Dict: Processing results including status and file paths
    """
    logger.info(f"User {user_id} applying low-pass filter: input={input_path}, resolution={p_resolution}")
    try:
        result = do_low_pass_filter(input_path, output_path, p_resolution)
        logger.info(f"User {user_id} successfully applied low-pass filter")
        return {**result, "processed_by": str(user_id)}
    except FileNotFoundError as e:
        logger.error(f"User {user_id} - File not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"User {user_id} - Error in low-pass filter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@image_processing_router.post("/low-pass-from-upload/", summary="Process an uploaded MRC file")
async def do_low_pass_from_upload(
    p_resolution: float,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Process an uploaded MRC file and return the processed file for download.

    **Requires:** Authentication (all authenticated users can upload and process)
    **Security:** User uploads their own file - no database access required

    Args:
        p_resolution: Target resolution in angstroms
        file: Uploaded MRC file

    Returns:
        FileResponse: The processed MRC file
    """
    logger.info(f"User {user_id} uploading file for low-pass filter: {file.filename}, resolution={p_resolution}")
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mrc") as temp_input:
            # Copy uploaded file to temp file
            shutil.copyfileobj(file.file, temp_input)
            temp_input_path = temp_input.name

        # Create output temp file
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mrc")
        temp_output_path = temp_output.name
        temp_output.close()

        # Process the file
        result = do_low_pass_filter(temp_input_path, temp_output_path, p_resolution)
        logger.info(f"User {user_id} processed uploaded file: {result}")

        # Clean up the input temp file
        os.unlink(temp_input_path)

        # Return the processed file
        logger.info(f"User {user_id} returning processed file: processed_{os.path.basename(file.filename)}")
        return FileResponse(
            temp_output_path,
            media_type="application/octet-stream",
            filename=f"processed_{os.path.basename(file.filename)}",
            background=lambda: os.unlink(temp_output_path)  # Clean up after sending file
        )

    except Exception as e:
        # Clean up temp files in case of error
        logger.error(f"User {user_id} - Error processing uploaded file: {str(e)}")
        if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
            os.unlink(temp_output_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")