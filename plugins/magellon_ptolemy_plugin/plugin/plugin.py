"""Broker-native ptolemy plugin — two PluginBase classes, one container.

Serves two categories from a single process:

* ``SQUARE_DETECTION`` — low-mag MRC → ranked squares with pickability scores
* ``HOLE_DETECTION``   — med-mag MRC → ranked holes with pickability scores

Both share ``PtolemyInput`` and ``plugin.compute``; they differ only
in which ONNX models run and the output schema. ``main.py`` spins up
one ``PluginBrokerRunner`` per category on its own daemon thread.

Phase 1b (2026-05-03): the per-plugin ``_active_task`` ContextVar,
daemon-loop, ``_emit`` / ``_make_reporter``, and ``PtolemyBrokerRunner``
subclass are gone. Now uses :func:`magellon_sdk.runner.current_task`,
:func:`emit_step`, :func:`make_step_reporter`. Back-compat shims
preserve old import names.
"""
from __future__ import annotations

import logging
from typing import Type

from magellon_sdk.base import PluginBase
from magellon_sdk.categories.outputs import (
    Detection,
    HoleDetectionOutput,
    SquareDetectionOutput,
)
from magellon_sdk.models import OutputFile, PluginInfo, TaskMessage, TaskResultMessage
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import PtolemyInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import emit_step, make_step_reporter

# ``plugin.compute`` is imported lazily inside ``execute`` so the SDK
# contract layer is testable without ``onnxruntime`` (the
# ``plugin.ptolemy.models`` chain drags it in at module load).
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


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

class PtolemySquarePlugin(PluginBase[PtolemyInput, SquareDetectionOutput]):
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
    def input_schema(cls) -> Type[PtolemyInput]:
        return PtolemyInput

    @classmethod
    def output_schema(cls) -> Type[SquareDetectionOutput]:
        return SquareDetectionOutput

    def execute(
        self,
        input_data: PtolemyInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> SquareDetectionOutput:
        from plugin.compute import run_square_detection  # lazy

        step = make_step_reporter(f"{STEP_NAME}.square", get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            if step is not None:
                emit_step(step.progress(10.0, "loading MRC"))
            dets = run_square_detection(input_data.input_file)
            if step is not None:
                emit_step(step.progress(95.0, f"found {len(dets)} squares"))
                emit_step(step.completed())
            return SquareDetectionOutput(
                detections=[Detection(**d) for d in dets],
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# PtolemyHolePlugin — med-mag category
# ---------------------------------------------------------------------------

class PtolemyHolePlugin(PluginBase[PtolemyInput, HoleDetectionOutput]):
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
    def input_schema(cls) -> Type[PtolemyInput]:
        return PtolemyInput

    @classmethod
    def output_schema(cls) -> Type[HoleDetectionOutput]:
        return HoleDetectionOutput

    def execute(
        self,
        input_data: PtolemyInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> HoleDetectionOutput:
        from plugin.compute import run_hole_detection  # lazy

        step = make_step_reporter(f"{STEP_NAME}.hole", get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            if step is not None:
                emit_step(step.progress(10.0, "loading MRC"))
            dets = run_hole_detection(input_data.input_file)
            if step is not None:
                emit_step(step.progress(95.0, f"found {len(dets)} holes"))
                emit_step(step.completed())
            return HoleDetectionOutput(
                detections=[Detection(**d) for d in dets],
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# Result factories — one per category
# ---------------------------------------------------------------------------

def _wrap_result(
    task: TaskMessage,
    output_dict: dict,
    input_file: str,
    message: str,
) -> TaskResultMessage:
    return TaskResultMessage(
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


def build_square_result(task: TaskMessage, output: SquareDetectionOutput) -> TaskResultMessage:
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


def build_hole_result(task: TaskMessage, output: HoleDetectionOutput) -> TaskResultMessage:
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


# ---------------------------------------------------------------------------
# Back-compat shims — Phase 1b absorbed these into the SDK runner.
# ---------------------------------------------------------------------------

from magellon_sdk.runner import PluginBrokerRunner as PtolemyBrokerRunner  # noqa: E402
from magellon_sdk.runner.active_task import current_task as get_active_task  # noqa: E402
from magellon_sdk.runner.active_task import (  # noqa: E402,F401
    _active_task,
    get_step_event_loop as _get_loop,
)


__all__ = [
    "PtolemySquarePlugin",
    "PtolemyHolePlugin",
    "PtolemyBrokerRunner",
    "build_square_result",
    "build_hole_result",
    "get_active_task",
]
