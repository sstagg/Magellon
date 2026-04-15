"""Broker-native FFT plugin built on the SDK ``PluginBrokerRunner``.

This module is the migration target for the hand-rolled
``core/rabbitmq_consumer_engine.py``. The runner harness now owns the
pika loop, discovery, heartbeat, dynamic config, provenance stamping,
and typed failure routing — the plugin only declares its identity,
schemas, and the compute itself.

What the FFT plugin specifically had to add on top of the SDK:

* A ``ContextVar`` to recover the active :class:`TaskDto` inside
  ``execute()`` — needed for step events, which key on ``job_id``.
  The base runner deliberately doesn't pass the envelope to
  ``plugin.run()`` (input-only signature, see runner.py); the
  ``FftBrokerRunner`` subclass below stashes it instead, which keeps
  ``PluginBase.execute()`` unchanged for every other plugin.

* A daemon-thread asyncio loop so ``execute()`` (sync, called from
  pika's consumer thread) can submit the existing async step-event
  publisher coroutines without recreating an event loop per task.
  Same pattern the old consumer_engine used.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextvars import ContextVar
from typing import Optional, Type

from magellon_sdk.base import PluginBase
from magellon_sdk.events import BoundStepReporter
from magellon_sdk.models import (
    OutputFile,
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
from magellon_sdk.models.tasks import FftTaskData
from magellon_sdk.categories.outputs import FftOutput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import PluginBrokerRunner

from service.fft_service import compute_file_fft
from service.step_events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active-task context
# ---------------------------------------------------------------------------
# Populated by FftBrokerRunner._process before plugin.run(); cleared in a
# finally. ContextVar (rather than thread-local) so the value follows the
# logical task even if a future async refactor moves work around.
_active_task: ContextVar[Optional[TaskDto]] = ContextVar(
    "_fft_active_task", default=None
)


def get_active_task() -> Optional[TaskDto]:
    """Public accessor — used by tests and by execute()."""
    return _active_task.get()


# ---------------------------------------------------------------------------
# Daemon-thread asyncio loop for step-event emission
# ---------------------------------------------------------------------------
# One long-lived loop per process. asyncio.run() per emit would spin up
# and tear down a loop for every task and stall pika's heartbeat long
# enough for the broker to drop the connection — same gotcha the old
# consumer_engine had.

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
                target=_loop.run_forever, name="fft-step-events", daemon=True
            )
            t.start()
    return _loop


def _resolve_output_path(data: FftTaskData) -> str:
    """Pick the FFT PNG output path. Mirrors ``service.service``'s
    helper — kept local so the broker path doesn't import the HTTP path."""
    if data.target_path:
        return data.target_path
    if not data.image_path:
        raise ValueError("FFT task: image_path or target_path is required")
    base = os.path.splitext(os.path.basename(data.image_path))[0] + "_FFT.png"
    return os.path.join(os.path.dirname(data.image_path), base)


# ---------------------------------------------------------------------------
# FftPlugin
# ---------------------------------------------------------------------------

class FftPlugin(PluginBase[FftTaskData, FftOutput]):
    """In-house FFT plugin built on the SDK contract.

    ``execute()`` is sync — runs inside ``PluginBrokerRunner``'s pika
    consumer thread. Step events bridge to async via the daemon loop.
    """

    capabilities = [
        Capability.CPU_INTENSIVE,
        Capability.IDEMPOTENT,
        Capability.PROGRESS_REPORTING,
    ]
    supported_transports = [
        Transport.RMQ,
        Transport.NATS,
        Transport.HTTP,
        Transport.IN_PROCESS,
    ]
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = ResourceHints(
        memory_mb=500, cpu_cores=1, typical_duration_seconds=1.0
    )
    tags = ["fft", "imaging"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="FFT Plugin",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description="Fast Fourier Transform of a micrograph, rendered to PNG",
        )

    @classmethod
    def input_schema(cls) -> Type[FftTaskData]:
        return FftTaskData

    @classmethod
    def output_schema(cls) -> Type[FftOutput]:
        return FftOutput

    # ------------------------------------------------------------------
    # Step-event helpers
    # ------------------------------------------------------------------

    def _emit(self, coro) -> None:
        """Run a step-event coroutine on the daemon loop, sync-style.

        A failed emit must never abort an otherwise-successful FFT
        compute — we log and continue, same as the old async _safe_emit.
        """
        loop = _get_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            future.result(timeout=5.0)
        except Exception:
            logger.exception("step-event emit failed (non-fatal)")

    def _make_reporter(self) -> Optional[BoundStepReporter]:
        """Build a BoundStepReporter for the active task — or None if
        step events are disabled or the publisher couldn't initialize.
        """
        task = _active_task.get()
        if task is None:
            return None
        loop = _get_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(get_publisher(), loop)
            publisher = future.result(timeout=5.0)
        except Exception:
            logger.exception("step-event publisher init failed (non-fatal)")
            return None
        if publisher is None:
            return None
        return BoundStepReporter(
            publisher, job_id=task.job_id, task_id=task.id, step=STEP_NAME
        )

    # ------------------------------------------------------------------
    # Core compute
    # ------------------------------------------------------------------

    def execute(
        self,
        input_data: FftTaskData,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> FftOutput:
        step = self._make_reporter()
        if step is not None:
            self._emit(step.started())
        try:
            out_path = _resolve_output_path(input_data)
            if step is not None:
                self._emit(step.progress(25.0, "loading image"))
            compute_file_fft(
                image_path=input_data.image_path,
                abs_out_file_name=out_path,
            )
            if step is not None:
                self._emit(step.progress(90.0, "writing PNG"))
                self._emit(step.completed(output_files=[out_path]))
            return FftOutput(
                output_path=out_path,
                source_image_path=input_data.image_path,
            )
        except Exception as exc:
            if step is not None:
                self._emit(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# FftBrokerRunner
# ---------------------------------------------------------------------------

class FftBrokerRunner(PluginBrokerRunner):
    """Runner subclass that exposes the active TaskDto via ContextVar.

    The base runner keeps ``plugin.run()`` input-only so PluginBase's
    signature is shared across every plugin. FFT needs the envelope to
    emit step events keyed on ``job_id`` — overriding ``_process()`` is
    the smallest hook; alternatives (changing PluginBase or threading
    a context kwarg through ``run()``) would touch every plugin.
    """

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

def build_fft_result(task: TaskDto, output: FftOutput) -> TaskResultDto:
    """Wrap an FftOutput in a TaskResultDto for the result queue."""
    out_file = OutputFile(
        name=os.path.basename(output.output_path),
        path=output.output_path,
        required=True,
    )
    return TaskResultDto(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_path=output.source_image_path,
        session_id=task.sesson_id,
        session_name=task.sesson_name,
        code=200,
        message="FFT successfully executed",
        type=task.type,
        output_data={"output_path": output.output_path, **output.extras},
        output_files=[out_file],
    )


__all__ = [
    "FftPlugin",
    "FftBrokerRunner",
    "build_fft_result",
    "get_active_task",
]
