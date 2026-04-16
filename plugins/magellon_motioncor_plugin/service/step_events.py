"""MotionCor plugin step-event binding — thin glue over magellon-sdk.

Mirror of ``magellon_ctf_plugin/service/step_events.py``. The publisher
init (NATS+RMQ fanout, lazy connect, env-var handling, graceful
degradation when one transport is down) lives in
:func:`magellon_sdk.events.make_step_publisher`. ``PLUGIN_NAME`` /
``STEP_NAME`` differ ("motioncor") so subjects route to a different
slice of the bus.
"""
from __future__ import annotations

import logging
from typing import Optional

from magellon_sdk.events import StepEventPublisher, make_step_publisher

from core.settings import AppSettingsSingleton

logger = logging.getLogger(__name__)

PLUGIN_NAME = "motioncor"
STEP_NAME = "motioncor"


async def get_publisher() -> Optional[StepEventPublisher]:
    return await make_step_publisher(
        plugin_name=PLUGIN_NAME,
        rmq_settings=AppSettingsSingleton.get_instance().rabbitmq_settings,
    )


async def safe_emit_started(publisher, *, job_id, task_id) -> None:
    if publisher is None:
        return
    try:
        await publisher.started(job_id=job_id, task_id=task_id, step=STEP_NAME)
    except Exception:
        logger.exception("step-event .started emit failed (non-fatal)")


async def safe_emit_completed(publisher, *, job_id, task_id, output_files=None) -> None:
    if publisher is None:
        return
    try:
        await publisher.completed(
            job_id=job_id, task_id=task_id, step=STEP_NAME, output_files=output_files
        )
    except Exception:
        logger.exception("step-event .completed emit failed (non-fatal)")


async def safe_emit_failed(publisher, *, job_id, task_id, error: str) -> None:
    if publisher is None:
        return
    try:
        await publisher.failed(
            job_id=job_id, task_id=task_id, step=STEP_NAME, error=error
        )
    except Exception:
        logger.exception("step-event .failed emit failed (non-fatal)")


__all__ = [
    "get_publisher",
    "safe_emit_started",
    "safe_emit_completed",
    "safe_emit_failed",
    "PLUGIN_NAME",
    "STEP_NAME",
]
