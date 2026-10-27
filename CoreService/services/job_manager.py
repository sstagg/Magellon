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
from models.sqlalchemy_models import ImageJob, ImageJobTask, PipelineRun

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

# PipelineRun.status_id uses a *different* enum from ImageJob.status_id
# (it mirrors the import_controller convention, not JobManager's). Kept
# in sync with controllers/pipelines_controller.py's _STATUS_* set.
RUN_STATUS_PENDING = 1
RUN_STATUS_RUNNING = 2
RUN_STATUS_COMPLETED = 4
RUN_STATUS_FAILED = 5
RUN_STATUS_CANCELLED = 6


def _iso_utc(value) -> Optional[str]:
    """Timestamps are stored naive in UTC; say so on the wire. Without the
    zone, browsers read them as local time (a 15:08 EDT start showed 19:08)."""
    if value is None:
        return None
    return value.isoformat() + "Z" if value.tzinfo is None else value.isoformat()


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
        "started_at": _iso_utc(job.start_date or job.created_date),
        "ended_at": _iso_utc(job.end_date),
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
        """Flag a running job for cancellation. Idempotent.

        Two cancellation paths fan out from here:

        - **In-process plugins** poll :meth:`is_cancelled` via their
          progress reporter and raise ``JobCancelledError`` at the
          next checkpoint. Same shape as pre-G.1.

        - **External (RMQ) plugins** (G.1) rely on a bus-delivered
          cancel event. This method publishes
          ``magellon.plugins.cancel.<job_id>`` via
          ``bus.events.publish``; the plugin's ``PluginBrokerRunner``
          subscribes on startup and marks the id in its
          :class:`CancelRegistry`. The plugin's progress reporter
          picks up the flag at the next ``reporter.progress(...)``
          and raises.

        Bus publish is best-effort: if the bus isn't installed or
        the broker is hiccuping, we log and continue — the in-process
        path is unaffected, and a retry of the cancel will republish.
        """
        self._cancel_requests.add(job_id)
        self._publish_bus_cancel(job_id)

    @staticmethod
    def _publish_bus_cancel(job_id: str) -> None:
        """Publish the G.1 cancel event. Swallow any failure so a
        broker hiccup doesn't block in-process cancel semantics."""
        try:
            from magellon_sdk.bus import get_bus
            from magellon_sdk.bus.routes.event_route import CancelRoute
            from magellon_sdk.bus.services.cancel_registry import CancelMessage
            from magellon_sdk.envelope import Envelope

            msg = CancelMessage(job_id=uuid.UUID(job_id)) if isinstance(job_id, str) else CancelMessage(job_id=job_id)
            route = CancelRoute.for_job(str(msg.job_id))
            envelope = Envelope.wrap(
                source="magellon/core_service/job_manager",
                type="magellon.plugin.cancel.v1",
                subject=route.subject,
                data=msg,
            )
            receipt = get_bus().events.publish(route, envelope)
            if not receipt.ok:
                logger.warning(
                    "JobManager.request_cancel: bus publish returned ok=False for job %s: %s",
                    job_id, receipt.error,
                )
        except Exception:  # noqa: BLE001
            logger.warning(
                "JobManager.request_cancel: bus publish failed for job %s — "
                "in-process cancel still fires; external plugins will not "
                "see this cancel until the bus recovers",
                job_id, exc_info=True,
            )

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
        parent_run_id: Optional[uuid.UUID] = None,
        subject_kind: Optional[str] = None,
        subject_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Insert a new job row and optional per-image / per-task rows.

        Four task-creation modes:
          - ``task_ids`` AND ``image_ids`` (zipped 1:1): broker dispatch
            mode — caller minted the task_id up front so the outbound
            TaskMessage carries the same id that lands in the DB. Each
            ImageJobTask gets the supplied (oid, image_id) pair.
            **Critical**: pre-2026-05-04 fix this branch silently
            discarded ``task_ids`` and minted random oids; results
            referenced ids that didn't exist. Reviewer-flagged blocker.
          - ``image_ids`` alone: one ImageJobTask per image with a fresh
            random oid (FK to image.oid). Used by importers that fan
            out per-image work without a pre-minted task id.
          - ``task_ids`` alone: pre-allocated task oids, image_id NULL —
            aggregate-input flows (TWO_D_CLASSIFICATION) where there
            is no per-image fan-out.
          - both omitted: just the parent ImageJob row.

        ``job_id`` lets the caller fix the parent oid in advance — useful
        when an upstream UUID has already been minted (e.g. echoed in
        the response so the client can subscribe to ``job:<uuid>`` before
        any events fire).

        ``parent_run_id`` (Phase 8 / 2026-05-03) links the new job to a
        PipelineRun. Nullable; pre-PipelineRun callers continue working
        as standalone runs. ``subject_kind`` / ``subject_id`` (Phase 3)
        seed the per-task subject for non-image-keyed dispatches; the
        runner's `_stamp_subject` provides the contract-default
        fallback if dispatch leaves them None.
        """
        job_oid = job_id or uuid.uuid4()
        now = datetime.utcnow()

        # The zipped mode needs both lists at the same length. Validate
        # eagerly — a length mismatch silently dropping work is the
        # exact bug the broker-dispatch fix is closing.
        if task_ids and image_ids and len(task_ids) != len(image_ids):
            raise ValueError(
                f"task_ids and image_ids must zip 1:1 when both supplied "
                f"(got {len(task_ids)} task_ids vs {len(image_ids)} image_ids)"
            )

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
                parent_run_id=parent_run_id,
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

            # Resolve subject_kind default — image when not supplied,
            # except aggregate-input case (task_ids alone) where the
            # caller is responsible for setting it explicitly.
            row_subject_kind = subject_kind if subject_kind is not None else "image"

            if task_ids and image_ids:
                # Broker dispatch — zip 1:1 so the TaskMessage's task_id
                # references a real ImageJobTask.oid.
                for tid, image_id in zip(task_ids, image_ids):
                    iid = (
                        uuid.UUID(image_id) if isinstance(image_id, str) else image_id
                    )
                    db.add(ImageJobTask(
                        oid=tid,
                        job_id=job_oid,
                        image_id=iid,
                        status_id=STATUS_QUEUED,
                        subject_kind=row_subject_kind,
                        subject_id=subject_id if subject_id else iid,
                    ))
            elif image_ids:
                for image_id in image_ids:
                    iid = (
                        uuid.UUID(image_id) if isinstance(image_id, str) else image_id
                    )
                    db.add(ImageJobTask(
                        oid=uuid.uuid4(),
                        job_id=job_oid,
                        image_id=iid,
                        status_id=STATUS_QUEUED,
                        subject_kind=row_subject_kind,
                        subject_id=subject_id if subject_id else iid,
                    ))
            elif task_ids:
                for tid in task_ids:
                    db.add(ImageJobTask(
                        oid=tid,
                        job_id=job_oid,
                        image_id=None,
                        status_id=STATUS_QUEUED,
                        subject_kind=row_subject_kind,
                        subject_id=subject_id,
                    ))

            db.commit()
            db.refresh(job)
            return _envelope(job)

    # -- update -------------------------------------------------------------

    def mark_running(self, job_id: str, *, progress: int = 0) -> Dict[str, Any]:
        """QUEUED → RUNNING only. Every task's "step started" event calls this,
        so it must not touch a job that is already running (that reset its
        start time and progress) or finished (that reopened completed imports,
        which a later restart then failed as orphans)."""
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            if job.status_id not in (None, STATUS_QUEUED):
                return _envelope(job)
            job.status_id = STATUS_RUNNING
            job.start_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["progress"] = progress
            job.processed_json = processed
            self._rollup_parent_run(db, job)
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
            processed = dict(job.processed_json or {})
            # Importers call this once they have dispatched everything, while
            # CTF / MotionCor tasks are still running. Keep the result, leave
            # the job running; record_task_finished completes it with the
            # final outcome when the last task reports.
            expected = self._expected_tasks(db, job, processed)
            finished = len(processed.get("completed_tasks") or [])
            if expected > 0 and finished < expected and job.status_id not in (STATUS_FAILED, STATUS_CANCELLED):
                merged = dict(processed["result"]) if isinstance(processed.get("result"), dict) else {}
                if isinstance(result, dict):
                    merged.update(result)
                processed["result"] = merged
                if job.status_id in (None, STATUS_QUEUED):
                    job.status_id = STATUS_RUNNING
                    job.start_date = job.start_date or datetime.utcnow()
                job.processed_json = processed
                db.commit()
                db.refresh(job)
                return _envelope(job, include_result=True)
            job.status_id = STATUS_COMPLETED
            job.end_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["progress"] = 100
            processed["num_items"] = num_items
            processed["result"] = result
            job.processed_json = processed
            self._rollup_parent_run(db, job)
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
            self._rollup_parent_run(db, job)
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

    def record_task_finished(
        self, job_id: str, task_id: str, *, failed: bool = False,
        step: Optional[str] = None, reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record that a task finished — successfully or not — and settle the
        job once every task has.

        Partial-success policy: one bad movie (say, a gain/frame size
        mismatch) must not turn a 113-image import into "failed". A failed
        task counts as finished and its step + reason are kept on the job.
        When all tasks are done the job is COMPLETED, carrying a grouped
        ``problems`` list; it is FAILED only if every task failed. Import-
        level failures (bad path, crash) still go through ``fail_job``.

        Idempotent per task_id, and both reporters (the step-event projector
        and the result processor) may report the same task: a later failure
        report overrides an earlier success, never the other way round.
        Returns ``{completed, expected, failed, progress_pct, settled}``.
        """
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            processed = dict(job.processed_json or {})
            completed = list(processed.get("completed_tasks") or [])
            if task_id not in completed:
                completed.append(task_id)
            failures = dict(processed.get("failed_tasks") or {})
            if failed:
                failures[task_id] = {"step": step or "task", "reason": (reason or "task failed")[:500]}
            processed["completed_tasks"] = completed
            processed["failed_tasks"] = failures
            expected = self._expected_tasks(db, job, processed)
            processed["progress"] = int(round(100 * len(completed) / expected)) if expected else 0
            settled = self._settle(db, job, processed)
            db.commit()
        if settled:
            self._clear_cancel(job_id)
        return {
            "completed": len(completed), "expected": expected, "failed": len(failures),
            "progress_pct": processed["progress"], "settled": settled,
        }

    def settle_if_done(self, job_id: str) -> Optional[str]:
        """Settle a job whose tasks have all finished (used at startup for jobs
        left "running"); returns "completed" / "failed", or None if work remains."""
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            processed = dict(job.processed_json or {})
            settled = self._settle(db, job, processed)
            db.commit()
        if settled:
            self._clear_cancel(job_id)
        return settled

    @staticmethod
    def _expected_tasks(db: Session, job: ImageJob, processed: Dict[str, Any]) -> int:
        """Tasks the job waits for. Plugin jobs store it at creation; importers
        create their ImageJobTask rows themselves, so count those instead."""
        expected = int(processed.get("expected_tasks") or 0)
        if expected <= 0:
            expected = db.query(ImageJobTask).filter(ImageJobTask.job_id == job.oid).count()
            if expected:
                processed["expected_tasks"] = expected
        return expected

    def _settle(self, db: Session, job: ImageJob, processed: Dict[str, Any]) -> Optional[str]:
        """Apply the partial-success outcome if every task has finished.

        Mutates ``job`` / ``processed`` (written back here); the caller commits.
        """
        from collections import Counter

        completed = list(processed.get("completed_tasks") or [])
        failures = dict(processed.get("failed_tasks") or {})
        expected = self._expected_tasks(db, job, processed)
        settled = None
        # A job already failed at import level, or cancelled, stays so.
        if expected > 0 and len(completed) >= expected and job.status_id not in (STATUS_FAILED, STATUS_CANCELLED):
            grouped = Counter((f["step"], f["reason"]) for f in failures.values())
            problems = [{"step": st, "reason": rs, "count": n} for (st, rs), n in grouped.most_common()]
            if failures and len(failures) >= expected:
                job.status_id = STATUS_FAILED
                top = problems[0]
                processed["error"] = f"All {expected} tasks failed: {top['step']}: {top['reason']}"
                settled = "failed"
            else:
                job.status_id = STATUS_COMPLETED
                result = dict(processed["result"]) if isinstance(processed.get("result"), dict) else {}
                result.update(task_count=expected, completed_tasks=len(completed) - len(failures),
                              failed_tasks=len(failures), problems=problems)
                processed["result"] = result
                processed["num_items"] = expected
                processed["progress"] = 100
                if failures:
                    processed["warning"] = f"{len(failures)} of {expected} tasks failed"
                settled = "completed"
            job.end_date = datetime.utcnow()
        job.processed_json = processed
        if settled:
            self._rollup_parent_run(db, job)
        return settled


    def cancel_job(self, job_id: str, *, reason: str = "Cancelled by user") -> Dict[str, Any]:
        """Mark a job cancelled in the DB. Call after a cooperative stop."""
        with session_local() as db:
            job = self._get_or_404(db, job_id)
            job.status_id = STATUS_CANCELLED
            job.end_date = datetime.utcnow()
            processed = dict(job.processed_json or {})
            processed["error"] = reason
            job.processed_json = processed
            self._rollup_parent_run(db, job)
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

    def list_active(self) -> List[Dict[str, Any]]:
        """Every queued or running job, however old."""
        with session_local() as db:
            query = (db.query(ImageJob)
                     .filter(ImageJob.GCRecord.is_(None),
                             ImageJob.status_id.in_((STATUS_QUEUED, STATUS_RUNNING)))
                     .order_by(ImageJob.created_date.desc()))
            return [_envelope(job, include_result=False) for job in query.all()]

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _get_or_404(db: Session, job_id: str) -> ImageJob:
        job = db.query(ImageJob).filter(ImageJob.oid == uuid.UUID(job_id)).first()
        if job is None:
            raise LookupError(f"Job {job_id} not found")
        return job

    @staticmethod
    def _rollup_parent_run(db: Session, job: ImageJob) -> None:
        """Recompute the parent ``PipelineRun.status_id`` from its child jobs.

        No-op when the job has no parent run (standalone job — the
        common pre-Phase-8 case). Runs inside the caller's open
        session so the run update commits atomically with the child
        job's status change; SQLAlchemy autoflush makes the just-set
        ``job.status_id`` visible to the sibling query below.

        Aggregate rule over child ``ImageJob.status_id`` (0-4 enum):

          - any child FAILED        -> run FAILED
          - else any CANCELLED      -> run CANCELLED
          - else all COMPLETED      -> run COMPLETED
          - else any RUNNING/done   -> run RUNNING
          - else (all QUEUED)       -> run PENDING

        Idempotent — recomputes the full picture each call, so
        out-of-order child transitions still converge.
        """
        run_id = job.parent_run_id
        if run_id is None:
            return
        run = db.query(PipelineRun).filter(PipelineRun.oid == run_id).first()
        if run is None:
            return

        statuses = [
            (s or STATUS_QUEUED)
            for (s,) in db.query(ImageJob.status_id)
            .filter(ImageJob.parent_run_id == run_id)
            .all()
        ]
        if not statuses:
            return

        if any(s == STATUS_FAILED for s in statuses):
            new_status = RUN_STATUS_FAILED
        elif any(s == STATUS_CANCELLED for s in statuses):
            new_status = RUN_STATUS_CANCELLED
        elif all(s == STATUS_COMPLETED for s in statuses):
            new_status = RUN_STATUS_COMPLETED
        elif any(s in (STATUS_RUNNING, STATUS_COMPLETED) for s in statuses):
            new_status = RUN_STATUS_RUNNING
        else:
            new_status = RUN_STATUS_PENDING

        terminal = (RUN_STATUS_COMPLETED, RUN_STATUS_FAILED, RUN_STATUS_CANCELLED)
        now = datetime.utcnow()
        if new_status != RUN_STATUS_PENDING and run.started_date is None:
            run.started_date = now
        if new_status in terminal:
            # Stamp the end time only on the *transition* into a terminal
            # state — a later child event must not drift ended_date.
            if run.ended_date is None:
                run.ended_date = now
        else:
            # Re-opened (e.g. a child re-run dropped the run back to
            # running); clear the stale end time.
            run.ended_date = None
        run.status_id = new_status


# Module-level singleton.
job_manager = JobManager()
