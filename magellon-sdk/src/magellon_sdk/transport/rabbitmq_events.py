"""RabbitMQ topic-exchange transport for step events.

Companion to :mod:`magellon_sdk.transport.nats`. NATS is the
exploration channel; RabbitMQ is the existing operational fabric.
Both carry the *same* :class:`magellon_sdk.envelope.Envelope` payload
with the *same* CloudEvents ``id`` so the read side can dedupe
across transports via a UNIQUE index on ``event_id``.

Routing convention: topic exchange named ``magellon.events`` with
routing keys shaped ``job.<job_id>.step.<step>``. Consumers can
subscribe to wildcards — ``job.*.step.ctf`` for one step across all
jobs, ``job.<id>.step.*`` for one job across all steps.

Sync (pika BlockingConnection) by deliberate choice — the consumer
runs in a daemon thread, matching the existing CoreService
``result_consumer_engine`` and the CTF plugin's RMQ engine. Mixing
async pika is an ergonomics problem we don't need to solve to get
the mirror working.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Optional

import pika
from pika.exceptions import AMQPConnectionError, ChannelError

from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)


DEFAULT_EXCHANGE = "magellon.events"

EnvelopeCallback = Callable[[Envelope[Any]], None]


def step_routing_key(job_id, step: str) -> str:
    """Build the topic routing key for a step event.

    Mirrors :func:`magellon_sdk.events.step_subject` but uses
    dot-separated form RMQ topic exchanges expect.
    """
    return f"job.{job_id}.step.{step}"


class RabbitmqEventPublisher:
    """Sync topic-exchange publisher.

    ``connect()`` is idempotent. ``publish(routing_key, envelope)``
    serializes the envelope to JSON and sets a ``message_id`` matching
    the CloudEvents ``id`` so brokers/operators can correlate.
    """

    def __init__(
        self,
        settings: Any,
        *,
        exchange: str = DEFAULT_EXCHANGE,
    ) -> None:
        self.settings = settings
        self.exchange = exchange
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Any = None

    def connect(self) -> None:
        if self.connection and not self.connection.is_closed:
            return
        credentials = pika.PlainCredentials(
            self.settings.USER_NAME, self.settings.PASSWORD
        )
        params = pika.ConnectionParameters(
            host=self.settings.HOST_NAME, credentials=credentials
        )
        try:
            self.connection = pika.BlockingConnection(params)
            self.channel = self.connection.channel()
            self.channel.exchange_declare(
                exchange=self.exchange, exchange_type="topic", durable=True
            )
            logger.info("RabbitmqEventPublisher: exchange %r ready", self.exchange)
        except (AMQPConnectionError, ChannelError):
            logger.exception("RabbitmqEventPublisher: connect failed")
            raise

    def publish(self, routing_key: str, envelope: Envelope[Any]) -> None:
        if not self.channel:
            raise RuntimeError("RabbitmqEventPublisher.connect() must be called first")
        body = envelope.model_dump_json().encode("utf-8")
        self.channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                message_id=envelope.id,
                type=envelope.type,
                delivery_mode=2,
            ),
        )

    def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = None
        self.channel = None


class RabbitmqEventConsumer:
    """Sync topic-exchange consumer that runs the blocking consume
    loop on a daemon thread.

    Each delivery is decoded into an :class:`Envelope` and handed to
    the callback. ACK on success, NACK (no requeue) on decode failure
    or callback exception — duplicates would just dedupe at the writer
    so we don't loop on a poison message.
    """

    def __init__(
        self,
        settings: Any,
        *,
        exchange: str = DEFAULT_EXCHANGE,
        queue_name: str,
        binding_key: str = "job.*.step.*",
    ) -> None:
        self.settings = settings
        self.exchange = exchange
        self.queue_name = queue_name
        self.binding_key = binding_key
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Any = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def _connect(self) -> None:
        credentials = pika.PlainCredentials(
            self.settings.USER_NAME, self.settings.PASSWORD
        )
        params = pika.ConnectionParameters(
            host=self.settings.HOST_NAME, credentials=credentials
        )
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange=self.exchange, exchange_type="topic", durable=True
        )
        self.channel.queue_declare(queue=self.queue_name, durable=True)
        self.channel.queue_bind(
            exchange=self.exchange,
            queue=self.queue_name,
            routing_key=self.binding_key,
        )
        logger.info(
            "RabbitmqEventConsumer: bound %s to %s with key %s",
            self.queue_name,
            self.exchange,
            self.binding_key,
        )

    def start(self, callback: EnvelopeCallback) -> None:
        if self._thread is not None:
            return

        def _run():
            try:
                self._connect()
            except Exception:
                logger.exception("RabbitmqEventConsumer: failed to connect")
                return

            def _on_message(ch, method, properties, body):
                try:
                    envelope = Envelope.model_validate_json(body)
                    callback(envelope)
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception:
                    logger.exception("RabbitmqEventConsumer: callback failed")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            self.channel.basic_consume(
                queue=self.queue_name, on_message_callback=_on_message
            )
            self._running = True
            try:
                self.channel.start_consuming()
            except Exception:
                if self._running:
                    logger.exception("RabbitmqEventConsumer: consume loop crashed")

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self.channel:
            try:
                self.channel.stop_consuming()
            except Exception:
                pass
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except Exception:
                pass
        self.connection = None
        self.channel = None
        self._thread = None


__all__ = [
    "DEFAULT_EXCHANGE",
    "EnvelopeCallback",
    "RabbitmqEventConsumer",
    "RabbitmqEventPublisher",
    "step_routing_key",
]
