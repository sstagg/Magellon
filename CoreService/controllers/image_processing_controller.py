import logging
import os
import shutil
import tempfile
import uuid
from typing import Dict
from uuid import UUID

import mrcfile
import numpy as np
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from starlette.responses import FileResponse
from typing import Optional

from config import MAGELLON_HOME_DIR
from controllers.image_processing_tools import lowpass_filter
from models.pydantic_models import LeginonFrameTransferJobBase, LeginonFrameTransferJobDto, \
    EpuImportJobBase, EpuImportJobDto
from services.importers.EPUImporter import EPUImporter
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService
from sqlalchemy.orm import Session
from database import get_db
from services.mrc_image_service import MrcImageService
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_permission

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
    ok = dispatch_fft_task(
        image_path=request.image_path,
        target_path=target_path,
        job_id=job_id,
        task_id=task_id,
        image_id=request.image_id,
    )
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
        ok = dispatch_fft_task(
            image_path=img,
            target_path=tgt,
            job_id=job_id,
            task_id=tid,
        )
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
    ok = dispatch_fn(
        image_path=request.image_path,
        job_id=job_id,
        task_id=task_id,
        image_id=request.image_id,
        session_name=request.session_name,
    )
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


@image_processing_router.post("/import_leginon_job")
def process_image_job(
    magellon_project_name: str = Form(...),
    magellon_session_name: str = Form(...),
    camera_directory: str = Form(...),
    session_name: str = Form(...),
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

    db: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import data from Leginon system.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Creates new sessions/images, requires creation permission
    """

    # ✅ Create your Pydantic model manually
    input_data = LeginonFrameTransferJobBase(
        magellon_project_name=magellon_project_name,
        magellon_session_name=magellon_session_name,
        camera_directory=camera_directory,
        session_name=session_name,
        copy_images=copy_images,
        retries=retries,
        leginon_mysql_host=leginon_mysql_host,
        leginon_mysql_port=leginon_mysql_port,
        leginon_mysql_db=leginon_mysql_db,
        leginon_mysql_user=leginon_mysql_user,
        leginon_mysql_pass=leginon_mysql_pass,
        replace_type=replace_type,
        replace_pattern=replace_pattern,
        replace_with=replace_with,
    )

    job_id = uuid.uuid4()
    job_dto = LeginonFrameTransferJobDto(
        magellon_project_name=input_data.magellon_project_name,
        magellon_session_name=input_data.magellon_session_name,
        camera_directory=input_data.camera_directory,
        session_name=input_data.session_name,
        copy_images=input_data.copy_images,
        retries=input_data.retries,
        leginon_mysql_host=input_data.leginon_mysql_host,
        leginon_mysql_port=input_data.leginon_mysql_port,
        leginon_mysql_db=input_data.leginon_mysql_db,
        leginon_mysql_user=input_data.leginon_mysql_user,
        leginon_mysql_pass=input_data.leginon_mysql_pass,
        replace_type=input_data.replace_type,
        replace_pattern=input_data.replace_pattern,
        replace_with=input_data.replace_with,
        job_id=job_id,
        target_directory=os.path.join(MAGELLON_HOME_DIR, input_data.magellon_session_name),
        defects_file=defects_file,
        gains_file=gains_file,
        task_list=[],
    )


    logger.warning(f"User {user_id} importing Leginon job: session={magellon_session_name}")

    lft_service.setup_data(job_dto)
    result = lft_service.process(db)

    logger.info(f"User {user_id} completed Leginon import: job_id={job_id}")
    return {**result, "imported_by": str(user_id)}




@image_processing_router.post("/import_epu_job")
def import_epu_job(
    input_data: EpuImportJobBase,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import data from EPU system.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Creates new sessions/images, requires creation permission
    """
    # Generate a unique job ID

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
        target_directory=os.path.join(MAGELLON_HOME_DIR, input_data.magellon_session_name),
        task_list=[]  # You can set this to None or any desired value
    )

    logger.warning(f"User {user_id} importing EPU job: session={input_data.magellon_session_name}")

    job_dto.target_directory = os.path.join(MAGELLON_HOME_DIR, job_dto.session_name)
    epu_importer = EPUImporter()
    epu_importer.setup_data(job_dto)
    result = epu_importer.process(db)

    logger.info(f"User {user_id} completed EPU import: job_id={job_id}")
    return {**result, "imported_by": str(user_id)}


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