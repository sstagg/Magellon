"""Broker-native MotionCor plugin built on the SDK ``PluginBrokerRunner``.

Phase 1b (2026-05-03): mirrors the CTF / FFT / topaz cutovers — drop
the per-plugin ContextVar + daemon-loop + ``MotioncorBrokerRunner``
subclass; use the SDK helpers from :mod:`magellon_sdk.runner.active_task`.
Back-compat shims preserve the old import names for one release.

Same pragmatic wrapper pattern as CTF — ``MotioncorPluginOutput`` is a
thin Pydantic shell carrying the ``TaskResultMessage`` that
``do_motioncor`` already builds inline; refactoring the 200-line
async compute to return a typed ``MotionCorOutput`` would be a
separate, larger PR.
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
from magellon_sdk.models.tasks import MotionCorInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import current_task, emit_step, get_step_event_loop

from service.motioncor_service import do_motioncor
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

class MotioncorPluginOutput(BaseModel):
    """Pydantic shell carrying the TaskResultMessage that ``do_motioncor`` builds."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    result_dto: TaskResultMessage


# ---------------------------------------------------------------------------
# MotioncorPlugin
# ---------------------------------------------------------------------------

class MotioncorPlugin(PluginBase[MotionCorInput, MotioncorPluginOutput]):
    """Broker-native MotionCor plugin.

    ``execute()`` is sync — invoked from the binder's consumer thread.
    ``do_motioncor`` is async, bridged via the SDK daemon loop. Step
    events follow the same best-effort pattern: a failed emit must
    never abort the compute. MotionCor3 runs ~3 minutes typical, so
    we emit coarse progress (10% on entry, 85% before publish).
    """

    capabilities = [
        Capability.GPU_REQUIRED,
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
        memory_mb=11_000, cpu_cores=2, gpu_count=1,
        typical_duration_seconds=180.0,
    )
    tags = ["motion-correction", "gpu", "movie"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="MotionCor Plugin",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description="Movie motion correction via the MotionCor3 binary",
        )

    @classmethod
    def input_schema(cls) -> Type[MotionCorInput]:
        return MotionCorInput

    @classmethod
    def output_schema(cls) -> Type[MotioncorPluginOutput]:
        return MotioncorPluginOutput

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
        input_data: MotionCorInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> MotioncorPluginOutput:
        task = current_task()
        if task is None:
            raise RuntimeError(
                "MotioncorPlugin.execute called outside PluginBrokerRunner context. "
                "Use magellon_sdk.runner.set_active_task in tests."
            )

        publisher = self._publisher()
        job_id, task_id = task.job_id, task.id
        emit_step(safe_emit_started(publisher, job_id=job_id, task_id=task_id))
        try:
            emit_step(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=10.0, message="running motioncor3",
            ))
            future = asyncio.run_coroutine_threadsafe(do_motioncor(task), get_step_event_loop())
            result_dto: TaskResultMessage = future.result()

            emit_step(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=85.0, message="publishing result",
            ))
            emit_step(safe_emit_completed(publisher, job_id=job_id, task_id=task_id))
            return MotioncorPluginOutput(result_dto=result_dto)
        except Exception as exc:
            emit_step(safe_emit_failed(
                publisher, job_id=job_id, task_id=task_id, error=str(exc),
            ))
            raise


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------

def build_motioncor_result(task: TaskMessage, output: MotioncorPluginOutput) -> TaskResultMessage:
    """Unwrap MotioncorPluginOutput. Same shape as build_ctf_result."""
    return output.result_dto


# ---------------------------------------------------------------------------
# Back-compat shims — Phase 1b absorbed these into the SDK runner.
# ---------------------------------------------------------------------------

from magellon_sdk.runner import PluginBrokerRunner as MotioncorBrokerRunner  # noqa: E402
from magellon_sdk.runner.active_task import current_task as get_active_task  # noqa: E402
from magellon_sdk.runner.active_task import (  # noqa: E402,F401
    _active_task,
    get_step_event_loop as _get_loop,
)


__all__ = [
    "MotioncorBrokerRunner",
    "MotioncorPlugin",
    "MotioncorPluginOutput",
    "build_motioncor_result",
    "get_active_task",
]
