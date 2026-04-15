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
from pika.exceptions import (
    AMQPConnectionError,
    AMQPChannelError,
    ChannelError,
    ChannelWrongStateError,
    ConnectionClosed,
    ConnectionWrongStateError,
    StreamLostError,
)

from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import AckAction, classify_exception

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

    # Connection-level reset signals: the next publish must reconnect first.
    # Pulled out as a tuple so both publish() and the consumer can share.
    _RECONNECTABLE_ERRORS = (
        StreamLostError,
        ConnectionClosed,
        ConnectionWrongStateError,
        ChannelWrongStateError,
        AMQPConnectionError,
        AMQPChannelError,
    )

    def __init__(
        self,
        settings: Any,
        *,
        exchange: str = DEFAULT_EXCHANGE,
        heartbeat: int = 30,
        blocked_connection_timeout: int = 300,
    ) -> None:
        self.settings = settings
        self.exchange = exchange
        # heartbeat keeps the TCP alive when the publisher is idle for long
        # periods (the failure mode that took down the FFT plugin's RMQ
        # mirror in the e2e). 30s is well under typical broker idle-timeouts
        # while staying cheap.
        self.heartbeat = heartbeat
        self.blocked_connection_timeout = blocked_connection_timeout
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Any = None

    def _open(self) -> None:
        """(Re)open connection + channel and re-declare the exchange.

        Idempotent on the broker side: re-declaring an existing exchange
        with matching properties is a no-op.
        """
        credentials = pika.PlainCredentials(
            self.settings.USER_NAME, self.settings.PASSWORD
        )
        params = pika.ConnectionParameters(
            host=self.settings.HOST_NAME,
            credentials=credentials,
            heartbeat=self.heartbeat,
            blocked_connection_timeout=self.blocked_connection_timeout,
        )
        self.connection = pika.BlockingConnection(params)
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange=self.exchange, exchange_type="topic", durable=True
        )

    def _is_alive(self) -> bool:
        if self.connection is None or self.channel is None:
            return False
        if self.connection.is_closed:
            return False
        try:
            return bool(self.channel.is_open)
        except Exception:
            return False

    def connect(self) -> None:
        if self._is_alive():
            return
        # Best-effort cleanup of any half-open state from a prior failure.
        self._reset_silently()
        try:
            self._open()
            logger.info("RabbitmqEventPublisher: exchange %r ready", self.exchange)
        except (AMQPConnectionError, ChannelError):
            logger.exception("RabbitmqEventPublisher: connect failed")
            raise

    def _reset_silently(self) -> None:
        """Drop any cached connection/channel without raising — used when
        we already know the underlying transport is broken."""
        if self.connection is not None:
            try:
                if not self.connection.is_closed:
                    self.connection.close()
            except Exception:
                pass
        self.connection = None
        self.channel = None

    def publish(self, routing_key: str, envelope: Envelope[Any]) -> None:
        # Auto-reconnect on first publish OR after an idle drop. Without
        # this the publisher zombifies: pika BlockingConnection has no
        # heartbeat-driven recovery, so once the broker drops a stale
        # socket every subsequent basic_publish raises ChannelWrongState
        # forever. With heartbeats we *should* never lose the channel,
        # but the retry is the belt to the heartbeat's suspenders.
        if not self._is_alive():
            self.connect()

        body = envelope.model_dump_json().encode("utf-8")
        properties = pika.BasicProperties(
            content_type="application/json",
            message_id=envelope.id,
            type=envelope.type,
            delivery_mode=2,
        )

        try:
            self.channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
            )
        except self._RECONNECTABLE_ERRORS as e:
            logger.warning(
                "RabbitmqEventPublisher: publish failed (%s) — reconnecting once",
                type(e).__name__,
            )
            self._reset_silently()
            self.connect()
            # One retry. If it fails again the caller's fanout will swallow
            # the per-event exception and move on, which matches our "one
            # transport down doesn't poison the others" isolation rule.
            self.channel.basic_publish(
                exchange=self.exchange,
                routing_key=routing_key,
                body=body,
                properties=properties,
            )

    def close(self) -> None:
        self._reset_silently()


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
            host=self.settings.HOST_NAME,
            credentials=credentials,
            heartbeat=30,
            blocked_connection_timeout=300,
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
                    return
                except Exception as exc:
                    # Decode errors are unrecoverable for this message —
                    # the body is what it is. Plugin-side exceptions may
                    # be retryable. Let the classifier decide; default
                    # policy sends untyped exceptions back for N retries
                    # before giving up, which is what we want for a
                    # step-event stream (broker blips shouldn't DLQ).
                    redeliveries = int(getattr(method, "redelivered", False))
                    classification = classify_exception(
                        exc, redelivery_count=redeliveries
                    )
                    logger.warning(
                        "RabbitmqEventConsumer: %s → %s (%s)",
                        type(exc).__name__,
                        classification.action.value,
                        classification.reason,
                    )
                    if classification.action is AckAction.REQUEUE:
                        ch.basic_nack(
                            delivery_tag=method.delivery_tag, requeue=True
                        )
                    else:
                        # ACK path never reached here (early return on
                        # success); DLQ uses nack+no-requeue which
                        # relies on the queue's dead-letter exchange.
                        ch.basic_nack(
                            delivery_tag=method.delivery_tag, requeue=False
                        )

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
