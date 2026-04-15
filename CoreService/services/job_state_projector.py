"""Project step-event envelopes onto JobManager state writes.

Sibling of :class:`JobEventWriter`. The writer is the audit log; the
projector is the *state machine*. They run side-by-side off the same
envelope stream — writer appends a ``job_event`` row, projector flips
``image_job`` / ``image_job_task`` rows to the correct status.

Why split them?

  - Writer is pure append + dedup; safe to retry, no business logic.
  - Projector applies non-trivial logic (count completions, finalize
    when all tasks done, fail-fast on first failure). Its writes are
    *idempotent* per envelope but not order-independent, so it lives
    behind the same downstream hook the writer uses.

Wired by the step-event forwarders (NATS + RMQ) as ``downstream``,
chained before the Socket.IO emit so the DB is up-to-date by the
time a client receives the live event. (Order matters because a UI
may then call GET /jobs/<id> on receipt and expect fresh state.)

Mapping (envelope.type → JobManager call)
-----------------------------------------

  magellon.step.started     -> mark_task_running(task_id)
                               + first-time only: mark_running(job_id)
  magellon.step.progress    -> no DB write (live-only by design)
  magellon.step.completed   -> mark_task_completed(task_id)
                               + record_task_completion(job_id, task_id)
                               + if completed==expected: complete_job(job_id)
  magellon.step.failed      -> mark_task_failed(task_id)
                               + fail_job(job_id)   # fail-fast policy

Failures inside the projector never re-raise — a poisoned envelope
must not block the rest of the chain (audit log + Socket.IO). They're
logged at error level for operator triage.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from magellon_sdk.envelope import Envelope
from magellon_sdk.events import (
    STEP_COMPLETED,
    STEP_FAILED,
    STEP_PROGRESS,
    STEP_STARTED,
)

from services.job_manager import job_manager

logger = logging.getLogger(__name__)


class StepEventJobStateProjector:
    """Translates step envelopes into JobManager state transitions.

    Stateless apart from the JobManager singleton it delegates to.
    Construct once per process (or use :data:`project_step_event` —
    the module-level convenience binding for the default singleton).
    """

    def __init__(self, manager=job_manager) -> None:
        self.manager = manager

    async def __call__(self, envelope: Envelope[Any]) -> None:
        """Async signature so the forwarder's downstream chain can
        ``await`` us alongside the Socket.IO emit. The actual JobManager
        calls are sync — short writes, fine on the event loop."""
        try:
            self._project(envelope)
        except Exception:
            # Never let a bad envelope poison the chain.
            logger.exception(
                "StepEventJobStateProjector: failed to project envelope %s "
                "(type=%s) — non-fatal, audit log already written",
                envelope.id, envelope.type,
            )

    def _project(self, envelope: Envelope[Any]) -> None:
        if envelope.type == STEP_PROGRESS:
            return  # live-only

        data = envelope.data if isinstance(envelope.data, dict) else {}
        job_id = _str_or_none(data.get("job_id"))
        task_id = _str_or_none(data.get("task_id"))

        if job_id is None:
            logger.debug("Projector: dropping %s — no job_id", envelope.type)
            return

        if envelope.type == STEP_STARTED:
            if task_id:
                self.manager.mark_task_running(task_id)
            # mark_running on the parent job is idempotent — it no-ops
            # if the job already left QUEUED. So it's safe to call on
            # every started event without tracking "first time".
            try:
                self.manager.mark_running(job_id)
            except LookupError:
                logger.warning("Projector: job %s missing — started event ignored", job_id)
            return

        if envelope.type == STEP_COMPLETED:
            if task_id:
                result = data.get("result") or {
                    "output_files": data.get("output_files") or [],
                }
                self.manager.mark_task_completed(task_id, result=result)

            try:
                progress = self.manager.record_task_completion(job_id, task_id or "")
            except LookupError:
                logger.warning("Projector: job %s missing — completed event ignored", job_id)
                return

            if (
                progress["expected"] > 0
                and progress["completed"] >= progress["expected"]
            ):
                # Aggregate result: list of task results would balloon the
                # row; just record the count + the "all tasks done" marker.
                self.manager.complete_job(
                    job_id,
                    result={
                        "task_count": progress["expected"],
                        "completed_tasks": progress["completed"],
                    },
                    num_items=progress["expected"],
                )
            return

        if envelope.type == STEP_FAILED:
            if task_id:
                err = (data.get("error") or {}).get("message") or "task failed"
                self.manager.mark_task_failed(task_id, error=str(err))
            err = (data.get("error") or {}).get("message") or "task failed"
            try:
                self.manager.fail_job(job_id, error=str(err))
            except LookupError:
                logger.warning("Projector: job %s missing — failed event ignored", job_id)
            return


def _str_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# Default singleton bound to the module-level JobManager.
project_step_event = StepEventJobStateProjector()


__all__ = ["StepEventJobStateProjector", "project_step_event"]
