"""FFT plugin entry point.

Intentionally minimal — FFT is a small, CPU-only operation, which
makes this plugin ideal as an end-to-end test bed for the messaging
stack (NATS + RMQ step events, dispatcher registry, React Socket.IO).

``do_execute`` follows the same started → (work) → completed|failed
contract as CTF / MotionCor. Step events are opt-in via
``MAGELLON_STEP_EVENTS_ENABLED=1`` — disabling keeps the plugin
a pure pipeline processor.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from magellon_sdk.events import BoundStepReporter
from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    PluginInfo,
    PluginManifest,
    ResourceHints,
    Transport,
)

from magellon_sdk.bootstrap import (
    check_operating_system,
    check_python_version,
    check_requirements_txt,
)
from magellon_sdk.models import FftTaskData, PluginInfoSingleton, TaskDto
from service.fft_service import compute_file_fft
from service.step_events import STEP_NAME, get_publisher

logger = logging.getLogger(__name__)

plugin_info_data = {
    "id": "b2e4a5f6-0000-4fff-8000-000000000fft",
    "name": "FFT Plugin",
    "developer": "Behdad Khoshbin b.khoshbin@gmail.com",
    "copyright": "Copyright © 2026",
    "version": "1.0.0",
    "port_number": 8010,
    "Python version": sys.version,
}


def get_plugin_info():
    return PluginInfoSingleton.get_instance(**plugin_info_data)


# ---------------------------------------------------------------------------
# Capability manifest
# ---------------------------------------------------------------------------
# The containerized counterpart of what in-house plugins set as
# ClassVars on PluginBase. The CoreService plugin manager (future)
# will fetch this at registration time via the /manifest endpoint,
# so out-of-tree plugins appear in the registry with the same shape
# as in-house ones.
#
# FFT is small and cheap — 2D numpy FFT on a micrograph finishes in
# well under a second. It's deployed as a separate service only to
# prove the distributed transport path works; in production it could
# just as easily run in-process. Hence IN_PROCESS stays in the
# supported list alongside the transports it actually uses today.

def get_manifest() -> PluginManifest:
    info = get_plugin_info()
    return PluginManifest(
        info=PluginInfo(
            name=info.name,
            version=info.version,
            developer=info.developer,
            description="Fast Fourier Transform of a micrograph, rendered to PNG",
        ),
        capabilities=[
            Capability.CPU_INTENSIVE,
            Capability.IDEMPOTENT,
            Capability.PROGRESS_REPORTING,
        ],
        supported_transports=[Transport.RMQ, Transport.NATS, Transport.HTTP, Transport.IN_PROCESS],
        default_transport=Transport.RMQ,
        isolation=IsolationLevel.CONTAINER,
        resources=ResourceHints(
            memory_mb=500,
            cpu_cores=1,
            typical_duration_seconds=1.0,
        ),
        tags=["fft", "imaging"],
    )


def _resolve_output_path(data: FftTaskData) -> str:
    """Pick the output path from the task payload.

    Order of preference:
      1. ``target_path`` — explicit caller-chosen location
      2. ``image_path`` → sibling ``<name>_FFT.png`` under the plugin's
         configured jobs dir if set, else next to the input

    This mirrors what CoreService's import pipeline does today via
    ``FFT_SUB_URL`` conventions, just expressed inline so the plugin
    doesn't need CoreService's config constants.
    """
    if data.target_path:
        return data.target_path
    if not data.image_path:
        raise ValueError("FFT task payload needs image_path or target_path")
    base = os.path.splitext(os.path.basename(data.image_path))[0] + "_FFT.png"
    return os.path.join(os.path.dirname(data.image_path), base)


async def _safe_emit(coro) -> None:
    """Swallow + log emit failures — a broker blip must not abort an
    otherwise-successful FFT compute."""
    try:
        await coro
    except Exception:
        logger.exception("step-event emit failed (non-fatal)")


async def do_execute(params: TaskDto):
    publisher = await get_publisher()
    reporter = BoundStepReporter(
        publisher, job_id=params.job_id, task_id=params.id, step=STEP_NAME
    )

    await _safe_emit(reporter.started())
    try:
        data = FftTaskData.model_validate(params.data)
        if not data.image_path:
            raise ValueError("FFT task: image_path is required")
        out_path = _resolve_output_path(data)

        # Demo progress tick — FFT is fast enough that one mid-flight
        # event is plenty to prove the progress path works end-to-end.
        await _safe_emit(reporter.progress(25.0, "loading image"))
        compute_file_fft(image_path=data.image_path, abs_out_file_name=out_path)
        await _safe_emit(reporter.progress(90.0, "writing PNG"))

        await _safe_emit(reporter.completed(output_files=[out_path]))
        return {"message": "FFT successfully executed", "output_path": out_path}
    except Exception as exc:
        await _safe_emit(reporter.failed(error=str(exc)))
        return {"error": str(exc)}


async def check_requirements():
    all_results = []
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    return all_results
