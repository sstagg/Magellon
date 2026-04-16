"""RabbitMQ binder — wraps ``RabbitmqClient`` behind the :class:`Binder` Protocol.

Design choices (matching the existing RMQ code, spec §5):

- **One long-lived ``RabbitmqClient`` per binder** for publish + operator
  ops (purge). Consumers and subscribers get **their own** clients so
  ``start_consuming`` blocks a thread that's not the binder's.
- **Topic exchanges declared at start()** — idempotent per AMQP. See
  :mod:`.topology`.
- **Work queues are declared lazily** at publish / consume time. DLQ
  topology is opt-in per queue (``TaskConsumerPolicy.dlq_enabled``) and
  safe only on new queues; the MB6.4 migration handles existing ones.
- **``legacy_queue_map``** — bus routes use subjects like
  ``magellon.tasks.ctf`` but production queues today are named
  ``ctf_tasks_queue``. MB3's producer wiring populates this map so the
  binder can translate subject → legacy queue at the wire boundary.
  Without the map, the subject is used as-is.

Wire format: each envelope goes out as its ``model_dump_json()`` bytes
(full CloudEvents envelope). On consume, the body is decoded back into
an Envelope and passed to the handler. MB3+ may revisit whether to
emit only ``envelope.data`` for back-compat with pre-bus plugins; for
now envelope-on-wire is the default and the simplest contract.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

import pika
from pika.exceptions import AMQPConnectionError, ChannelError

from magellon_sdk.bus.binders.rmq.audit import write_audit_entry
from magellon_sdk.bus.binders.rmq.topology import (
    declare_event_exchanges,
    exchange_for_pattern,
    exchange_for_subject,
    glob_to_rmq_routing_key,
)
from magellon_sdk.bus.interfaces import (
    ConsumerHandle,
    EventHandler,
    PatternRef,
    RouteRef,
    SubscriptionHandle,
    TaskHandler,
)
from magellon_sdk.bus.policy import (
    AuditLogConfig,
    PublishReceipt,
    TaskConsumerPolicy,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import AckAction, classify_exception
from magellon_sdk.transport.rabbitmq import RabbitmqClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------

class _RmqConsumerHandle:
    """:class:`ConsumerHandle` over a pika BlockingConnection.

    ``run_until_shutdown`` calls ``start_consuming`` on the calling
    thread; ``close`` signals ``stop_consuming`` (via
    ``add_callback_threadsafe``) so the blocking loop returns.
    """

    def __init__(
        self, client: RabbitmqClient, binder: "RmqBinder"
    ) -> None:
        self._client = client
        self._binder = binder
        self._stopped = threading.Event()

    def close(self) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        conn = self._client.connection
        if conn is not None and not conn.is_closed:
            try:
                conn.add_callback_threadsafe(self._client.channel.stop_consuming)
            except Exception as e:  # noqa: BLE001
                logger.debug("stop_consuming callback dispatch failed: %s", e)
        try:
            self._client.close_connection()
        except Exception as e:  # noqa: BLE001
            logger.debug("close_connection failed: %s", e)
        self._binder._forget_consumer(self)

    def run_until_shutdown(self) -> None:
        try:
            self._client.start_consuming()
        except Exception as e:  # noqa: BLE001
            if not self._stopped.is_set():
                logger.warning("consume loop exited unexpectedly: %s", e)


class _RmqSubscriptionHandle:
    """:class:`SubscriptionHandle` — event subscriptions run on a
    daemon thread owned by the binder. ``close`` drops the client."""

    def __init__(
        self,
        client: RabbitmqClient,
        thread: threading.Thread,
        binder: "RmqBinder",
    ) -> None:
        self._client = client
        self._thread = thread
        self._binder = binder
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        conn = self._client.connection
        if conn is not None and not conn.is_closed:
            try:
                conn.add_callback_threadsafe(self._client.channel.stop_consuming)
            except Exception as e:  # noqa: BLE001
                logger.debug("subscriber stop_consuming dispatch failed: %s", e)
        try:
            self._client.close_connection()
        except Exception as e:  # noqa: BLE001
            logger.debug("subscriber close_connection failed: %s", e)
        self._binder._forget_subscriber(self)


# ---------------------------------------------------------------------------
# Binder
# ---------------------------------------------------------------------------

class RmqBinder:
    """RabbitMQ implementation of :class:`magellon_sdk.bus.Binder`."""

    name = "rmq"

    def __init__(
        self,
        settings: Any,
        *,
        audit: Optional[AuditLogConfig] = None,
        legacy_queue_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self._settings = settings
        self._audit = audit or AuditLogConfig()
        # Subject → legacy queue name. Bus routes use category-scoped
        # subjects (magellon.tasks.ctf); today's queues are named
        # ctf_tasks_queue etc. MB3 populates this at CoreService boot.
        self._queue_map: Dict[str, str] = dict(legacy_queue_map or {})
        self._client: Optional[RabbitmqClient] = None
        self._consumer_handles: List[_RmqConsumerHandle] = []
        self._subscriber_handles: List[_RmqSubscriptionHandle] = []
        self._lock = threading.Lock()
        self._started = False

    # -- queue name resolution --------------------------------------------

    def _resolve_queue(self, subject: str) -> str:
        return self._queue_map.get(subject, subject)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        client = RabbitmqClient(self._settings)
        client.connect()
        declare_event_exchanges(client.channel)
        self._client = client
        self._started = True
        logger.info("RmqBinder started")

    def close(self) -> None:
        if not self._started:
            return
        # Copy lists because handles remove themselves on close().
        with self._lock:
            consumers = list(self._consumer_handles)
            subscribers = list(self._subscriber_handles)
        for h in consumers:
            h.close()
        for s in subscribers:
            s.close()
        if self._client is not None:
            self._client.close_connection()
            self._client = None
        self._started = False
        logger.info("RmqBinder closed")

    # -- Work queue --------------------------------------------------------

    def publish_task(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        self._require_started()
        queue_name = self._resolve_queue(route.subject)
        write_audit_entry(self._audit, route.subject, envelope)
        body = envelope.model_dump_json().encode("utf-8")
        try:
            self._client.publish_message(body, queue_name)
            return PublishReceipt(ok=True, message_id=str(envelope.id))
        except (AMQPConnectionError, ChannelError) as e:
            logger.error("publish_task failed for %s: %s", queue_name, e)
            return PublishReceipt(
                ok=False, message_id=str(envelope.id), error=str(e)
            )

    def consume_tasks(
        self,
        route: RouteRef,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
    ) -> ConsumerHandle:
        self._require_started()
        queue_name = self._resolve_queue(route.subject)

        # New client so start_consuming can block a dedicated thread
        # without freezing the binder's publish channel.
        client = RabbitmqClient(self._settings)
        client.connect()
        client.declare_queue(queue_name)
        if policy.prefetch is not None:
            client.channel.basic_qos(prefetch_count=policy.prefetch)

        def _callback(ch, method, properties, body):
            redelivery_count = _redelivery_count(method, properties)
            try:
                envelope = Envelope.model_validate_json(body.decode("utf-8"))
                _invoke(handler, envelope)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as exc:
                cls = classify_exception(exc, redelivery_count=redelivery_count)
                logger.warning(
                    "RmqBinder[%s]: %s → %s (%s)",
                    queue_name,
                    type(exc).__name__,
                    cls.action.value,
                    cls.reason,
                )
                if cls.action is AckAction.REQUEUE:
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                else:
                    # ACK or DLQ both nack-no-requeue; DLQ topology (if
                    # configured on the queue) routes to the dead-letter
                    # exchange.
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        client.consume(queue_name, _callback)
        handle = _RmqConsumerHandle(client, self)
        with self._lock:
            self._consumer_handles.append(handle)
        return handle

    def purge_tasks(self, route: RouteRef) -> int:
        self._require_started()
        queue_name = self._resolve_queue(route.subject)
        # passive=True: fail if the queue doesn't exist (matches today's
        # cancellation_service behavior — intentional safety).
        frame = self._client.channel.queue_declare(queue=queue_name, passive=True)
        count = frame.method.message_count
        self._client.channel.queue_purge(queue=queue_name)
        return count

    # -- Events ------------------------------------------------------------

    def publish_event(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        self._require_started()
        exchange = exchange_for_subject(route.subject)
        body = envelope.model_dump_json().encode("utf-8")
        try:
            self._client.channel.basic_publish(
                exchange=exchange,
                routing_key=route.subject,
                body=body,
                properties=pika.BasicProperties(delivery_mode=2),
            )
            return PublishReceipt(ok=True, message_id=str(envelope.id))
        except (AMQPConnectionError, ChannelError) as e:
            logger.error(
                "publish_event failed on %s/%s: %s", exchange, route.subject, e
            )
            return PublishReceipt(
                ok=False, message_id=str(envelope.id), error=str(e)
            )

    def subscribe_events(
        self, pattern: PatternRef, handler: EventHandler
    ) -> SubscriptionHandle:
        self._require_started()
        exchange = exchange_for_pattern(pattern.subject_glob)
        routing_key = glob_to_rmq_routing_key(pattern.subject_glob)

        client = RabbitmqClient(self._settings)
        client.connect()
        # Ensure the exchange exists on this channel too — idempotent,
        # cheap, and guards against the subscriber outpacing start()
        # on a very-early subscription.
        declare_event_exchanges(client.channel)
        # Anonymous, exclusive, auto-deleted queue — dies with the
        # subscriber. One queue per subscription so multiple handlers
        # all get every matching message (pub-sub semantics).
        decl = client.channel.queue_declare(
            queue="", exclusive=True, auto_delete=True
        )
        qname = decl.method.queue
        client.channel.queue_bind(
            exchange=exchange, queue=qname, routing_key=routing_key
        )

        def _callback(ch, method, properties, body):
            try:
                envelope = Envelope.model_validate_json(body.decode("utf-8"))
                _invoke(handler, envelope)
            except Exception:  # noqa: BLE001
                logger.exception(
                    "event handler failed on %s", method.routing_key
                )

        client.channel.basic_consume(
            queue=qname, on_message_callback=_callback, auto_ack=True
        )

        thread = threading.Thread(
            target=client.start_consuming,
            name=f"rmq-subscriber-{pattern.subject_glob}",
            daemon=True,
        )
        thread.start()

        handle = _RmqSubscriptionHandle(client, thread, self)
        with self._lock:
            self._subscriber_handles.append(handle)
        return handle

    # -- internals ---------------------------------------------------------

    def _require_started(self) -> None:
        if not self._started or self._client is None:
            raise RuntimeError(
                "RmqBinder not started. Call .start() before using the bus."
            )

    def _forget_consumer(self, handle: _RmqConsumerHandle) -> None:
        with self._lock:
            try:
                self._consumer_handles.remove(handle)
            except ValueError:
                pass

    def _forget_subscriber(self, handle: _RmqSubscriptionHandle) -> None:
        with self._lock:
            try:
                self._subscriber_handles.remove(handle)
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _redelivery_count(method: Any, properties: Any) -> int:
    """Read the redelivery count from AMQP headers.

    Today's code passes ``int(method.redelivered)`` — a boolean — as
    the count. MB4 flips this to an honest integer in a pika header
    (``x-magellon-redelivery``) managed by the binder. For MB2 we
    honor that header if present and fall back to the boolean.
    """
    if properties is not None and properties.headers:
        value = properties.headers.get("x-magellon-redelivery")
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return int(bool(getattr(method, "redelivered", False)))


def _invoke(handler: Callable, envelope: Envelope) -> None:
    """Invoke a handler, dropping awaitable returns.

    Sync handlers are first-class. Async handlers are accepted but
    the coroutine is not awaited — the binder is pika-sync and
    wiring an asyncio loop here is out of MB2 scope. MB4 revisits
    if any plugin actually needs async at the handler level.
    """
    result = handler(envelope)
    if result is not None and hasattr(result, "__await__"):
        logger.debug(
            "RmqBinder: handler returned an awaitable; not awaiting (MB2 limitation)"
        )


__all__ = ["RmqBinder"]
