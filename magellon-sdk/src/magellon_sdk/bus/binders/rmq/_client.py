"""Pika-based blocking RabbitMQ client shared by CoreService and plugins.

This consolidates the four byte-near-identical copies that previously lived
in ``CoreService/core/rabbitmq_client.py`` and ``plugins/*/core/rabbitmq_client.py``.
The motioncor plugin's hardcoded heartbeat / blocked_connection_timeout
values are preserved by passing them as constructor kwargs at the call
site; other callers keep pika's defaults.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

import pika
from pika.exceptions import AMQPConnectionError, ChannelError

logger = logging.getLogger(__name__)


class RabbitmqClient:
    def __init__(
        self,
        settings: Any,
        *,
        heartbeat: Optional[int] = None,
        blocked_connection_timeout: Optional[int] = None,
    ) -> None:
        self.settings = settings
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel = None
        self._heartbeat = heartbeat
        self._blocked_connection_timeout = blocked_connection_timeout

    def connect(self) -> None:
        """Open a blocking connection + channel.

        Raises :class:`pika.exceptions.AMQPConnectionError` /
        :class:`ChannelError` on failure — previous versions swallowed
        these, which left ``self.connection`` as ``None`` and caused
        the next ``publish_message`` call to ``AttributeError`` on a
        missing channel, masking the real error.
        """
        credentials = pika.PlainCredentials(
            self.settings.USER_NAME,
            self.settings.PASSWORD,
        )
        conn_kwargs: dict = {
            "host": self.settings.HOST_NAME,
            "credentials": credentials,
        }
        port = getattr(self.settings, "PORT", None)
        if port is not None:
            conn_kwargs["port"] = port
        virtual_host = getattr(self.settings, "VIRTUAL_HOST", None)
        if virtual_host:
            conn_kwargs["virtual_host"] = virtual_host
        if self._heartbeat is not None:
            conn_kwargs["heartbeat"] = self._heartbeat
        if self._blocked_connection_timeout is not None:
            conn_kwargs["blocked_connection_timeout"] = self._blocked_connection_timeout
        parameters = pika.ConnectionParameters(**conn_kwargs)
        try:
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ server")
        except (AMQPConnectionError, ChannelError) as e:
            logger.error("Error connecting to RabbitMQ: %s", e)
            raise

    def close_connection(self) -> None:
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ server")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

    def declare_queue(self, queue_name: str) -> None:
        self.channel.queue_declare(queue=queue_name, durable=True)
        logger.info(f"Declared queue: {queue_name}")

    def declare_queue_with_dlq(
        self,
        queue_name: str,
        *,
        dlq_suffix: str = "_dlq",
    ) -> str:
        """Declare ``queue_name`` with a dead-letter queue alongside.

        Creates:

        - ``<queue_name>`` (durable) with ``x-dead-letter-exchange=""``
          and ``x-dead-letter-routing-key=<queue_name><dlq_suffix>`` so
          rejected/expired messages route to the DLQ via the default
          exchange.
        - ``<queue_name><dlq_suffix>`` (durable) — the parking lot.

        Returns the DLQ name.

        **Only use on new queues.** Re-declaring an existing queue
        with different ``x-*`` args raises a
        :class:`PRECONDITION_FAILED` channel error. Existing queues
        (``ctf_tasks_queue``, ``motioncor_tasks_queue``) need a broker
        policy or an operator-driven rename — do not call this on them.
        """
        dlq_name = f"{queue_name}{dlq_suffix}"
        self.channel.queue_declare(queue=dlq_name, durable=True)
        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": dlq_name,
            },
        )
        logger.info("Declared queue %s with DLQ %s", queue_name, dlq_name)
        return dlq_name

    def publish_message(self, message, queue_name: Optional[str] = None) -> None:
        """Publish ``message`` to ``queue_name``.

        Raises :class:`AMQPConnectionError` / :class:`ChannelError` on
        failure so callers (e.g. ``messaging.publish_message_to_queue``)
        can return ``False`` instead of reporting a silently-dropped
        message as a success.
        """
        queue_name = queue_name or self.settings.QUEUE_NAME
        self.declare_queue(queue_name)
        try:
            self.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                ),
            )
            logger.info("Message published to %s", queue_name)
        except (AMQPConnectionError, ChannelError) as e:
            logger.error("Error publishing message to %s: %s", queue_name, e)
            raise

    def consume(self, queue_name: str, callback: Callable) -> None:
        self.declare_queue(queue_name)
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)

    def start_consuming(self) -> None:
        logger.info("Waiting for messages. To exit press CTRL+C")
        self.channel.start_consuming()


# Only ``RabbitmqClient`` is intended for plugin authors that want to
# poke pika directly (discovery, standalone publishers, test harnesses).
# Everything else in this module is internal to the client.
__all__ = ["RabbitmqClient"]
