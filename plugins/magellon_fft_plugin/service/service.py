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

from core.model_dto import FftTaskData, PluginInfoSingleton, TaskDto
from core.setup_plugin import (
    check_operating_system,
    check_python_version,
    check_requirements_txt,
)
from service.fft_service import compute_file_fft
from service.step_events import (
    get_publisher,
    safe_emit_completed,
    safe_emit_failed,
    safe_emit_started,
)

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


async def do_execute(params: TaskDto):
    publisher = await get_publisher()
    await safe_emit_started(publisher, job_id=params.job_id, task_id=params.id)
    try:
        data = FftTaskData.model_validate(params.data)
        if not data.image_path:
            raise ValueError("FFT task: image_path is required")
        out_path = _resolve_output_path(data)

        compute_file_fft(image_path=data.image_path, abs_out_file_name=out_path)

        await safe_emit_completed(
            publisher,
            job_id=params.job_id,
            task_id=params.id,
            output_files=[out_path],
        )
        return {"message": "FFT successfully executed", "output_path": out_path}
    except Exception as exc:
        await safe_emit_failed(
            publisher, job_id=params.job_id, task_id=params.id, error=str(exc)
        )
        return {"error": str(exc)}


async def check_requirements():
    all_results = []
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    return all_results
