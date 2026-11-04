"""Nightly clean-up of the jobs scratch directory.

Plugins (MotionCor, CTF, ...) work in MAGELLON_JOBS_DIR — MotionCor in
``<jobs>/<image id>/``, CTF in ``<jobs>/<task id>/`` — and the backend moves
each task's output files into the session folder under MAGELLON_HOME_DIR
when its result arrives. What stays in the jobs directory is scratch (a copy
of the gain reference per task, intermediate sums, logs): ~380 MB per movie.

Once a night (``MAGELLON_JOBS_CLEANUP_HOUR_UTC``, default 06:00 UTC =
2:00 AM US Eastern) the import worker removes every folder there, except:

* folders named after a task, or an image, whose task is still queued or
  running — that work isn't finished;
* folders with anything modified in the last ``QUIET_HOURS`` — a second
  guard for work in flight.

If the database can't be read, that night's clean-up is skipped: without
knowing what is active nothing is deleted.

The same run removes the logs of Jobs tab tests from <home>/testing, which
aren't kept: see clean_test_logs.
"""
import logging
import os
import shutil
import time
from datetime import datetime
from typing import Optional, Set

logger = logging.getLogger(__name__)

CLEANUP_HOUR_UTC = int(os.environ.get("MAGELLON_JOBS_CLEANUP_HOUR_UTC", "6")) % 24
QUIET_HOURS = 2
# Where Jobs tab tests keep their run logs (core/motioncor_test_result_processor.py).
TEST_LOGS_DIR = "testing"
TEST_LOGS = (("fao", "_motioncor.log"), ("ctf", "_ctffind.log"))

_last_run_date: Optional[str] = None


def _jobs_dir() -> str:
    from config import app_settings
    return app_settings.directory_settings.MAGELLON_JOBS_DIR or "/jobs"


def _active_ids() -> Set[str]:
    """Task ids and image ids of tasks that are queued or running."""
    from database import session_local
    from models.sqlalchemy_models import ImageJobTask

    db = session_local()
    try:
        ids: Set[str] = set()
        for oid, image_id in (db.query(ImageJobTask.oid, ImageJobTask.image_id)
                              .filter(ImageJobTask.status_id.in_((0, 1)))):
            ids.add(str(oid))
            if image_id:
                ids.add(str(image_id))
        return ids
    finally:
        db.close()


def _newest_change(path: str) -> float:
    newest = os.lstat(path).st_mtime
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                newest = max(newest, os.lstat(os.path.join(root, name)).st_mtime)
            except OSError:
                pass
    return newest


def _size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def clean(now: Optional[float] = None) -> dict:
    """Remove finished scratch folders now; returns what was done."""
    now = now or time.time()
    jobs_dir = _jobs_dir()
    active = _active_ids()            # raises if the DB is unreachable → nothing deleted
    cutoff = now - QUIET_HOURS * 3600
    removed = kept_active = kept_recent = freed = 0
    for entry in os.scandir(jobs_dir):
        path = entry.path
        try:
            if entry.name in active:
                kept_active += 1
                continue
            if _newest_change(path) >= cutoff:
                kept_recent += 1
                continue
            size = _size(path) if entry.is_dir(follow_symlinks=False) else entry.stat(follow_symlinks=False).st_size
            if entry.is_dir(follow_symlinks=False):
                shutil.rmtree(path)
            else:
                os.remove(path)
            removed += 1
            freed += size
        except OSError:
            logger.warning("jobs clean-up: could not remove %s", path, exc_info=True)
    summary = {"removed": removed, "freed_gb": round(freed / 1e9, 2),
               "kept_active": kept_active, "kept_recent": kept_recent}
    logger.warning("[jobs-cleanup] %s: removed %d folder(s), freed %.2f GB; kept %d active, %d recently changed",
                   jobs_dir, removed, freed / 1e9, kept_active, kept_recent)
    return summary


def _testing_is_a_session() -> bool:
    from database import session_local
    from models.sqlalchemy_models import Msession

    db = session_local()
    try:
        return db.query(Msession.oid).filter(Msession.name == TEST_LOGS_DIR).first() is not None
    finally:
        db.close()


def clean_test_logs(now: Optional[float] = None) -> dict:
    """Remove Jobs tab test logs from <home>/testing/<fao or ctf>/<image>/.

    Only run logs and the folders they leave empty go, and nothing if a real
    session has been named "testing": its results would live in the same folder."""
    from config import MAGELLON_HOME_DIR

    if _testing_is_a_session():      # raises if the DB is unreachable → nothing deleted
        logger.warning("[jobs-cleanup] a session is named '%s': its folder was left alone", TEST_LOGS_DIR)
        return {"removed": 0, "kept_recent": 0}
    cutoff = (now or time.time()) - QUIET_HOURS * 3600
    removed = kept_recent = 0
    for sub_dir, suffix in TEST_LOGS:
        parent = os.path.join(MAGELLON_HOME_DIR, TEST_LOGS_DIR, sub_dir)
        if not os.path.isdir(parent):
            continue
        for entry in os.scandir(parent):
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if _newest_change(entry.path) >= cutoff:
                    kept_recent += 1
                    continue
                for name in os.listdir(entry.path):
                    if name.endswith(suffix):
                        os.remove(os.path.join(entry.path, name))
                        removed += 1
                if not os.listdir(entry.path):
                    os.rmdir(entry.path)
            except OSError:
                logger.warning("test log clean-up: could not remove %s", entry.path, exc_info=True)
    logger.warning("[jobs-cleanup] test logs: removed %d, kept %d recently changed", removed, kept_recent)
    return {"removed": removed, "kept_recent": kept_recent}


def run_if_due() -> Optional[dict]:
    """Call often (every minute); cleans once per night at CLEANUP_HOUR_UTC."""
    global _last_run_date
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    if now.hour != CLEANUP_HOUR_UTC or _last_run_date == today:
        return None
    _last_run_date = today
    try:
        clean_test_logs()
    except Exception:
        logger.warning("[jobs-cleanup] test logs skipped tonight", exc_info=True)
    try:
        return clean()
    except Exception:
        logger.warning("[jobs-cleanup] skipped tonight: could not determine active tasks", exc_info=True)
        return None
