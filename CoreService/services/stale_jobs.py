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
