"""Durable, fair import queue.

Imports used to run as background threads inside the web backend: all at
once, competing with page requests for threads and database connections,
and lost on every restart. Now:

* the API **submits** an import as a row in ``import_job_queue`` (status
  ``queued``) and returns at once;
* separate **import workers** (``services/import_worker.py``, their own
  container) claim rows, run them, heartbeat while running and record the
  outcome — the web backend never runs an import itself;
* rows survive restarts of the backend and of the workers; a running import
  whose worker died is detected by its stale heartbeat and marked failed
  (an import is not safe to re-run halfway, so it is not retried);
* the next import is chosen **fairly**: from the user with the fewest
  imports running, oldest first within each user, so one person's ten
  imports don't block everyone else. Queue positions use the same order, so
  what users see is what will happen.

Claiming is a compare-and-set (``UPDATE … WHERE status='queued'``), so any
number of workers, on any number of hosts, never run the same import twice.
"""
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import update

from database import session_local
from models.sqlalchemy_models import ImageJob, ImportJobQueue

logger = logging.getLogger(__name__)

QUEUED, RUNNING, DONE, FAILED, CANCELLED = "queued", "running", "done", "failed", "cancelled"
# Stop pressed while the import was running: its worker ends it, then the
# backend removes what it created and the row becomes cancelled.
STOPPING = "stopping"
ACTIVE = (QUEUED, RUNNING, STOPPING)

# Imports one worker process runs at once (the 4 GPUs bound throughput).
MAX_CONCURRENT_IMPORTS = max(1, int(os.environ.get("MAGELLON_MAX_CONCURRENT_IMPORTS", "4")))
HEARTBEAT_SECONDS = 30
# A running import whose worker hasn't checked in for this long is dead.
STALE_AFTER = timedelta(minutes=5)

# Same names the importers give their image_job rows, so queued imports read
# (and resume in the UI) like running ones.
_JOB_NAME = {
    "leginon": "Leginon Import: {}",
    "serialem": "SerialEM Import: {}",
}


def job_name(kind: str, label: Optional[str]) -> str:
    return _JOB_NAME.get(kind, "Import: {}").format(label or "")


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------------
# Submitting and reading
# ---------------------------------------------------------------------------

def submit(job_id, kind: str, payload: dict, owner_id=None, label: Optional[str] = None) -> Optional[int]:
    """Add an import to the queue; returns its position (1 = next).

    ``label`` is the session the import creates; raises
    ``session_names.SessionNameTaken`` when that name is already used.
    """
    from services import session_names
    if label is not None:
        session_names.require_free(label)
    db = session_local()
    try:
        db.add(ImportJobQueue(
            id=str(job_id), kind=kind, label=label,
            owner_id=str(owner_id) if owner_id else None,
            payload=payload, status=QUEUED, created_at=_now(),
        ))
        db.commit()
    finally:
        db.close()
    pos = position(job_id)
    logger.warning("[import-queue] job=%s kind=%s label=%s queued at position %s", job_id, kind, label, pos)
    return pos


def get(job_id) -> Optional[ImportJobQueue]:
    db = session_local()
    try:
        row = db.get(ImportJobQueue, str(job_id))
        if row is not None:
            db.expunge(row)
        return row
    finally:
        db.close()


def _fair_order(db) -> List[ImportJobQueue]:
    """Queued imports in the order workers will start them.

    Round-robin by user, weighted by what each already has running: the
    next slot goes to the user with the fewest running imports (ties →
    whoever's oldest waiting import is older), taking that user's oldest.
    """
    queued = (db.query(ImportJobQueue)
              .filter(ImportJobQueue.status == QUEUED)
              .order_by(ImportJobQueue.created_at, ImportJobQueue.id)
              .all())
    running: Dict[Optional[str], int] = defaultdict(int)
    for (owner,) in db.query(ImportJobQueue.owner_id).filter(ImportJobQueue.status == RUNNING):
        running[owner] += 1

    per_user: Dict[Optional[str], List[ImportJobQueue]] = defaultdict(list)
    for row in queued:
        per_user[row.owner_id].append(row)

    order: List[ImportJobQueue] = []
    while per_user:
        owner = min(per_user, key=lambda u: (running[u], per_user[u][0].created_at, per_user[u][0].id))
        order.append(per_user[owner].pop(0))
        running[owner] += 1
        if not per_user[owner]:
            del per_user[owner]
    return order


def position(job_id) -> Optional[int]:
    """1-based place in line of a queued import; None once started (or unknown)."""
    db = session_local()
    try:
        for index, row in enumerate(_fair_order(db), start=1):
            if row.id == str(job_id):
                return index
        return None
    finally:
        db.close()


def stats() -> dict:
    db = session_local()
    try:
        counts = {status: 0 for status in ACTIVE}
        for (status,) in db.query(ImportJobQueue.status).filter(ImportJobQueue.status.in_(ACTIVE)):
            counts[status] += 1
        return {"running": counts[RUNNING] + counts[STOPPING], "waiting": counts[QUEUED],
                "limit": MAX_CONCURRENT_IMPORTS}
    finally:
        db.close()


def active_for_user(owner_id) -> Optional[ImportJobQueue]:
    """The user's newest queued or running import."""
    rows = all_active_for_user(owner_id)
    return rows[0] if rows else None


def all_active_for_user(owner_id) -> List[ImportJobQueue]:
    """All the user's queued or running imports, newest first."""
    db = session_local()
    try:
        rows = (db.query(ImportJobQueue)
                .filter(ImportJobQueue.owner_id == str(owner_id), ImportJobQueue.status.in_(ACTIVE))
                .order_by(ImportJobQueue.created_at.desc())
                .all())
        for row in rows:
            db.expunge(row)
        return rows
    finally:
        db.close()


def list_waiting() -> List[dict]:
    """Queued imports in start order, shaped like job-list entries."""
    db = session_local()
    try:
        return [{
            "job_id": row.id,
            "plugin_id": None,
            "name": job_name(row.kind, row.label),
            "owner_id": row.owner_id,
            "status": QUEUED,
            "progress": 0,
            "num_items": 0,
            "queued_at": row.created_at.isoformat() + "Z" if row.created_at else None,
            "started_at": None,
            "ended_at": None,
            "error": None,
            "queue_position": index,
        } for index, row in enumerate(_fair_order(db), start=1)]
    finally:
        db.close()


def list_preparing(known_ids) -> List[dict]:
    """Running imports that haven't created their job row yet (still reading
    the session), shaped like job-list entries."""
    db = session_local()
    try:
        rows = (db.query(ImportJobQueue).filter(ImportJobQueue.status == RUNNING)
                .order_by(ImportJobQueue.started_at.desc()).all())
        return [{
            "job_id": row.id,
            "plugin_id": None,
            "name": job_name(row.kind, row.label),
            "owner_id": row.owner_id,
            "status": RUNNING,
            "preparing": True,
            "progress": 0,
            "num_items": 0,
            "queued_at": row.created_at.isoformat() + "Z" if row.created_at else None,
            "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
            "ended_at": None,
            "error": None,
        } for row in rows if row.id not in known_ids]
    finally:
        db.close()


def cancel(job_id) -> bool:
    """Withdraw an import that hasn't started yet."""
    db = session_local()
    try:
        result = db.execute(
            update(ImportJobQueue)
            .where(ImportJobQueue.id == str(job_id), ImportJobQueue.status == QUEUED)
            .values(status=CANCELLED, finished_at=_now())
        )
        db.commit()
        return result.rowcount == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Worker side
# ---------------------------------------------------------------------------

def request_stop(job_id) -> bool:
    """Ask the worker running this import to end it (running → stopping)."""
    db = session_local()
    try:
        result = db.execute(update(ImportJobQueue)
                            .where(ImportJobQueue.id == str(job_id), ImportJobQueue.status == RUNNING)
                            .values(status=STOPPING))
        db.commit()
        return result.rowcount == 1
    finally:
        db.close()


def mark_stopped(job_id, message: str = "Stopped by the user.") -> None:
    """Record the import as cancelled (whatever state it was in)."""
    db = session_local()
    try:
        db.execute(update(ImportJobQueue).where(ImportJobQueue.id == str(job_id))
                   .values(status=CANCELLED, finished_at=_now(), error=message))
        db.commit()
    finally:
        db.close()


def is_stopped(job_id) -> bool:
    """Whether this job is an import the user stopped (late plugin results
    for it are dropped instead of recreating files of a deleted session)."""
    row = get(job_id)
    return row is not None and row.status in (STOPPING, CANCELLED)


def claim_next(worker: str) -> Optional[ImportJobQueue]:
    """Atomically take the next import in fair order, or None if none waits."""
    db = session_local()
    try:
        for candidate in _fair_order(db):
            now = _now()
            result = db.execute(
                update(ImportJobQueue)
                .where(ImportJobQueue.id == candidate.id, ImportJobQueue.status == QUEUED)
                .values(status=RUNNING, worker=worker, started_at=now, heartbeat_at=now)
            )
            db.commit()
            if result.rowcount == 1:
                row = db.get(ImportJobQueue, candidate.id)
                db.refresh(row)
                db.expunge(row)
                return row
            # Another worker took it (or it was cancelled) — try the next one.
        return None
    finally:
        db.close()


def heartbeat(job_id) -> None:
    db = session_local()
    try:
        db.execute(update(ImportJobQueue)
                   .where(ImportJobQueue.id == str(job_id), ImportJobQueue.status == RUNNING)
                   .values(heartbeat_at=_now()))
        db.commit()
    finally:
        db.close()


def finish(job_id, error: Optional[str] = None) -> None:
    db = session_local()
    try:
        db.execute(update(ImportJobQueue)
                   .where(ImportJobQueue.id == str(job_id), ImportJobQueue.status == RUNNING)
                   .values(status=FAILED if error else DONE, finished_at=_now(), error=error))
        db.commit()
    finally:
        db.close()


def fail_running(job_ids, message: str) -> int:
    """Mark these running imports failed, and their image_job rows too.

    An import stopped halfway is not re-run: its partial records would be
    duplicated. The user sees ``message`` and imports again.
    """
    from uuid import UUID

    db = session_local()
    try:
        rows = (db.query(ImportJobQueue)
                .filter(ImportJobQueue.id.in_([str(j) for j in job_ids]), ImportJobQueue.status == RUNNING)
                .all())
        for row in rows:
            row.status, row.finished_at, row.error = FAILED, _now(), message
            job = db.get(ImageJob, UUID(row.id))
            if job is not None and job.status_id in (0, 1):
                job.status_id = 3
                processed = dict(job.processed_json or {})
                processed.setdefault("error", message)
                job.processed_json = processed
        db.commit()
        return len(rows)
    finally:
        db.close()


def recover_stale() -> int:
    """Fail running imports whose worker stopped heartbeating (crash, kill,
    host restart)."""
    cutoff = _now() - STALE_AFTER
    db = session_local()
    try:
        stale = [row_id for (row_id,) in db.query(ImportJobQueue.id)
                 .filter(ImportJobQueue.status == RUNNING, ImportJobQueue.heartbeat_at < cutoff)]
    finally:
        db.close()
    if not stale:
        return 0
    count = fail_running(stale, "The import worker stopped while this import was running; please import again.")
    logger.warning("[import-queue] marked %d stale running import(s) failed", count)
    return count


def running_job_ids() -> List[str]:
    """Ids of imports a live worker is running (used to spare them at backend startup)."""
    cutoff = _now() - STALE_AFTER
    db = session_local()
    try:
        return [row_id for (row_id,) in db.query(ImportJobQueue.id)
                .filter(ImportJobQueue.status == RUNNING, ImportJobQueue.heartbeat_at >= cutoff)]
    finally:
        db.close()
