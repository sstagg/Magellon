"""CoreService's in-process result-consumer wiring (P3 + MB4.5 + MB4.B).

Thin wrapper over :mod:`magellon_sdk.bus.services.result_consumer`. This
module owns the CoreService-specific glue:

- Resolves which subjects to subscribe to from
  ``app_settings.rabbitmq_settings.OUT_QUEUES``.
- Decodes each bus :class:`Envelope` into a :class:`TaskResultMessage`
  and projects it through :class:`TaskOutputProcessor`, which writes
  into CoreService's MySQL on a fresh SQLAlchemy session.
- Classifies failures — malformed payloads and projection errors both
  become :class:`PermanentError` so the binder routes them to the DLQ
  rather than requeuing a poison message.

The actual bus iteration + ``bus.tasks.consumer`` calls + handle
lifecycle live in the SDK — this module delegates via
``_sdk_start_result_consumers`` / ``_sdk_result_consumer_engine``.
MB4.B relocated that logic so the same code paths back CoreService's
in-process consumer and any self-hosted processor that wants to ride
the bus.

Dormancy note: if ``OUT_QUEUES`` is empty this module returns early
without touching the bus at all. That's the safety valve for
deployments that still run the out-of-tree
``magellon_result_processor`` plugin — populating ``OUT_QUEUES`` in
both places causes a round-robin double-consume (see MB4.C in
``IMPLEMENTATION_PLAN.md``).
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from config import app_settings
from database import session_local as default_session_local
from magellon_sdk.bus import ConsumerHandle, get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.bus.services.result_consumer import (
    result_consumer_engine as _sdk_result_consumer_engine,
    start_result_consumers as _sdk_start_result_consumers,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError
from models.plugins_models import TaskResultMessage
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
            task_result = TaskResultMessage.model_validate(envelope.data)
        except Exception as exc:
            # Malformed payload will never decode on retry. Raise as
            # PermanentError so classify_exception routes to DLQ.
            raise PermanentError(f"undecodable TaskResultMessage: {exc}") from exc

        # Live tap for the plugin test panel — emit the raw result
        # envelope onto its job room before processing. Best-effort;
        # never blocks the writer or DLQ classification.
        try:
            from core.socketio_server import schedule_test_envelope
            schedule_test_envelope(
                "in", "result",
                str(task_result.job_id) if task_result.job_id else None,
                task_result.model_dump(mode="json"),
                transport="bus",
            )
        except Exception:
            logger.debug("envelope tap (in) failed", exc_info=True)

        db = session_factory()
        out_queues = app_settings.rabbitmq_settings.OUT_QUEUES
        processor = TaskOutputProcessor(db=db, out_queues=out_queues)
        try:
            processor.process(task_result)
            # processor.process() closes the session in its finally block.
        except Exception as exc:
            # The processor already commits/rolls-back its own session.
            # Re-raise so the binder DLQs this delivery via classify —
            # a write that died mid-projection would just fail again on
            # the same row, and the processor's best-effort path already
            # marked the task FAILED before we get here.
            raise PermanentError(f"processor failed: {exc}") from exc

    return _on_envelope


def _routes_from_out_queues() -> List[TaskRoute]:
    """Translate each ``OUT_QUEUES`` entry into a :class:`TaskRoute`
    named for the legacy queue name (MB3's ``legacy_queue_map`` path)."""
    out_queues = app_settings.rabbitmq_settings.OUT_QUEUES
    if not out_queues:
        return []
    return [TaskRoute.named(q.name) for q in out_queues]


def start_result_consumers(
    session_factory: Optional[sessionmaker] = None,
) -> List[ConsumerHandle]:
    """Register one bus consumer per ``OUT_QUEUES`` entry.

    Returns the list of consumer handles so the caller (startup code)
    can close them cleanly on shutdown. Returns an empty list if
    ``OUT_QUEUES`` is empty (no-op, dormant).

    Idempotent in practice — calling twice produces duplicate consumers,
    which would double-process each delivery. ``main.py`` calls this once.
    """
    routes = _routes_from_out_queues()
    if not routes:
        logger.info(
            "result_consumer: OUT_QUEUES is empty — staying dormant. "
            "Add queues to rabbitmq_settings.OUT_QUEUES to enable."
        )
        return []

    handler = _make_handler(session_factory or default_session_local)
    return _sdk_start_result_consumers(routes, handler, get_bus())


def result_consumer_engine(
    session_factory: Optional[sessionmaker] = None,
) -> None:
    """Blocking variant for ``threading.Thread(target=...)`` callers.

    Registers consumers and blocks on the first handle's
    ``run_until_shutdown`` until the bus closes or KeyboardInterrupt.
    Returns immediately (dormant) when ``OUT_QUEUES`` is empty —
    notably *without* touching the bus, so deployments that haven't
    migrated off the out-of-tree result_processor plugin aren't
    disturbed.
    """
    routes = _routes_from_out_queues()
    if not routes:
        logger.info(
            "result_consumer: OUT_QUEUES is empty — staying dormant. "
            "Add queues to rabbitmq_settings.OUT_QUEUES to enable."
        )
        return

    handler = _make_handler(session_factory or default_session_local)
    _sdk_result_consumer_engine(routes, handler, get_bus())


__all__ = ["result_consumer_engine", "start_result_consumers"]
