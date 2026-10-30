"""Import tasks whose plugin steps couldn't start.

A step that never reaches its plugin (a movie that isn't there, a dispatch
the broker refused) is never reported back, so the import would wait for it
forever. Importers record it here instead: the task fails now with the
reason, or, if another step of it is still running, the reason is kept on the
job and the task finishes when that step reports. Each kind of problem is
also shown once per import in the browsers' Logs panel.
"""
import logging

from models.sqlalchemy_models import ImageJobTask

logger = logging.getLogger(__name__)

STATUS_COMPLETED = 2
STATUS_FAILED = 3


def finish_task(task_dto, problems=()) -> None:
    """Finish a task no plugin will report: completed, or failed with the first
    of ``problems`` ((step, reason) pairs) when a step couldn't start."""
    from database import session_local
    from services.job_manager import job_manager

    task_id, job_id = getattr(task_dto, "task_id", None), getattr(task_dto, "job_id", None)
    if not task_id or not job_id:
        return
    failed = bool(problems)
    db = session_local()
    try:
        db.query(ImageJobTask).filter(ImageJobTask.oid == task_id).update(
            {ImageJobTask.status_id: STATUS_FAILED if failed else STATUS_COMPLETED},
            synchronize_session=False)
        db.commit()
    finally:
        db.close()
    step, reason = problems[0] if failed else (None, None)
    try:
        job_manager.record_task_finished(str(job_id), str(task_id), failed=failed, step=step, reason=reason)
    except LookupError:
        pass


def record_problem(task_dto, step: str, reason: str) -> None:
    """Keep the reason a step couldn't start while the task's other steps run on."""
    from services.job_manager import job_manager

    task_id, job_id = getattr(task_dto, "task_id", None), getattr(task_dto, "job_id", None)
    if not task_id or not job_id:
        return
    try:
        job_manager.record_task_problem(str(job_id), str(task_id), step=step, reason=reason)
    except LookupError:
        pass


def log_problem(logged: set, session: str, image: str, step: str, reason: str) -> None:
    """Show a step that couldn't start in the Logs panel, once per kind of
    problem in this import (``logged`` is the import's own set). Reasons that
    name a file are grouped by the text before the colon."""
    key = (step, reason.split(":")[0])
    if key in logged:
        logger.debug("%s not started for %s: %s", step, image, reason)
        return
    logged.add(key)
    logger.warning("%s not started for %s: %s", step, image, reason)
    try:
        from services.import_progress import publish_log
        publish_log("error", step.lower(),
                    f"{step} couldn't start for {image} in {session}: {reason} "
                    "(other images with the same problem aren't listed again)")
    except Exception:
        logger.debug("could not send the problem to the Logs panel", exc_info=True)


def report(task_dto, problems, *, sent: bool, logged: set, session: str) -> None:
    """Record ``problems`` for a task: it fails now if nothing was sent to a
    plugin (and finishes completed if there were no problems either);
    otherwise the reasons wait on the job for its running steps."""
    image = getattr(task_dto, "image_name", None) or getattr(task_dto, "file_name", None) or "an image"
    for step, reason in problems:
        log_problem(logged, session, image, step, reason)
    if not sent:
        finish_task(task_dto, problems)
    else:
        for step, reason in problems:
            record_problem(task_dto, step, reason)
