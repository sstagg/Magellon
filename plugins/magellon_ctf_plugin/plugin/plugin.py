"""Broker-native CTF plugin built on the SDK ``PluginBrokerRunner``.

Phase 1b (2026-05-03): the per-plugin ContextVar + daemon-loop +
``CtfBrokerRunner`` subclass are gone — :class:`PluginBrokerRunner`
now sets the active-task ContextVar on every delivery, and
:func:`magellon_sdk.runner.get_step_event_loop` is the shared
sync-from-async bridge. Back-compat shims at the bottom preserve the
old import names for one release.

Pragmatic wrapping vs. the cleaner FFT pattern:

The FFT plugin's ``execute()`` returns a typed ``FftOutput`` that
``build_fft_result`` then wraps in a TaskResultMessage. CTF can't
follow that pattern verbatim without a 200-line refactor of
``service/ctf_service.py``, which builds the full TaskResultMessage
inline (three branches: success / eval-failed / error). Instead
``CtfPluginOutput`` is a thin shell around the TaskResultMessage that
``do_ctf`` already returns; ``build_ctf_result`` unwraps it. The
compute logic stays untouched.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Type

from pydantic import BaseModel, ConfigDict

from magellon_sdk.base import PluginBase
from magellon_sdk.models import (
    PluginInfo,
    TaskMessage,
    TaskResultMessage,
)
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import CtfInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import current_task, emit_step, get_step_event_loop

from service.ctf_service import do_ctf
from service.step_events import (
    STEP_NAME,
    get_publisher,
    safe_emit_completed,
    safe_emit_failed,
    safe_emit_progress,
    safe_emit_started,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output wrapper
# ---------------------------------------------------------------------------

class CtfPluginOutput(BaseModel):
    """Pydantic shell carrying the TaskResultMessage that ``do_ctf`` builds."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    result_dto: TaskResultMessage


# ---------------------------------------------------------------------------
# CtfPlugin
# ---------------------------------------------------------------------------

class CtfPlugin(PluginBase[CtfInput, CtfPluginOutput]):
    """Broker-native CTF plugin.

    ``execute()`` is sync — invoked from the binder's pika consumer
    thread. ``do_ctf`` is async, so we bridge via the SDK's daemon
    loop. Step events follow the same best-effort pattern as the rest
    of the plugin: a failed emit must never abort the CTF compute.
    """

    capabilities = [
        Capability.CPU_INTENSIVE,
        Capability.IDEMPOTENT,
    ]
    supported_transports = [
        Transport.RMQ,
        Transport.NATS,
        Transport.HTTP,
    ]
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = ResourceHints(
        memory_mb=1_000, cpu_cores=1, typical_duration_seconds=10.0,
    )
    tags = ["ctf", "imaging"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="CTF Plugin",
            version="1.0.2",
            developer="Behdad Khoshbin b.khoshbin@gmail.com & Puneeth Reddy",
            description="Defocus/astigmatism estimation via the ctffind4 binary",
        )

    @classmethod
    def input_schema(cls) -> Type[CtfInput]:
        return CtfInput

    @classmethod
    def output_schema(cls) -> Type[CtfPluginOutput]:
        return CtfPluginOutput

    # ------------------------------------------------------------------
    # Step-event helper — resolves publisher off the SDK daemon loop.
    # ------------------------------------------------------------------

    def _publisher(self):
        loop = get_step_event_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(get_publisher(), loop)
            return future.result(timeout=15.0)
        except Exception:
            logger.exception("step-event publisher init failed (non-fatal)")
            return None

    # ------------------------------------------------------------------
    # Core execute
    # ------------------------------------------------------------------

    def execute(
        self,
        input_data: CtfInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> CtfPluginOutput:
        task = current_task()
        if task is None:
            # Direct call without the runner setting context — happens
            # in unit tests. Plugin tests that want execute() should
            # use ``magellon_sdk.runner.set_active_task`` to populate
            # the var first.
            raise RuntimeError(
                "CtfPlugin.execute called outside PluginBrokerRunner context. "
                "Use magellon_sdk.runner.set_active_task in tests."
            )

        publisher = self._publisher()
        job_id, task_id = task.job_id, task.id
        emit_step(safe_emit_started(publisher, job_id=job_id, task_id=task_id))
        try:
            emit_step(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=10.0, message="running ctffind",
            ))
            # do_ctf is async — bridge via the SDK daemon loop.
            future = asyncio.run_coroutine_threadsafe(do_ctf(task), get_step_event_loop())
            result_dto: TaskResultMessage = future.result()

            emit_step(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=85.0, message="publishing result",
            ))
            emit_step(safe_emit_completed(publisher, job_id=job_id, task_id=task_id))
            return CtfPluginOutput(result_dto=result_dto)
        except Exception as exc:
            emit_step(safe_emit_failed(
                publisher, job_id=job_id, task_id=task_id, error=str(exc),
            ))
            raise


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------

def build_ctf_result(task: TaskMessage, output: CtfPluginOutput) -> TaskResultMessage:
    """Unwrap the CtfPluginOutput shell. ``do_ctf`` already built the
    full TaskResultMessage inside; this hands it to the runner."""
    return output.result_dto


# ---------------------------------------------------------------------------
# Back-compat shims — Phase 1b absorbed these into the SDK runner.
# Remove in 2026-Q3 when downstream callers (main.py, tests) have
# migrated.
# ---------------------------------------------------------------------------

from magellon_sdk.runner import PluginBrokerRunner as CtfBrokerRunner  # noqa: E402
from magellon_sdk.runner.active_task import current_task as get_active_task  # noqa: E402
from magellon_sdk.runner.active_task import (  # noqa: E402,F401
    _active_task,
    get_step_event_loop as _get_loop,
)


__all__ = [
    "CtfBrokerRunner",
    "CtfPlugin",
    "CtfPluginOutput",
    "build_ctf_result",
    "get_active_task",
]
