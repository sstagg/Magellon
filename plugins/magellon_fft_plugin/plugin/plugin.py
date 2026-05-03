"""Broker-native FFT plugin built on the SDK ``PluginBrokerRunner``.

Phase 1 (2026-05-03): the per-plugin ``FftBrokerRunner`` subclass is
gone. The active-task ContextVar, daemon-thread asyncio loop, and the
sync-from-async ``_emit`` / ``_make_reporter`` helpers are now in
:mod:`magellon_sdk.runner.active_task` — every plugin gets them for
free. This file is the new, minimal shape: input/output schemas,
manifest metadata, and the algorithm wiring.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Type

from magellon_sdk.base import PluginBase
from magellon_sdk.models import (
    OutputFile,
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
from magellon_sdk.models.tasks import FftInput
from magellon_sdk.categories.outputs import FftOutput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import current_task, emit_step, make_step_reporter

from plugin.compute import compute_file_fft
from plugin.events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)


def _resolve_output_path(data: FftInput) -> str:
    """Pick the FFT PNG output path: explicit ``target_path`` if given,
    otherwise ``<image_stem>_FFT.png`` next to the input image."""
    if data.target_path:
        return data.target_path
    if not data.image_path:
        raise ValueError("FFT task: image_path or target_path is required")
    base = os.path.splitext(os.path.basename(data.image_path))[0] + "_FFT.png"
    return os.path.join(os.path.dirname(data.image_path), base)


def _resolve_height(data: FftInput) -> int:
    """Render height (px) for the downsampled magnitude spectrum.
    Read from ``engine_opts['height']`` so callers can override per-task
    without a schema change. Defaults to 1024 — the historical value."""
    raw = (data.engine_opts or {}).get("height", 1024)
    try:
        h = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"engine_opts.height must be an integer; got {raw!r}") from exc
    if h <= 0:
        raise ValueError(f"engine_opts.height must be > 0; got {h}")
    return h


# ---------------------------------------------------------------------------
# FftPlugin
# ---------------------------------------------------------------------------

class FftPlugin(PluginBase[FftInput, FftOutput]):
    """In-house FFT plugin built on the SDK contract.

    ``execute()`` is sync — runs inside :class:`PluginBrokerRunner`'s
    pika consumer thread. Step events bridge to async via
    :func:`magellon_sdk.runner.emit_step` (daemon-loop singleton).
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
    def input_schema(cls) -> Type[FftInput]:
        return FftInput

    @classmethod
    def output_schema(cls) -> Type[FftOutput]:
        return FftOutput

    def execute(
        self,
        input_data: FftInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> FftOutput:
        step = make_step_reporter(STEP_NAME, get_publisher)
        if step is not None:
            emit_step(step.started())
        try:
            out_path = _resolve_output_path(input_data)
            height = _resolve_height(input_data)
            if step is not None:
                emit_step(step.progress(25.0, "loading image"))
            compute_file_fft(
                image_path=input_data.image_path,
                abs_out_file_name=out_path,
                height=height,
            )
            if step is not None:
                emit_step(step.progress(90.0, "writing PNG"))
                emit_step(step.completed(output_files=[out_path]))
            return FftOutput(
                output_path=out_path,
                source_image_path=input_data.image_path,
            )
        except Exception as exc:
            if step is not None:
                emit_step(step.failed(error=str(exc)))
            raise


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------

def build_fft_result(task: TaskMessage, output: FftOutput) -> TaskResultMessage:
    """Wrap an FftOutput in a TaskResultMessage for the result queue."""
    out_file = OutputFile(
        name=os.path.basename(output.output_path),
        path=output.output_path,
        required=True,
    )
    return TaskResultMessage(
        worker_instance_id=task.worker_instance_id,
        job_id=task.job_id,
        task_id=task.id,
        image_path=output.source_image_path,
        session_id=task.session_id,
        session_name=task.session_name,
        code=200,
        message="FFT successfully executed",
        type=task.type,
        output_data={"output_path": output.output_path, **output.extras},
        output_files=[out_file],
    )


# ---------------------------------------------------------------------------
# Back-compat shims for plugin-level tests + callers that imported the
# old subclass + helpers. Phase 1 deleted ``FftBrokerRunner`` /
# ``get_active_task`` / ``_active_task`` / ``_get_loop`` from this module
# in favor of the SDK helpers; the names below preserve import
# compatibility for one release. Remove in 2026-Q3.
# ---------------------------------------------------------------------------

from magellon_sdk.runner import PluginBrokerRunner as FftBrokerRunner  # noqa: E402
from magellon_sdk.runner.active_task import current_task as get_active_task  # noqa: E402
from magellon_sdk.runner.active_task import (  # noqa: E402,F401
    _active_task,
    get_step_event_loop as _get_loop,
)


__all__ = [
    "FftPlugin",
    "FftBrokerRunner",
    "build_fft_result",
    "get_active_task",
]
