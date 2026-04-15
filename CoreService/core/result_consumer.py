"""In-process consumer for plugin result queues (P3).

Replaces the out-of-tree ``magellon_result_processor`` plugin's
RabbitMQ consumer loop. Subscribes to every queue listed in
``app_settings.rabbitmq_settings.OUT_QUEUES`` and projects each
``TaskResultDto`` through :class:`TaskOutputProcessor`, which writes
the per-task DB rows on a fresh SQLAlchemy session.

Designed to be run on a daemon thread spawned from ``main.py``
startup — same pattern as the existing motioncor test consumer and
the RMQ step-event forwarder. Failures are isolated per delivery so
one bad message can't take the loop down.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

from pika.exceptions import ConnectionClosedByBroker
from sqlalchemy.orm import sessionmaker

from config import app_settings
from core.rabbitmq_client import RabbitmqClient
from database import session_local as default_session_local
from models.plugins_models import TaskResultDto
from services.task_output_processor import TaskOutputProcessor

logger = logging.getLogger(__name__)


def _process_one(body: bytes, session_factory: sessionmaker) -> None:
    """Decode the message, hand it to TaskOutputProcessor on a fresh
    session. Raises on decode failure so the broker callback can DLQ
    the bad delivery instead of silently dropping it."""
    text = body.decode("utf-8")
    task_result = TaskResultDto.model_validate_json(text)

    db = session_factory()
    out_queues = app_settings.rabbitmq_settings.OUT_QUEUES
    processor = TaskOutputProcessor(db=db, out_queues=out_queues)
    processor.process(task_result)
    # processor.process() closes the session in its finally block.


def _make_callback(session_factory: sessionmaker):
    """Bind a session factory into a pika-shaped on_message callback."""

    def _on_message(ch, method, properties, body):
        try:
            _process_one(body, session_factory)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except json.JSONDecodeError as exc:
            # Bad JSON will never decode on retry — DLQ immediately.
            logger.error("result_consumer: undecodable message → DLQ: %s", exc)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as exc:
            # The processor already commits/rolls-back its own session.
            # We DLQ here rather than requeue: a write that died
            # mid-projection would just fail again on the same row, and
            # the JobManager status writer will mark the task FAILED via
            # the processor's best-effort path before we get here.
            logger.error(
                "result_consumer: processing failed → DLQ: %s", exc, exc_info=True
            )
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    return _on_message


def result_consumer_engine(
    session_factory: Optional[sessionmaker] = None,
) -> None:
    """Long-running consumer loop. Reconnects on broker bounce.

    ``session_factory`` is injectable for tests; production passes
    the module-level ``database.session_local``.
    """
    factory = session_factory or default_session_local
    out_queues = app_settings.rabbitmq_settings.OUT_QUEUES

    if not out_queues:
        logger.info(
            "result_consumer: OUT_QUEUES is empty — staying dormant. "
            "Add queues to rabbitmq_settings.OUT_QUEUES to enable."
        )
        return

    queue_names = [q.name for q in out_queues]
    logger.info("result_consumer: subscribing to %s", queue_names)

    while True:
        try:
            client = RabbitmqClient(app_settings.rabbitmq_settings)
            client.connect()
            callback = _make_callback(factory)
            for name in queue_names:
                client.declare_queue(name)
                client.consume(name, callback)
            logger.info("result_consumer: consuming. press CTRL+C to exit")
            client.start_consuming()
        except KeyboardInterrupt:
            logger.info("result_consumer: interrupted, exiting")
            break
        except ConnectionClosedByBroker:
            logger.warning("result_consumer: broker closed connection, reconnecting in 5s")
            time.sleep(5)
        except Exception as exc:
            logger.error("result_consumer: loop crashed (%s) — reconnecting in 5s", exc)
            time.sleep(5)


__all__ = ["result_consumer_engine"]
