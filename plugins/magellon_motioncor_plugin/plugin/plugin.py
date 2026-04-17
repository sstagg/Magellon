"""Broker-native MotionCor plugin built on the SDK ``PluginBrokerRunner`` (MB4.3).

Mirrors the FFT and CTF cutovers: the runner owns the pika loop,
ack/nack/DLQ classification, discovery, heartbeat, dynamic config,
and provenance stamping. This module declares the plugin's identity,
its input schema, and the wrapper that calls the existing
``do_motioncor`` compute.

Same pragmatic wrapper pattern as CTF — ``MotioncorPluginOutput`` is
a thin Pydantic shell carrying the ``TaskResultDto`` that
``do_motioncor`` already builds inline; refactoring the 200-line
async compute to return a typed ``MotionCorOutput`` would be a
separate, larger PR.

The legacy ``process_test_message`` path (a translator that maps the
test queue's denormalized schema into ``CryoEmCryoEmMotionCorTaskData``) is
NOT part of the runner — it sits on its own ``bus.tasks.consumer``
subscription wired by ``core/test_consumer.py``. That keeps the
runner simple (one in/out queue) and the test path doesn't need the
runner's ``input_schema`` validation since it's already normalizing.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextvars import ContextVar
from typing import Optional, Type

from pydantic import BaseModel, ConfigDict

from magellon_sdk.base import PluginBase
from magellon_sdk.models import (
    PluginInfo,
    TaskDto,
    TaskResultDto,
)
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import CryoEmMotionCorTaskData
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import PluginBrokerRunner

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
# Active-task context (mirror of FFT/CTF pattern).
# ---------------------------------------------------------------------------
_active_task: ContextVar[Optional[TaskDto]] = ContextVar(
    "_motioncor_active_task", default=None
)


def get_active_task() -> Optional[TaskDto]:
    return _active_task.get()


# ---------------------------------------------------------------------------
# Daemon-thread asyncio loop. Bridges sync ``execute()`` (called from the
# binder's pika consumer thread) to the async ``do_motioncor`` + step-event
# emits. Same rationale as plugin/plugin.py in FFT.
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is not None:
        return _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            t = threading.Thread(
                target=_loop.run_forever, name="motioncor-runner-loop", daemon=True,
            )
            t.start()
    return _loop


# ---------------------------------------------------------------------------
# Output wrapper
# ---------------------------------------------------------------------------

class MotioncorPluginOutput(BaseModel):
    """Pydantic shell carrying the TaskResultDto that ``do_motioncor`` builds."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    result_dto: TaskResultDto


# ---------------------------------------------------------------------------
# MotioncorPlugin
# ---------------------------------------------------------------------------

class MotioncorPlugin(PluginBase[CryoEmMotionCorTaskData, MotioncorPluginOutput]):
    """Broker-native MotionCor plugin.

    ``execute()`` is sync — invoked from the binder's consumer thread.
    ``do_motioncor`` is async, bridged via the daemon loop. Step
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
    def input_schema(cls) -> Type[CryoEmMotionCorTaskData]:
        return CryoEmMotionCorTaskData

    @classmethod
    def output_schema(cls) -> Type[MotioncorPluginOutput]:
        return MotioncorPluginOutput

    # ------------------------------------------------------------------
    # Step-event helpers (sync wrappers around the async safe_emit_*)
    # ------------------------------------------------------------------

    def _emit(self, coro) -> None:
        loop = _get_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            future.result(timeout=15.0)
        except Exception:
            logger.exception("step-event emit failed (non-fatal)")

    def _publisher(self):
        loop = _get_loop()
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
        input_data: CryoEmMotionCorTaskData,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> MotioncorPluginOutput:
        task = _active_task.get()
        if task is None:
            raise RuntimeError(
                "MotioncorPlugin.execute called outside MotioncorBrokerRunner context"
            )

        publisher = self._publisher()
        job_id, task_id = task.job_id, task.id
        self._emit(safe_emit_started(publisher, job_id=job_id, task_id=task_id))
        try:
            self._emit(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=10.0, message="running motioncor3",
            ))
            future = asyncio.run_coroutine_threadsafe(do_motioncor(task), _get_loop())
            result_dto: TaskResultDto = future.result()

            self._emit(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=85.0, message="publishing result",
            ))
            self._emit(safe_emit_completed(publisher, job_id=job_id, task_id=task_id))
            return MotioncorPluginOutput(result_dto=result_dto)
        except Exception as exc:
            self._emit(safe_emit_failed(
                publisher, job_id=job_id, task_id=task_id, error=str(exc),
            ))
            raise


# ---------------------------------------------------------------------------
# MotioncorBrokerRunner
# ---------------------------------------------------------------------------

class MotioncorBrokerRunner(PluginBrokerRunner):
    """Runner subclass that exposes the active TaskDto via ContextVar.
    Same shape as FftBrokerRunner / CtfBrokerRunner."""

    def _handle_task(self, envelope) -> None:
        task = self._task_from_envelope(envelope)
        token = _active_task.set(task)
        try:
            super()._handle_task(envelope)
        finally:
            _active_task.reset(token)

    def _process(self, body: bytes) -> bytes:
        text = body.decode("utf-8")
        task = TaskDto.model_validate_json(text)
        token = _active_task.set(task)
        try:
            self._apply_pending_config()
            input_schema = self.plugin.input_schema()
            validated = input_schema.model_validate(task.data)
            plugin_output = self.plugin.run(validated)
            result = self.result_factory(task, plugin_output)
            self._stamp_provenance(result)
            return result.model_dump_json().encode("utf-8")
        finally:
            _active_task.reset(token)


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------

def build_motioncor_result(task: TaskDto, output: MotioncorPluginOutput) -> TaskResultDto:
    """Unwrap MotioncorPluginOutput. Same shape as build_ctf_result."""
    return output.result_dto


__all__ = [
    "MotioncorBrokerRunner",
    "MotioncorPlugin",
    "MotioncorPluginOutput",
    "build_motioncor_result",
    "get_active_task",
]
