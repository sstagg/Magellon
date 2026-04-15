"""Lazy-constructed :class:`StepEventPublisher` for the CTF plugin.

Opt-in via ``MAGELLON_STEP_EVENTS_ENABLED=1``. When disabled — or when
NATS is unreachable — ``get_publisher()`` returns ``None`` and the
plugin behaves exactly as before (no emission, no failures). This is
observability, not a critical path: a broken events channel must
never fail a job.

Config (env):
  MAGELLON_STEP_EVENTS_ENABLED=1     toggle
  NATS_URL                            default nats://localhost:4222
  NATS_STEP_EVENTS_STREAM             default MAGELLON_STEP_EVENTS
  NATS_STEP_EVENTS_SUBJECTS           default magellon.job.*.step.*
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from magellon_sdk.events import StepEventPublisher
from magellon_sdk.transport.nats import NatsPublisher

logger = logging.getLogger(__name__)

PLUGIN_NAME = "ctf"
STEP_NAME = "ctf"

_publisher: Optional[StepEventPublisher] = None
_nats: Optional[NatsPublisher] = None
_init_lock = asyncio.Lock()


def is_enabled() -> bool:
    return os.environ.get("MAGELLON_STEP_EVENTS_ENABLED") == "1"


async def get_publisher() -> Optional[StepEventPublisher]:
    """Return a connected :class:`StepEventPublisher`, or ``None`` if
    disabled / unreachable. Idempotent — first caller connects, the
    rest reuse the singleton."""
    global _publisher, _nats
    if not is_enabled():
        return None
    if _publisher is not None:
        return _publisher

    async with _init_lock:
        if _publisher is not None:
            return _publisher
        try:
            _nats = NatsPublisher(
                broker_url=os.environ.get("NATS_URL", "nats://localhost:4222"),
                stream=os.environ.get("NATS_STEP_EVENTS_STREAM", "MAGELLON_STEP_EVENTS"),
                subjects=[
                    os.environ.get("NATS_STEP_EVENTS_SUBJECTS", "magellon.job.*.step.*")
                ],
            )
            await _nats.connect()
            _publisher = StepEventPublisher(_nats, plugin_name=PLUGIN_NAME)
            logger.info("CTF step-event publisher ready")
            return _publisher
        except Exception:
            logger.exception("CTF step-event publisher init failed — disabling for this run")
            _nats = None
            _publisher = None
            # Flip the flag in-process so we don't retry connect() on every task.
            os.environ["MAGELLON_STEP_EVENTS_ENABLED"] = "0"
            return None


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
    "is_enabled",
    "safe_emit_started",
    "safe_emit_completed",
    "safe_emit_failed",
    "PLUGIN_NAME",
    "STEP_NAME",
]
