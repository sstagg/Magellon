"""Delete a Magellon session: its database records and its files.

Used by "Delete session" and by stopping an import (an import owns the
session it creates, see services/session_names.py). Removes, for one session:

* database rows: job events, artifacts, image metadata (CTF, MotionCor,
  particle picks, ...), tasks, images, atlases, sample materials, the
  session's jobs and pipeline runs, and the session itself;
* files: the session folder in MAGELLON_HOME_DIR, and the scratch folders in
  the jobs directory named after its tasks and images.

Research storage (/gpfs) is never touched: it is mounted read-only and
nothing here points into it.
"""
import logging
import os
import shutil
from typing import Optional

from sqlalchemy import false, or_

from config import MAGELLON_HOME_DIR, MAGELLON_JOBS_DIR
from database import session_local
from models.sqlalchemy_models import (
    Artifact, Atlas, Image, ImageJob, ImageJobTask, ImageMetaData, JobEvent,
    Msession, PipelineRun, SampleMaterial,
)

logger = logging.getLogger(__name__)


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return path != root and path.startswith(root + os.sep)


def find_session(name: str) -> Optional[Msession]:
    db = session_local()
    try:
        session = db.query(Msession).filter(Msession.name == name).first()
        if session is not None:
            db.expunge(session)
        return session
    finally:
        db.close()


def other_jobs(session_id, job_id) -> int:
    """How many jobs besides ``job_id`` wrote into this session."""
    db = session_local()
    try:
        return (db.query(ImageJob).filter(ImageJob.msession_id == str(session_id), ImageJob.oid != job_id).count())
    finally:
        db.close()


def delete_session(session_id) -> dict:
    """Remove one session's records and files; returns counts."""
    db = session_local()
    try:
        session = db.get(Msession, session_id)
        if session is None:
            return {"deleted": False}
        name = session.name
        # image_job / artifact / pipeline_run keep the session id as text.
        sid_text = str(session_id)
        job_ids = [j for (j,) in db.query(ImageJob.oid).filter(ImageJob.msession_id == sid_text)]
        image_ids = [i for (i,) in db.query(Image.oid).filter(Image.session_id == session_id)]
        def _in(column, ids):
            return column.in_(ids) if ids else false()

        task_ids = [t for (t,) in db.query(ImageJobTask.oid).filter(
            or_(_in(ImageJobTask.job_id, job_ids), _in(ImageJobTask.image_id, image_ids)))]

        counts = {}
        counts["events"] = db.query(JobEvent).filter(
            or_(_in(JobEvent.job_id, job_ids), _in(JobEvent.task_id, task_ids))).delete(synchronize_session=False)
        counts["artifacts"] = db.query(Artifact).filter(or_(
            Artifact.msession_id == sid_text, _in(Artifact.producing_job_id, job_ids),
            _in(Artifact.producing_task_id, task_ids))).delete(synchronize_session=False)
        counts["metadata"] = db.query(ImageMetaData).filter(or_(
            _in(ImageMetaData.image_id, image_ids), _in(ImageMetaData.job_id, job_ids),
            _in(ImageMetaData.task_id, task_ids))).delete(synchronize_session=False)
        counts["tasks"] = db.query(ImageJobTask).filter(_in(ImageJobTask.oid, task_ids)).delete(synchronize_session=False)
        # Images point at their parent image and their atlas; unlink first.
        db.query(Image).filter(Image.session_id == session_id).update(
            {Image.parent_id: None, Image.atlas_id: None}, synchronize_session=False)
        counts["images"] = db.query(Image).filter(Image.session_id == session_id).delete(synchronize_session=False)
        counts["atlases"] = db.query(Atlas).filter(Atlas.session_id == session_id).delete(synchronize_session=False)
        db.query(SampleMaterial).filter(SampleMaterial.session == session_id).delete(synchronize_session=False)
        run_ids = [r for (r,) in db.query(ImageJob.parent_run_id)
                   .filter(_in(ImageJob.oid, job_ids), ImageJob.parent_run_id.isnot(None)).distinct()]
        counts["jobs"] = db.query(ImageJob).filter(_in(ImageJob.oid, job_ids)).delete(synchronize_session=False)
        db.query(PipelineRun).filter(or_(PipelineRun.msession_id == sid_text, _in(PipelineRun.oid, run_ids))) \
            .delete(synchronize_session=False)
        db.query(Msession).filter(Msession.oid == session_id).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # Files, once the records are gone.
    removed_dirs = 0
    home = os.path.join(MAGELLON_HOME_DIR, name)
    if name and _inside(home, MAGELLON_HOME_DIR) and os.path.isdir(home):
        shutil.rmtree(home, ignore_errors=True)
        removed_dirs += 1
    jobs_dir = MAGELLON_JOBS_DIR or "/jobs"
    for scratch_id in {str(i) for i in task_ids + image_ids}:
        path = os.path.join(jobs_dir, scratch_id)
        if _inside(path, jobs_dir) and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
            removed_dirs += 1
    counts["folders"] = removed_dirs
    logger.warning("[session-delete] %s: %s", name, counts)
    return {"deleted": True, "name": name, **counts}
