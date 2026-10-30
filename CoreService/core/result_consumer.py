"""CoreService's in-process result-consumer wiring (P3 + MB4.5 + MB4.B).

Thin wrapper over :mod:`magellon_sdk.bus.services.result_consumer`. This
module owns the CoreService-specific glue:

- Resolves which subjects to subscribe to from
  ``app_settings.rabbitmq_settings.OUT_QUEUES``.
- Decodes each bus :class:`Envelope` into a :class:`TaskResultMessage`
  and projects it through :class:`TaskOutputProcessor`, which writes
  into CoreService's MySQL on a fresh SQLAlchemy session.
- Classifies failures: a malformed payload is a :class:`PermanentError`;
  a processing error propagates, so the binder retries it (after a delay
  for transient database errors) and, once its retries are spent,
  dead-letters it. Dead letters are kept in ``task_result_dead_letter``
  and fail their task's step, so the job still finishes.
- Stops cleanly: :func:`stop_result_consumers` lets each consumer finish
  the result in hand before the process exits.

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

import json
import logging
import threading
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from config import app_settings
from database import session_local as default_session_local
from magellon_sdk.bus import ConsumerHandle, get_bus
from magellon_sdk.bus.policy import TaskConsumerPolicy
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError
from magellon_sdk.models import TaskResultMessage
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

        # Results still in flight for an import the user stopped: its session
        # was deleted, so don't move files back into it — drop the result.
        if task_result.job_id:
            from services import import_queue
            if import_queue.is_stopped(task_result.job_id):
                logger.info("Dropping result for task %s: its import was stopped", task_result.task_id)
                return

        db = session_factory()
        out_queues = app_settings.rabbitmq_settings.OUT_QUEUES
        processor = TaskOutputProcessor(db=db, out_queues=out_queues)
        try:
            processor.process(task_result)
            # processor.process() closes the session in its finally block.
        except Exception:
            # The processor rolled back, so nothing of this result was kept.
            # Let the binder retry it (RetryableError waits first) and,
            # after its retries, dead-letter it (see _dead_letter_hook).
            raise

    return _on_envelope


def _routes_from_out_queues() -> List[TaskRoute]:
    """Translate each ``OUT_QUEUES`` entry into a :class:`TaskRoute`
    named for the legacy queue name (MB3's ``legacy_queue_map`` path)."""
    out_queues = app_settings.rabbitmq_settings.OUT_QUEUES
    if not out_queues:
        return []
    return [TaskRoute.named(q.name) for q in out_queues]


# Consumers started by result_consumer_engine, for stop_result_consumers.
_handles: List[ConsumerHandle] = []
_threads: List[threading.Thread] = []


def _dead_letter_hook(queue_name: str, session_factory: sessionmaker):
    """Keep a result that failed all its retries, and fail its task's step so
    the job finishes instead of waiting for it forever."""
    def hook(envelope: Optional[Envelope], exc: BaseException) -> None:
        data = getattr(envelope, "data", None)
        task_id = job_id = step = None
        try:
            result = TaskResultMessage.model_validate(data)
            task_id = str(result.task_id) if result.task_id else None
            job_id = str(result.job_id) if result.job_id else None
            step = result.type.name if result.type else None
        except Exception:
            pass
        reason = f"Result could not be processed: {exc}"[:300]
        logger.error("result_consumer: dead-lettered a result from %s (task %s): %s", queue_name, task_id, exc)
        db = session_factory()
        try:
            from models.sqlalchemy_models import TaskResultDeadLetter
            db.add(TaskResultDeadLetter(
                id=str(uuid.uuid4()), queue=queue_name, task_id=task_id, job_id=job_id, step=step,
                error=str(exc)[:4000], payload=json.loads(json.dumps(data, default=str)) if data else None,
                created_at=datetime.utcnow()))
            if job_id and task_id:
                from services.job_manager import job_manager
                try:
                    job_manager.record_task_finished(job_id, task_id, failed=True, step=step or "Result",
                                                     reason=reason, db=db)
                except LookupError:
                    pass
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("result_consumer: could not record the dead letter")
        finally:
            db.close()
        try:
            from core.socketio_server import schedule_log
            schedule_log("error", (step or "results").lower(),
                         f"A {step or 'plugin'} result for task {task_id} could not be processed and was "
                         f"set aside for an administrator: {exc}"[:500])
        except Exception:
            pass
    return hook


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

    factory = session_factory or default_session_local
    handler = _make_handler(factory)
    bus = get_bus()
    handles = []
    for route in routes:
        policy = TaskConsumerPolicy(on_dead_letter=_dead_letter_hook(route.subject, factory))
        handles.append(bus.tasks.consumer(route, handler, policy=policy))
        logger.info("result_consumer: subscribed to %s", route.subject)
    return handles


def result_consumer_engine(
    session_factory: Optional[sessionmaker] = None,
) -> None:
    """Blocking variant for ``threading.Thread(target=...)`` callers.

    Starts one consumer loop per ``OUT_QUEUES`` entry, each on its own
    thread, and blocks until they all stop (see
    :func:`stop_result_consumers`). Returns immediately (dormant) when
    ``OUT_QUEUES`` is empty — notably *without* touching the bus, so
    deployments that haven't migrated off the out-of-tree
    result_processor plugin aren't disturbed.
    """
    if not _routes_from_out_queues():
        logger.info(
            "result_consumer: OUT_QUEUES is empty — staying dormant. "
            "Add queues to rabbitmq_settings.OUT_QUEUES to enable."
        )
        return
    for handle in start_result_consumers(session_factory):
        thread = threading.Thread(target=handle.run_until_shutdown,
                                  name=f"result-consumer-{len(_threads)}", daemon=True)
        _handles.append(handle)
        _threads.append(thread)
        thread.start()
    for thread in _threads:
        thread.join()


def stop_result_consumers(timeout: float = 45.0) -> None:
    """Stop the result consumers, letting each finish the result in hand,
    so a shutdown never cuts a result off halfway (unfinished results stay
    in their queue for the next start)."""
    for handle in _handles:
        try:
            handle.close()
        except Exception:
            logger.debug("result_consumer: close failed", exc_info=True)
    for thread in _threads:
        thread.join(timeout)
    logger.info("result_consumer: stopped (%d consumer(s))", len(_threads))


__all__ = ["result_consumer_engine", "start_result_consumers", "stop_result_consumers"]
