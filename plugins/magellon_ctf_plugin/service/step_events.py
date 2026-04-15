"""Lazy-constructed step-event publisher for the CTF plugin.

Opt-in via ``MAGELLON_STEP_EVENTS_ENABLED=1``. Optionally fans out to
both NATS and RabbitMQ so consumers on either fabric see the event;
the CloudEvents ``id`` is the same on both copies, so downstream
dedup (DB UNIQUE on event_id) makes double-delivery a no-op.

When transports fail — or the toggle is off — ``get_publisher()``
returns ``None`` and the plugin behaves exactly as before. This is
observability, not a critical path.

Config (env):
  MAGELLON_STEP_EVENTS_ENABLED=1      toggle
  MAGELLON_STEP_EVENTS_RMQ=1          also publish to RMQ topic exchange
  NATS_URL                            default nats://localhost:4222
  NATS_STEP_EVENTS_STREAM             default MAGELLON_STEP_EVENTS
  NATS_STEP_EVENTS_SUBJECTS           default magellon.job.*.step.*
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, List, Optional

from magellon_sdk.events import StepEventPublisher
from magellon_sdk.transport.nats import NatsPublisher
from magellon_sdk.transport.rabbitmq_events import (
    DEFAULT_EXCHANGE,
    RabbitmqEventPublisher,
)

logger = logging.getLogger(__name__)


class _RmqAsyncAdapter:
    """Make the sync :class:`RabbitmqEventPublisher` quack like the
    async ``publish(subject, envelope)`` interface ``StepEventPublisher``
    expects. The publish is sync but pika's basic_publish is fast
    enough that wrapping it in ``asyncio.to_thread`` is unnecessary
    overhead — emits are best-effort observability."""

    def __init__(self, rmq: RabbitmqEventPublisher) -> None:
        self._rmq = rmq

    async def publish(self, subject: str, envelope) -> None:
        # subject is dot-form already (matches NATS subject); RMQ topic
        # exchanges use the same dotted shape, so no translation needed.
        self._rmq.publish(subject, envelope)


class _FanoutPublisher:
    """Emits each envelope to every wrapped transport. One publisher
    raising is logged but does not block the others — partial delivery
    is better than full silence."""

    def __init__(self, publishers: List[Any]) -> None:
        self._publishers = publishers

    async def publish(self, subject: str, envelope) -> None:
        for pub in self._publishers:
            try:
                await pub.publish(subject, envelope)
            except Exception:
                logger.exception(
                    "fanout publisher: one transport failed for event %s — continuing",
                    envelope.id,
                )

PLUGIN_NAME = "ctf"
STEP_NAME = "ctf"

_publisher: Optional[StepEventPublisher] = None
_nats: Optional[NatsPublisher] = None
_rmq: Optional[RabbitmqEventPublisher] = None
_init_lock = asyncio.Lock()


def is_enabled() -> bool:
    return os.environ.get("MAGELLON_STEP_EVENTS_ENABLED") == "1"


def _rmq_enabled() -> bool:
    return os.environ.get("MAGELLON_STEP_EVENTS_RMQ") == "1"


async def get_publisher() -> Optional[StepEventPublisher]:
    """Return a connected :class:`StepEventPublisher`, or ``None`` if
    disabled / unreachable. Idempotent — first caller connects, the
    rest reuse the singleton.

    When ``MAGELLON_STEP_EVENTS_RMQ=1`` is also set, the publisher
    fans out to both NATS and RMQ. RMQ failure to connect at init
    time degrades to NATS-only rather than disabling everything."""
    global _publisher, _nats, _rmq
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

            transports: list = [_nats]
            if _rmq_enabled():
                try:
                    from core.settings import AppSettingsSingleton
                    rmq_settings = AppSettingsSingleton.get_instance().rabbitmq_settings
                    _rmq = RabbitmqEventPublisher(rmq_settings, exchange=DEFAULT_EXCHANGE)
                    _rmq.connect()
                    transports.append(_RmqAsyncAdapter(_rmq))
                    logger.info("CTF step-event publisher: RMQ mirror enabled")
                except Exception:
                    logger.exception("CTF step-event publisher: RMQ init failed — NATS only")
                    _rmq = None

            inner = transports[0] if len(transports) == 1 else _FanoutPublisher(transports)
            _publisher = StepEventPublisher(inner, plugin_name=PLUGIN_NAME)
            logger.info("CTF step-event publisher ready (transports=%d)", len(transports))
            return _publisher
        except Exception:
            logger.exception("CTF step-event publisher init failed — disabling for this run")
            _nats = None
            _rmq = None
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
