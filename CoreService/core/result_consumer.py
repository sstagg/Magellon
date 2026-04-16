"""In-process consumer for plugin result routes (P3 + MB4.5).

Subscribes to every subject listed in ``app_settings.rabbitmq_settings.OUT_QUEUES``
via the MessageBus and projects each :class:`TaskResultDto` through
:class:`TaskOutputProcessor`, which writes the per-task DB rows on a
fresh SQLAlchemy session.

MB4.5 replaced the direct pika loop with ``bus.tasks.consumer``:
- Connection / reconnect / ack / nack-to-DLQ are the binder's job.
- Decoding is the binder's job (body → Envelope).
- This module only owns: what to subscribe to, what handler to run.

Failures are isolated per delivery so one bad message can't take the
loop down. Decode errors propagate to the binder as exceptions → the
classifier routes them to DLQ. Processing errors (DB writes etc.)
also DLQ — a row that failed mid-projection would just fail again
on retry.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from config import app_settings
from database import session_local as default_session_local
from magellon_sdk.bus import ConsumerHandle, get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError
from models.plugins_models import TaskResultDto
from services.task_output_processor import TaskOutputProcessor

logger = logging.getLogger(__name__)


def _make_handler(session_factory: sessionmaker):
    """Bind a session factory into a bus-shaped task handler.

    Handler signature matches ``bus.tasks.consumer``: takes an
    :class:`Envelope`, returns ``None`` (ack) or raises (classify →
    DLQ). The binder reconstructs the envelope from wire bytes + ce-*
    headers; ``envelope.data`` is the raw result dict.
    """

    def _on_envelope(envelope: Envelope) -> None:
        try:
            task_result = TaskResultDto.model_validate(envelope.data)
        except Exception as exc:
            # Malformed payload will never decode on retry. Raise as
            # PermanentError so classify_exception routes to DLQ.
            raise PermanentError(f"undecodable TaskResultDto: {exc}") from exc

        db = session_factory()
        out_queues = app_settings.rabbitmq_settings.OUT_QUEUES
        processor = TaskOutputProcessor(db=db, out_queues=out_queues)
        try:
            processor.process(task_result)
            # processor.process() closes the session in its finally block.
        except Exception as exc:
            # The processor already commits/rolls-back its own session.
            # We re-raise so the binder DLQs this delivery via classify:
            # a write that died mid-projection would just fail again on
            # the same row, and the JobManager status writer will mark
            # the task FAILED via the processor's best-effort path
            # before we get here.
            raise PermanentError(f"processor failed: {exc}") from exc

    return _on_envelope


def start_result_consumers(
    session_factory: Optional[sessionmaker] = None,
) -> List[ConsumerHandle]:
    """Register one bus consumer per ``OUT_QUEUES`` entry.

    Returns the list of consumer handles so the caller (startup code)
    can close them cleanly on shutdown. Idempotent in practice —
    calling twice produces duplicate consumers, which would double-
    process each delivery. ``main.py`` should call this once.

    Returns an empty list if ``OUT_QUEUES`` is empty (no-op).
    """
    factory = session_factory or default_session_local
    out_queues = app_settings.rabbitmq_settings.OUT_QUEUES

    if not out_queues:
        logger.info(
            "result_consumer: OUT_QUEUES is empty — staying dormant. "
            "Add queues to rabbitmq_settings.OUT_QUEUES to enable."
        )
        return []

    handler = _make_handler(factory)
    bus = get_bus()
    handles: List[ConsumerHandle] = []
    for q in out_queues:
        route = TaskRoute.named(q.name)
        handles.append(bus.tasks.consumer(route, handler))
        logger.info("result_consumer: subscribed to %s", q.name)
    return handles


# Backward-compat shim: the old module exposed ``result_consumer_engine``
# as a blocking loop spawned on a daemon thread. Post-MB4.5 the bus
# owns the loop — consumers run on binder-managed threads. This
# function registers consumers, waits on the first handle's
# ``run_until_shutdown`` (which blocks until the binder is closed or
# all handles are closed), and returns. Keeps ``main.py`` working
# without code changes at the caller site.
def result_consumer_engine(
    session_factory: Optional[sessionmaker] = None,
) -> None:
    handles = start_result_consumers(session_factory)
    if not handles:
        return
    try:
        handles[0].run_until_shutdown()
    except KeyboardInterrupt:
        logger.info("result_consumer: interrupted, exiting")
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass


__all__ = ["result_consumer_engine", "start_result_consumers"]
