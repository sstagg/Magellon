"""Async-job routes for the plugins router.

Submit (single / batch) plus the job list / detail / cancel surface.
Dispatch mechanics live in :mod:`plugins.dispatch_service`.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from services.job_manager import job_manager

from plugins.dispatch_service import _submit_broker_batch, _submit_broker_job
from plugins.registry_service import _find_broker_plugin
from plugins.schemas import BatchSubmitRequest, JobSubmitRequest

jobs_router = APIRouter()


# ---------------------------------------------------------------------------
# Job submission — single and batch
# ---------------------------------------------------------------------------

@jobs_router.post("/{plugin_id:path}/jobs", summary="Submit one plugin job (async)")
async def submit_job(plugin_id: str, request: JobSubmitRequest, sid: str | None = None):
    """Dispatch one job to a broker plugin via ``bus.tasks.send``.

    Post-PI-6 there are no in-process plugins; every dispatch flows
    through the bus. The plugin's runner consumes the task and
    publishes the result + step events back. ``job_manager`` rows
    track lifecycle the same way regardless of where the plugin runs.
    """
    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_job(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@jobs_router.post("/{plugin_id:path}/jobs/batch", summary="Submit a batch of plugin jobs (one per input)")
async def submit_batch(plugin_id: str, request: BatchSubmitRequest, sid: str | None = None):
    if request.image_ids is not None and len(request.image_ids) != len(request.inputs):
        raise HTTPException(
            status_code=422,
            detail="image_ids length must match inputs length when provided",
        )

    broker = _find_broker_plugin(plugin_id)
    if broker is not None:
        return await _submit_broker_batch(plugin_id, broker, request)
    raise HTTPException(status_code=404, detail=f"Plugin {plugin_id} not found")


@jobs_router.get("/jobs", summary="List plugin jobs")
async def list_all_jobs(plugin_id: Optional[str] = None, limit: int = 100):
    jobs = job_manager.list_jobs(plugin_id=plugin_id, limit=limit)
    _add_task_progress(jobs)
    _add_session_names(jobs)
    if plugin_id is None:
        # Imports still waiting in the queue, or still reading their session,
        # have no job row yet; list them too so the Jobs panel shows the
        # whole picture.
        from services import import_queue
        known = {job["job_id"] for job in jobs}
        # Long-running jobs older than the newest `limit` stay listed.
        older_active = [job for job in job_manager.list_active() if job["job_id"] not in known]
        _add_task_progress(older_active)
        _add_session_names(older_active)
        jobs = older_active + jobs
        known |= {job["job_id"] for job in older_active}
        waiting = import_queue.list_waiting() + import_queue.list_preparing(known)
        _add_owner_names(waiting)
        jobs = waiting + jobs
    return jobs


def _add_session_names(jobs: list) -> None:
    """Name the session each job wrote into (for the Jobs panel's delete),
    and who owns the job (the Jobs panel shows each user their own)."""
    import uuid

    from database import session_local
    from models.sqlalchemy_models import ImageJob, Msession

    if not jobs:
        return
    with session_local() as db:
        rows = {oid: (sid, user) for oid, sid, user in
                db.query(ImageJob.oid, ImageJob.msession_id, ImageJob.user_id)
                .filter(ImageJob.oid.in_([uuid.UUID(job["job_id"]) for job in jobs]))}
        ids = [uuid.UUID(sid) for sid, _ in rows.values() if sid]
        sessions = {oid: (name, owner) for oid, name, owner in
                    db.query(Msession.oid, Msession.name, Msession.user_id).filter(Msession.oid.in_(ids))} if ids else {}
    for job in jobs:
        sid, job_user = rows.get(uuid.UUID(job["job_id"]), (None, None))
        name, owner = sessions.get(uuid.UUID(sid), (None, None)) if sid else (None, None)
        job["session_name"] = name
        # Imports belong to their session's owner; plugin jobs (picks) to
        # the user who started them. Besides admins, they may stop / delete it.
        owner = owner or job_user
        job["owner_id"] = str(owner) if owner else None
    _add_owner_names(jobs)


def _add_owner_names(jobs: list) -> None:
    """Owner usernames, shown to admins viewing everyone's jobs."""
    import uuid

    from database import session_local
    from models.sqlalchemy_models import SysSecUser

    owners = {str(job["owner_id"]) for job in jobs if job.get("owner_id")}
    names = {}
    if owners:
        with session_local() as db:
            names = {str(oid): username for oid, username in
                     db.query(SysSecUser.oid, SysSecUser.USERNAME)
                     .filter(SysSecUser.oid.in_([uuid.UUID(o) for o in owners]))}
    for job in jobs:
        if job.get("owner_id"):
            job["owner_id"] = str(job["owner_id"])
        job["owner_name"] = names.get(job.get("owner_id"))


def _add_task_progress(jobs: list) -> None:
    """Give running jobs their task counts, progress and estimated time left.

    The estimate assumes the remaining tasks take as long, on average, as the
    finished ones have so far (elapsed time per finished task).
    """
    import uuid
    from datetime import datetime, timezone

    from sqlalchemy import func

    from database import session_local
    from models.sqlalchemy_models import ImageJobTask

    running = {job["job_id"]: job for job in jobs if job.get("status") == "running"}
    if not running:
        return
    with session_local() as db:
        rows = (db.query(ImageJobTask.job_id, ImageJobTask.status_id, func.count(ImageJobTask.oid))
                .filter(ImageJobTask.job_id.in_([uuid.UUID(i) for i in running]))
                .group_by(ImageJobTask.job_id, ImageJobTask.status_id).all())
    counts: dict = {}
    for job_id, status_id, count in rows:
        total, done = counts.get(str(job_id), (0, 0))
        counts[str(job_id)] = (total + count, done + (count if status_id in (2, 3, 4) else 0))
    now = datetime.now(timezone.utc)
    for job_id, (total, done) in counts.items():
        job = running[job_id]
        job["tasks_total"], job["tasks_done"] = total, done
        job["progress"] = round(100 * done / total) if total else 0
        started = job.get("started_at")
        if started and 0 < done < total:
            elapsed = (now - datetime.fromisoformat(started.replace("Z", "+00:00"))).total_seconds()
            job["eta_seconds"] = round(elapsed / done * (total - done))
    _add_step_results(running)


# Plugin steps of an import, with the metadata each successful result saves.
_IMPORT_STEPS = (("CTF", "CTF Data"), ("MotionCor", "MotionCor Meta Data"))


def _add_step_results(running: dict) -> None:
    """Per plugin step of each running import: how many images it applies to,
    how many succeeded and failed so far, and the most common failure reason
    — so a step failing for every image shows up while the import runs."""
    import uuid
    from collections import Counter

    from sqlalchemy import text

    from database import session_local
    from models.sqlalchemy_models import ImageJob

    imports = [job_id for job_id, job in running.items() if "Import:" in (job.get("name") or "")]
    if not imports:
        return
    with session_local() as db:
        for job_id in imports:
            params = {"job": uuid.UUID(job_id).bytes}
            totals = db.execute(text(
                "SELECT SUM(t.frame_name IS NOT NULL AND t.frame_name <> ''),"
                " SUM(i.pixel_size IS NOT NULL AND i.pixel_size * 1e10 <= 5)"
                " FROM image_job_task t JOIN image i ON i.oid = t.image_id WHERE t.job_id = :job"),
                params).one()
            ok = dict(db.execute(text(
                "SELECT m.name, COUNT(DISTINCT m.image_id) FROM image_meta_data m"
                " JOIN image_job_task t ON t.image_id = m.image_id"
                " WHERE t.job_id = :job AND m.name IN ('CTF Data', 'MotionCor Meta Data') GROUP BY m.name"),
                params).all())
            job = db.query(ImageJob).filter(ImageJob.oid == uuid.UUID(job_id)).first()
            failures = ((job.processed_json or {}).get("failed_tasks") or {}) if job else {}
            by_step = Counter((f.get("step") or "").lower() for f in failures.values())
            steps = []
            for (step, meta_name), total in zip(_IMPORT_STEPS, (totals[1], totals[0])):
                failed = by_step.get(step.lower(), 0)
                if not total and not failed:
                    continue
                reasons = Counter(f.get("reason") for f in failures.values()
                                  if (f.get("step") or "").lower() == step.lower())
                steps.append({"step": step, "total": int(total or 0), "ok": int(ok.get(meta_name, 0)),
                              "failed": failed,
                              "reason": reasons.most_common(1)[0][0] if reasons else None})
            running[job_id]["steps"] = steps


@jobs_router.get("/jobs/{job_id}", summary="Get plugin job detail")
async def get_any_job(job_id: str):
    try:
        return job_manager.get_job(job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")


@jobs_router.delete("/jobs/{job_id}", summary="Request cancellation of a running plugin job")
async def cancel_any_job(job_id: str):
    """Cooperative cancel: flags the job so the plugin stops at its next
    progress checkpoint. Terminal jobs are untouched; the current envelope
    is returned so the caller can observe the outcome."""
    try:
        envelope = job_manager.get_job(job_id, include_result=False)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")

    if envelope["status"] in ("completed", "failed", "cancelled"):
        return envelope

    job_manager.request_cancel(job_id)
    return {**envelope, "cancel_requested": True}
