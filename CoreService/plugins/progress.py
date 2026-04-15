"""Progress reporting for plugin executions.

Plugins run in a worker thread via ``run_in_executor``. To stream mid-flight
progress back to the Socket.IO client they receive a ``ProgressReporter``.
The reporter persists each update via :class:`JobManager` and marshals the
Socket.IO emit back onto the running asyncio loop.

Plugins call ``reporter.report(percent, message)`` at logical stage
boundaries; the infrastructure handles dedup, DB persistence, and cross-
thread event emission. In-process tests and plugins that don't want a
reporter use :class:`NullReporter`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

# ProgressReporter, NullReporter, and JobCancelledError are the plugin-
# facing contract and live in the SDK. Re-exported here so existing
# CoreService call sites keep working unchanged.
from magellon_sdk.progress import (  # noqa: F401  (re-export)
    JobCancelledError,
    NullReporter,
    ProgressReporter,
)

from services.job_manager import job_manager

logger = logging.getLogger(__name__)


class JobReporter:
    """Forwards progress into the job row and out over Socket.IO.

    Safe to call from any thread: the Socket.IO coroutines are scheduled
    onto the supplied asyncio loop via ``run_coroutine_threadsafe`` and
    DB writes happen directly (JobManager opens its own session per call).
    """

    def __init__(
        self,
        *,
        job_id: str,
        sid: Optional[str],
        plugin_label: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._job_id = job_id
        self._sid = sid
        self._plugin_label = plugin_label
        self._loop = loop
        self._last_percent = -1

    def report(self, percent: int, message: Optional[str] = None) -> None:
        # Cooperative cancellation: raise as soon as we learn the user asked
        # to stop. Plugins that call report() at stage boundaries will bail
        # within one stage; pure-compute stretches without reports can't be
        # interrupted by this alone (documented tradeoff).
        if job_manager.is_cancelled(self._job_id):
            raise JobCancelledError(f"Job {self._job_id} cancelled")

        clamped = max(0, min(100, int(percent)))
        # Skip no-op updates; an explicit message still fires so logs land.
        if clamped == self._last_percent and not message:
            return
        self._last_percent = clamped

        try:
            envelope = job_manager.update_progress(self._job_id, progress=clamped)
        except Exception:
            logger.exception("Progress update failed for job %s", self._job_id)
            return

        self._emit_job_update(envelope)
        if message:
            self.log("info", message)

    def log(self, level: str, message: str) -> None:
        from core.socketio_server import emit_log

        coro = emit_log(level, self._plugin_label, message)
        asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _emit_job_update(self, envelope: dict) -> None:
        from core.socketio_server import emit_job_update

        coro = emit_job_update(self._sid, envelope)
        asyncio.run_coroutine_threadsafe(coro, self._loop)
