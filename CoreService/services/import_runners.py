"""How each kind of import travels through the durable queue.

``enqueue_<kind>`` runs in the web backend: it turns the request into a
JSON payload (saving any uploaded files to disk, since bytes in memory can't
reach another process) and submits it to ``services.import_queue``.

``run(row)`` runs in an import worker: it rebuilds the request objects from
the payload and calls the very same ``_run_*_import`` functions the backend
used to run in-process, so importer behaviour is unchanged.

Secrets are not stored in the queue: the Leginon database password comes
from the worker's own settings (``LEGINON_DB_*``) when the import runs.
"""
import json
import os
import shutil
from pathlib import Path
from typing import Callable, Dict, Optional
from uuid import UUID

from config import MAGELLON_HOME_DIR, app_settings
from models.pydantic_models import (
    EpuImportJobDto,
    LeginonFrameTransferJobDto,
    MagellonImportJobDto,
    SerialEMImportJobDto,
)
from services import import_queue, session_names

# Hidden staging area for uploaded files of queued imports: inside Magellon's
# storage (shared by backend and workers) but outside the browsable
# /magellon/uploads and /magellon/templates folders.
_UPLOAD_ROOT = Path(MAGELLON_HOME_DIR) / ".import-uploads"


def _upload_dir(job_id) -> Path:
    return _UPLOAD_ROOT / str(job_id)


def cleanup(job_id) -> None:
    shutil.rmtree(_upload_dir(job_id), ignore_errors=True)


# ---------------------------------------------------------------------------
# Backend side: request → queue payload
# ---------------------------------------------------------------------------

def enqueue_leginon(job_dto: LeginonFrameTransferJobDto, user_id: UUID) -> Optional[int]:
    job_id = str(job_dto.job_id)
    uploads = {}
    for field in ("gains_file", "defects_file"):
        upload = getattr(job_dto, field, None)
        if upload is None:
            continue
        target_dir = _upload_dir(job_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = os.path.basename(upload.filename.replace("\\", "/")) or field
        path = target_dir / f"{field}-{name}"
        upload.file.seek(0)
        path.write_bytes(upload.file.read())
        uploads[field] = {"filename": upload.filename, "path": str(path)}

    dto = job_dto.model_dump(mode="json", exclude={"gains_file", "defects_file", "leginon_mysql_pass"})
    try:
        return import_queue.submit(
            job_id, "leginon", {"dto": dto, "uploads": uploads, "user_id": str(user_id)},
            owner_id=user_id, label=job_dto.magellon_session_name,
        )
    except session_names.SessionNameTaken:
        cleanup(job_id)
        raise


def enqueue_epu_job(job_dto: EpuImportJobDto, job_id: UUID, user_id: UUID) -> Optional[int]:
    # EpuImportJobDto has no job_id field (the legacy endpoint's job_id=...
    # was silently dropped), so it travels beside the DTO.
    return import_queue.submit(
        job_id, "epu_job",
        {"dto": job_dto.model_dump(mode="json"), "user_id": str(user_id)},
        owner_id=user_id, label=job_dto.magellon_session_name,
    )


def enqueue_epu(request: EpuImportJobDto, job_id: UUID, user_id: UUID) -> Optional[int]:
    return import_queue.submit(
        job_id, "epu",
        {"dto": request.model_dump(mode="json"), "user_id": str(user_id)},
        owner_id=user_id, label=request.magellon_session_name,
    )


def _magellon_session_name(source_dir: str) -> str:
    """The session a Magellon export creates: the name in its session.json."""
    try:
        with open(os.path.join(source_dir, "session.json")) as f:
            name = (json.load(f).get("msession") or {}).get("name")
        if name:
            return name
    except (OSError, ValueError):
        pass
    return os.path.basename(source_dir.rstrip("/"))


def enqueue_magellon(request: MagellonImportJobDto, job_id: UUID, user_id: UUID) -> Optional[int]:
    return import_queue.submit(
        job_id, "magellon",
        {"dto": request.model_dump(mode="json"), "user_id": str(user_id)},
        owner_id=user_id, label=_magellon_session_name(request.source_dir),
    )


def enqueue_serialem(request: SerialEMImportJobDto, job_id: UUID, user_id: UUID) -> Optional[int]:
    return import_queue.submit(
        job_id, "serialem",
        {"dto": request.model_dump(mode="json"), "user_id": str(user_id)},
        owner_id=user_id, label=request.magellon_session_name,
    )


# ---------------------------------------------------------------------------
# Worker side: queue payload → the existing import runners
# ---------------------------------------------------------------------------

def _run_leginon(payload: dict, job_id: str) -> None:
    from controllers.image_processing_controller import _UploadProxy, _run_leginon_import

    dto = LeginonFrameTransferJobDto.model_validate(payload["dto"])
    if not dto.leginon_mysql_pass:
        dto.leginon_mysql_pass = app_settings.leginon_db_settings.PASSWORD
    for field, info in (payload.get("uploads") or {}).items():
        setattr(dto, field, _UploadProxy(info["filename"], Path(info["path"]).read_bytes()))
    _run_leginon_import(dto, UUID(payload["user_id"]))


def _run_epu_job(payload: dict, job_id: str) -> None:
    from controllers.image_processing_controller import _run_epu_job_import

    dto = EpuImportJobDto.model_validate(payload["dto"])
    # The legacy runner reads job_dto.job_id; attach it (not a model field).
    object.__setattr__(dto, "job_id", UUID(job_id))
    _run_epu_job_import(dto, UUID(payload["user_id"]))


def _run_epu(payload: dict, job_id: str) -> None:
    from controllers.import_controller import _run_epu_import

    _run_epu_import(EpuImportJobDto.model_validate(payload["dto"]), UUID(job_id), UUID(payload["user_id"]))


def _run_magellon(payload: dict, job_id: str) -> None:
    from controllers.import_controller import _run_magellon_import

    _run_magellon_import(MagellonImportJobDto.model_validate(payload["dto"]), UUID(job_id), UUID(payload["user_id"]))


def _run_serialem(payload: dict, job_id: str) -> None:
    from controllers.import_controller import _run_serialem_import

    _run_serialem_import(SerialEMImportJobDto.model_validate(payload["dto"]), UUID(job_id), UUID(payload["user_id"]))


RUNNERS: Dict[str, Callable[[dict, str], None]] = {
    "leginon": _run_leginon,
    "epu_job": _run_epu_job,
    "epu": _run_epu,
    "magellon": _run_magellon,
    "serialem": _run_serialem,
}


def run(row) -> None:
    """Run one claimed queue row (worker side)."""
    try:
        if row.label:
            # Re-checked here: the name may have been taken since submission,
            # or by an import submitted in the same instant (the earlier wins).
            reason = session_names.problem(row.label, row.id, check_queue=False)
            if reason is None and not session_names.first_claim(row.label, row.id):
                reason = f"Another import named '{row.label}' was submitted at the same time. Choose another session name."
            if reason:
                raise session_names.SessionNameTaken(reason)
        RUNNERS[row.kind](row.payload, row.id)
    finally:
        cleanup(row.id)
