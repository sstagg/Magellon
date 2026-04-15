"""JobManager — DB-persisted job lifecycle for plugin executions.

Writes job state to the ``image_job`` table (plus ``image_job_task`` for
per-image tasks in a batch). Broadcasts every state change over Socket.IO
so the frontend can render real progress instead of client-side guesses.

The manager is plugin-agnostic: any plugin runner (sync, async, batch)
calls the same ``create_job`` / ``update_job`` / ``complete_job`` methods.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import session_local
from models.sqlalchemy_models import ImageJob, ImageJobTask

logger = logging.getLogger(__name__)


# Status codes — kept small & stable so UI can switch on them.
STATUS_QUEUED = 0
STATUS_RUNNING = 1
STATUS_COMPLETED = 2
STATUS_FAILED = 3
STATUS_CANCELLED = 4

_STATUS_LABEL = {
    STATUS_QUEUED: "queued",
    STATUS_RUNNING: "running",
    STATUS_COMPLETED: "completed",
    STATUS_FAILED: "failed",
    STATUS_CANCELLED: "cancelled",
}


def _envelope(job: ImageJob, *, include_result: bool = False, progress: int = 0,
              error: Optional[str] = None, num_items: int = 0) -> Dict[str, Any]:
    """Uniform JSON shape returned by every plugin job endpoint."""
    processed = job.processed_json or {}
    return {
        "job_id": str(job.oid),
        "plugin_id": job.plugin_id,
        "name": job.name,
        "status": _STATUS_LABEL.get(job.status_id or 0, "unknown"),
        "progress": processed.get("progress", progress),
        "num_items": processed.get("num_items", num_items),
        "started_at": job.start_date.isoformat() if job.start_date else None,
        "ended_at": job.end_date.isoformat() if job.end_date else None,
        "error": processed.get("error", error),
        "settings": job.settings,
        "result": processed.get("result") if include_result else None,
    }


class JobManager:
    """DB-backed persistence for plugin jobs — single state writer.

    All methods are synchronous from SQLAlchemy's perspective; callers in
    async code should invoke them through ``run_in_executor`` if the
    expected transaction is non-trivial. For short writes the direct call
    is fine — each method opens and closes its own session.
    """

    # In-memory set of jobs the user has asked to cancel. Cooperative:
    # plugins check this via the reporter and raise at stage boundaries;
    # a running thread won't be pre-empted. Cleared once the job settles.
    _cancel_requests: set[str] = set()

    # -- cancellation -------------------------------------------------------

    def request_cancel(self, job_id: str) -> None:
        """Flag a running job for cancellation. Idempotent."""
        self._cancel_requests.add(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        return job_id in self._cancel_requests

    def _clear_cancel(self, job_id: str) -> None:
        self._cancel_requests.discard(job_id)

    # -- create -------------------------------------------------------------

    def create_job(
        self,
        *,
        plugin_id: str,
        name: str,
        settings: Optional[Dict[str, Any]] = None,
        image_ids: Optional[List[str]] = None,
        task_ids: Optional[List[uuid.UUID]] = None,
        user_id: Optional[str] = None,
        msession_id: Optional[str] = None,
        job_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Insert a new job row and optional per-image / per-task rows.

        Three task-creation modes:
          - ``image_ids``: one ImageJobTask per image (FK to image.oid).
          - ``task_ids``: pre-allocated task oids, image_id NULL — used
            by message-driven dispatch flows (FFT/CTF/MotionCor) where
            the caller needs to know the task_id before persistence so
            it can echo the same id in the outbound RMQ TaskDto.
          - both omitted: just the parent ImageJob row.

        ``job_id`` lets the caller fix the parent oid in advance — useful
        when an upstream UUID has already been minted (e.g. echoed in
        the response so the client can subscribe to ``job:<uuid>`` before
        any events fire).
        """
        job_oid = job_id or uuid.uuid4()
        now = datetime.utcnow()

        expected_tasks = 0
        if task_ids:
            expected_tasks = len(task_ids)
        elif image_ids:
            expected_tasks = len(image_ids)

        with session_local() as db:
            job_settings = dict(settings or {})
            job = ImageJob(
                oid=job_oid,
                name=name,
                plugin_id=plugin_id,
                settings=job_settings,
                status_id=STATUS_QUEUED,
                created_date=now,
                user_id=user_id,
                msession_id=msession_id,
                # `expected_tasks` lets the projector know when the job
                # is fully done without scanning ImageJobTask rows.
                processed_json={
                    "progress": 0,
                    "num_items": expected_tasks,
                    "expected_tasks": expected_tasks,
                    "completed_tasks": [],
                },
            )
            db.add(job)

            if image_ids:
                for image_id in image_ids:
                    db.add(ImageJobTask(
                        oid=uuid.uuid4(),
                        job_id=job_oid,
                        image_id=uuid.UUID(image_id) if isinstance(image_id, str) else image_id,
                        status_id=STATUS_QUEUED,
                    ))
            elif task_ids:
                for tid in task_ids:
                    db.add(ImageJobTask(
                        oid=tid,
                        job_id=job_oid,
                        image_id=None,
                        status_id=STATUS_QUEUED,
                    ))

            db.commit()
            db.refresh(job)
            return _envelope(job)

    # -- update -------------------------------------------------------------

    def mark_running(self, job_id: str, *, progress: int = 0) -> Dict[str, Any]:
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            job.status_id = STATUS_RUNNING
            job.start_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["progress"] = progress
            job.processed_json = processed
            db.commit()
            db.refresh(job)
            return _envelope(job)

    def update_progress(self, job_id: str, *, progress: int,
                        num_items: Optional[int] = None) -> Dict[str, Any]:
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            processed = dict(job.processed_json or {})
            processed["progress"] = progress
            if num_items is not None:
                processed["num_items"] = num_items
            job.processed_json = processed
            db.commit()
            db.refresh(job)
            return _envelope(job)

    def complete_job(self, job_id: str, *, result: Any,
                     num_items: int = 0) -> Dict[str, Any]:
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            job.status_id = STATUS_COMPLETED
            job.end_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["progress"] = 100
            processed["num_items"] = num_items
            processed["result"] = result
            job.processed_json = processed
            db.commit()
            db.refresh(job)
            self._clear_cancel(job_id)
            return _envelope(job, include_result=True)

    def fail_job(self, job_id: str, *, error: str) -> Dict[str, Any]:
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            job.status_id = STATUS_FAILED
            job.end_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["error"] = error
            job.processed_json = processed
            db.commit()
            db.refresh(job)
            self._clear_cancel(job_id)
            return _envelope(job)

    # -- per-task transitions (driven by the step-event projector) ----------

    def mark_task_running(self, task_id: str) -> bool:
        """Flip a task row to RUNNING. Idempotent — no-op if already past
        QUEUED. Returns True if the row was updated."""
        with session_local() as db:
            task = db.query(ImageJobTask).filter(
                ImageJobTask.oid == uuid.UUID(task_id)
            ).first()
            if task is None or (task.status_id or 0) >= STATUS_RUNNING:
                return False
            task.status_id = STATUS_RUNNING
            db.commit()
            return True

    def mark_task_completed(self, task_id: str, *, result: Any = None) -> bool:
        """Flip a task row to COMPLETED and stash result in processed_json."""
        with session_local() as db:
            task = db.query(ImageJobTask).filter(
                ImageJobTask.oid == uuid.UUID(task_id)
            ).first()
            if task is None:
                return False
            task.status_id = STATUS_COMPLETED
            if result is not None:
                processed = dict(task.processed_json or {})
                processed["result"] = result
                task.processed_json = processed
            db.commit()
            return True

    def mark_task_failed(self, task_id: str, *, error: str) -> bool:
        with session_local() as db:
            task = db.query(ImageJobTask).filter(
                ImageJobTask.oid == uuid.UUID(task_id)
            ).first()
            if task is None:
                return False
            task.status_id = STATUS_FAILED
            processed = dict(task.processed_json or {})
            processed["error"] = error
            task.processed_json = processed
            db.commit()
            return True

    def record_task_completion(self, job_id: str, task_id: str) -> Dict[str, int]:
        """Record that ``task_id`` finished under ``job_id`` and recompute
        progress. Returns ``{completed, expected, progress_pct}``.

        Idempotent on task_id — re-recording a completion doesn't double-count.
        Caller decides whether to call ``complete_job`` based on the result.
        """
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            processed = dict(job.processed_json or {})
            completed = list(processed.get("completed_tasks") or [])
            if task_id not in completed:
                completed.append(task_id)
            expected = int(processed.get("expected_tasks") or 0)
            pct = int(round(100 * len(completed) / expected)) if expected else 0
            processed["completed_tasks"] = completed
            processed["progress"] = pct
            job.processed_json = processed
            db.commit()
            return {
                "completed": len(completed),
                "expected": expected,
                "progress_pct": pct,
            }

    def cancel_job(self, job_id: str, *, reason: str = "Cancelled by user") -> Dict[str, Any]:
        """Mark a job cancelled in the DB. Call after a cooperative stop."""
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            job.status_id = STATUS_CANCELLED
            job.end_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["error"] = reason
            job.processed_json = processed
            db.commit()
            db.refresh(job)
            self._clear_cancel(job_id)
            return _envelope(job)

    # -- read ---------------------------------------------------------------

    def get_job(self, job_id: str, *, include_result: bool = True) -> Dict[str, Any]:
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            return _envelope(job, include_result=include_result)

    def list_jobs(self, *, plugin_id: Optional[str] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        with session_local() as db:
            query = db.query(ImageJob)
            if plugin_id:
                query = query.filter(ImageJob.plugin_id == plugin_id)
            query = query.order_by(ImageJob.created_date.desc()).limit(limit)
            return [_envelope(job, include_result=False) for job in query.all()]

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _get_or_404(db: Session, job_id: str) -> ImageJob:
        job = db.query(ImageJob).filter(ImageJob.oid == uuid.UUID(job_id)).first()
        if job is None:
            raise LookupError(f"Job {job_id} not found")
        return job


# Module-level singleton.
job_manager = JobManager()
