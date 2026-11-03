"""Fail plugin jobs that were never picked up.

A plugin job still queued after STALE_QUEUED_MINUTES, while its plugin
finished nothing in that time, was lost (the plugin was down or the task
was dropped). Without this it shows "Queued" in the Jobs panel forever.
Run by the import worker's maintenance loop.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from database import session_local
from models.sqlalchemy_models import ImageJob, ImageJobTask
from services.job_manager import STATUS_COMPLETED, STATUS_FAILED, STATUS_QUEUED, job_manager

logger = logging.getLogger(__name__)

STALE_QUEUED_MINUTES = int(os.environ.get("MAGELLON_STALE_QUEUED_MINUTES", "60"))


def fail_stale_queued(now: Optional[datetime] = None) -> int:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(minutes=STALE_QUEUED_MINUTES)
    with session_local() as db:
        stale = (db.query(ImageJob.oid, ImageJob.plugin_id)
                 .filter(ImageJob.GCRecord.is_(None), ImageJob.plugin_id.isnot(None),
                         ImageJob.status_id == STATUS_QUEUED, ImageJob.created_date < cutoff).all())
        if not stale:
            return 0
        # A plugin still working through a backlog finished something lately;
        # its queued jobs are waiting their turn, not lost.
        busy = {pid for (pid,) in db.query(ImageJob.plugin_id)
                .filter(ImageJob.plugin_id.in_({pid for _, pid in stale}),
                        ImageJob.end_date >= cutoff,
                        ImageJob.status_id.in_((STATUS_COMPLETED, STATUS_FAILED))).distinct()}
        lost = [(oid, pid) for oid, pid in stale if pid not in busy]
        for oid, _ in lost:
            (db.query(ImageJobTask)
             .filter(ImageJobTask.job_id == oid, ImageJobTask.status_id == STATUS_QUEUED)
             .update({ImageJobTask.status_id: STATUS_FAILED}, synchronize_session=False))
        db.commit()
    for oid, pid in lost:
        job_manager.fail_job(str(oid), error=(
            f"Never started: {pid} did not pick this job up within {STALE_QUEUED_MINUTES} minutes. "
            "Run it again; if it fails again, ask an admin to check that the plugin is running."))
    if lost:
        logger.warning("[jobs] failed %d plugin job(s) that were never picked up", len(lost))
    return len(lost)


# How long a stopped import's cancel is repeated to the plugins.
CANCEL_REPEAT_HOURS = 24


def repeat_recent_cancels(now: Optional[datetime] = None) -> int:
    """Send the cancel again for imports stopped in the last day.

    Plugins skip queued tasks of a cancelled job, but keep the cancelled
    jobs in memory only; a plugin restarted after a stop would otherwise
    run the stopped import's leftover tasks. Repeating the (tiny) cancel
    message every maintenance pass covers that.
    """
    from sqlalchemy import text

    now = now or datetime.utcnow()
    with session_local() as db:
        ids = [row[0] for row in db.execute(text(
            "SELECT id FROM import_job_queue WHERE status = 'cancelled' AND finished_at >= :since"),
            {"since": now - timedelta(hours=CANCEL_REPEAT_HOURS)}).all()]
    for job_id in ids:
        job_manager._publish_bus_cancel(job_id)
    return len(ids)


# An import whose plugin steps have shown no activity (no result, no step
# event) for this long, after its worker finished, will never get them.
# Activity, not queue length: plugins hold many delivered tasks at once,
# which a queue's ready count doesn't show.
STUCK_IMPORT_MINUTES = int(os.environ.get("MAGELLON_STUCK_IMPORT_MINUTES", "30"))
# Each step an import task waits for, its label and the metadata its result saves.
# A late real result replaces this failure (JobManager.record_task_finished).
NO_RESULT_REASON = "No result came back from"
_STEP_RESULTS = {"ctf": ("CTF", "CTF Data"), "motioncor": ("MotionCor", "MotionCor Meta Data")}


def settle_stuck_import_tasks(now: Optional[datetime] = None) -> int:
    """Finish import tasks whose step results were lost (e.g. a backend
    restart while a result was being processed), so the import completes.

    For imports whose worker has finished and whose plugin steps have shown
    no activity (results, step events) for STUCK_IMPORT_MINUTES: a pending
    step whose result is saved is ticked off, and one without a result fails
    ("no result came back"; a result arriving later still replaces that).
    Returns the number of steps settled.
    """
    import json
    import uuid

    from sqlalchemy import text

    now = now or datetime.utcnow()
    cutoff = now - timedelta(minutes=STUCK_IMPORT_MINUTES)
    with session_local() as db:
        jobs = [row[0] for row in db.execute(text(
            "SELECT q.id FROM import_job_queue q JOIN image_job j ON j.oid = UNHEX(REPLACE(q.id, '-', ''))"
            " WHERE q.status = 'done' AND q.finished_at < :cutoff AND j.status_id = 1"
            " AND NOT EXISTS (SELECT 1 FROM task_result_receipt r WHERE r.job_id = q.id AND r.processed_at >= :cutoff)"
            " AND NOT EXISTS (SELECT 1 FROM job_event e WHERE e.job_id = j.oid AND e.ts >= :cutoff)"),
            {"cutoff": cutoff}).all()]
        stuck = {}
        for job_id in jobs:
            rows = db.execute(text(
                "SELECT t.oid, t.processed_json, "
                " (SELECT GROUP_CONCAT(m.name) FROM image_meta_data m WHERE m.image_id = t.image_id)"
                " FROM image_job_task t WHERE t.job_id = :job AND t.status_id = 1"),
                {"job": uuid.UUID(job_id).bytes}).all()
            for oid, processed, saved in rows:
                processed = processed if isinstance(processed, dict) else json.loads(processed or "{}")
                pending = processed.get("pending_steps")
                if pending:
                    stuck.setdefault(job_id, []).append(
                        (str(uuid.UUID(bytes=oid) if isinstance(oid, bytes) else oid), pending,
                         set((saved or "").split(","))))
    if not stuck:
        return 0
    settled = 0
    for job_id, tasks in stuck.items():
        for task_id, pending, saved in tasks:
            for step in pending:
                label, result_name = _STEP_RESULTS.get(step, (step, None))
                if result_name in saved:
                    job_manager.record_task_finished(job_id, task_id, step=label)
                else:
                    job_manager.record_task_finished(job_id, task_id, step=label, failed=True,
                                                     reason=f"{NO_RESULT_REASON} {label}")
                settled += 1
    if settled:
        logger.warning("settled %d stuck import step(s) in %d import(s)", settled, len(stuck))
    return settled
