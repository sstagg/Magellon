"""Broker-native ptolemy plugin — two PluginBase classes, one container.

This plugin serves two categories from a single process:

* ``SQUARE_DETECTION`` — low-mag MRC → ranked squares with pickability scores
* ``HOLE_DETECTION``   — med-mag MRC → ranked holes with pickability scores

Both categories share the same input shape (``PtolemyTaskData``) and
compute layer (``plugin.compute``); they differ only in which ONNX models
run and the output schema. ``main.py`` spins up one ``PluginBrokerRunner``
per category on its own daemon thread.

Architecture mirrors ``magellon_fft_plugin``: ContextVar for active-task
recovery, daemon asyncio loop for step events, runner subclasses for
plugin-local bookkeeping.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextvars import ContextVar
from typing import Callable, List, Optional, Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import (
    Detection,
    HoleDetectionOutput,
    SquareDetectionOutput,
)
from magellon_sdk.events import BoundStepReporter
from magellon_sdk.models import OutputFile, PluginInfo, TaskDto, TaskResultDto
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import PtolemyTaskData
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import PluginBrokerRunner

from plugin.compute import run_hole_detection, run_square_detection
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active-task ContextVar (one per process — both categories share it, each
# delivery wraps it via the runner's set/reset).
# ---------------------------------------------------------------------------

_active_task: ContextVar[Optional[TaskDto]] = ContextVar(
    "_ptolemy_active_task", default=None
)


def get_active_task() -> Optional[TaskDto]:
    return _active_task.get()


# ---------------------------------------------------------------------------
# Daemon-thread asyncio loop for step-event emission
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
            threading.Thread(
                target=_loop.run_forever, name="ptolemy-step-events", daemon=True
            ).start()
    return _loop


def _emit(coro) -> None:
    try:
        fut = asyncio.run_coroutine_threadsafe(coro, _get_loop())
        fut.result(timeout=5.0)
    except Exception:
        logger.exception("step-event emit failed (non-fatal)")


def _make_reporter(step_suffix: str) -> Optional[BoundStepReporter]:
    task = _active_task.get()
    if task is None:
        return None
    try:
        fut = asyncio.run_coroutine_threadsafe(get_publisher(), _get_loop())
        publisher = fut.result(timeout=15.0)
    except Exception:
        logger.exception("step-event publisher init failed (non-fatal)")
        return None
    if publisher is None:
        return None
    return BoundStepReporter(
        publisher,
        job_id=task.job_id,
        task_id=task.id,
        step=f"{STEP_NAME}.{step_suffix}",
    )


# ---------------------------------------------------------------------------
# Shared plugin metadata
# ---------------------------------------------------------------------------

_CAPABILITIES = [
    Capability.CPU_INTENSIVE,
    Capability.IDEMPOTENT,
    Capability.PROGRESS_REPORTING,
]
_TRANSPORTS = [
    Transport.RMQ,
    Transport.NATS,
    Transport.HTTP,
    Transport.IN_PROCESS,
]
_RESOURCES = ResourceHints(
    # Three ORT sessions in memory (~6 MB of weights) + numpy buffers for
    # the image + a ~270^2 batch of crops = fits comfortably under 500 MB.
    memory_mb=600,
    cpu_cores=2,
    typical_duration_seconds=5.0,
)


# ---------------------------------------------------------------------------
# PtolemySquarePlugin — low-mag category
# ---------------------------------------------------------------------------

class PtolemySquarePlugin(PluginBase[PtolemyTaskData, SquareDetectionOutput]):
    capabilities = _CAPABILITIES
    supported_transports = _TRANSPORTS
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = _RESOURCES
    tags = ["ptolemy", "square-detection", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Ptolemy Square Detection",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Low-mag square detection + pickability scoring. "
                "Vendors SMLC-NYSBC ptolemy (CC BY-NC 4.0); runs on ONNX, no PyTorch."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[PtolemyTaskData]:
        return PtolemyTaskData

    @classmethod
    def output_schema(cls) -> Type[SquareDetectionOutput]:
        return SquareDetectionOutput

    def execute(
        self,
        input_data: PtolemyTaskData,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> SquareDetectionOutput:
        step = _make_reporter("square")
        if step is not None:
            _emit(step.started())
        try:
            if step is not None:
                _emit(step.progress(10.0, "loading MRC"))
            dets = run_square_detection(input_data.input_file)
            if step is not None:
                _emit(step.progress(95.0, f"found {len(dets)} squares"))
                _emit(step.completed())
            return SquareDetectionOutput(
                detections=[Detection(**d) for d in dets],
            )
        except Exception as exc:
            if step is not None:
                _emit(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# PtolemyHolePlugin — med-mag category
# ---------------------------------------------------------------------------

class PtolemyHolePlugin(PluginBase[PtolemyTaskData, HoleDetectionOutput]):
    capabilities = _CAPABILITIES
    supported_transports = _TRANSPORTS
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = _RESOURCES
    tags = ["ptolemy", "hole-detection", "cryo-em"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="Ptolemy Hole Detection",
            version="1.0.0",
            developer="Behdad Khoshbin b.khoshbin@gmail.com",
            description=(
                "Med-mag hole detection + pickability scoring. "
                "Vendors SMLC-NYSBC ptolemy (CC BY-NC 4.0); runs on ONNX, no PyTorch."
            ),
        )

    @classmethod
    def input_schema(cls) -> Type[PtolemyTaskData]:
        return PtolemyTaskData

    @classmethod
    def output_schema(cls) -> Type[HoleDetectionOutput]:
        return HoleDetectionOutput

    def execute(
        self,
        input_data: PtolemyTaskData,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> HoleDetectionOutput:
        step = _make_reporter("hole")
        if step is not None:
            _emit(step.started())
        try:
            if step is not None:
                _emit(step.progress(10.0, "loading MRC"))
            dets = run_hole_detection(input_data.input_file)
            if step is not None:
                _emit(step.progress(95.0, f"found {len(dets)} holes"))
                _emit(step.completed())
            return HoleDetectionOutput(
                detections=[Detection(**d) for d in dets],
            )
        except Exception as exc:
            if step is not None:
                _emit(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# Runners — share the ContextVar so step events can key on the active task
# ---------------------------------------------------------------------------

class PtolemyBrokerRunner(PluginBrokerRunner):
    """Runner that exposes the active TaskDto via ContextVar.

    Same shape as ``FftBrokerRunner``; one subclass covers both categories
    because the two plugin instances each get their own runner instance.
    """

    def _handle_task(self, envelope) -> None:
        task = self._task_from_envelope(envelope)
        token = _active_task.set(task)
        try:
            super()._handle_task(envelope)
        finally:
            _active_task.reset(token)

    def _process(self, body: bytes) -> bytes:
        task = TaskDto.model_validate_json(body.decode("utf-8"))
        token = _active_task.set(task)
        try:
            self._apply_pending_config()
            validated = self.plugin.input_schema().model_validate(task.data)
            plugin_output = self.plugin.run(validated)
            result = self.result_factory(task, plugin_output)
            self._stamp_provenance(result)
            return result.model_dump_json().encode("utf-8")
        finally:
            _active_task.reset(token)


# ---------------------------------------------------------------------------
# Result factories — one per category
# ---------------------------------------------------------------------------

def _wrap_result(
    task: TaskDto,
    output_dict: dict,
    input_file: str,
    message: str,
) -> TaskResultDto:
    return TaskResultDto(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_path=input_file,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message=message,
        type=task.type,
        output_data=output_dict,
        output_files=[],
    )


def build_square_result(task: TaskDto, output: SquareDetectionOutput) -> TaskResultDto:
    data = task.data or {}
    input_file = data.get("input_file", "")
    return _wrap_result(
        task,
        {
            "detections": [d.model_dump() for d in output.detections],
            **output.extras,
        },
        input_file,
        f"Ptolemy square-detection found {len(output.detections)} squares",
    )


def build_hole_result(task: TaskDto, output: HoleDetectionOutput) -> TaskResultDto:
    data = task.data or {}
    input_file = data.get("input_file", "")
    return _wrap_result(
        task,
        {
            "detections": [d.model_dump() for d in output.detections],
            **output.extras,
        },
        input_file,
        f"Ptolemy hole-detection found {len(output.detections)} holes",
    )


__all__ = [
    "PtolemySquarePlugin",
    "PtolemyHolePlugin",
    "PtolemyBrokerRunner",
    "build_square_result",
    "build_hole_result",
    "get_active_task",
]
