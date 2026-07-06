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

Wire format: **CloudEvents 1.0 "binary content mode"**. The AMQP body
carries ``envelope.data`` serialized as JSON (unchanged from today's
``TaskMessage.model_dump_json()`` shape — existing plugins can decode it
without any code change). Envelope metadata rides on AMQP
``properties.headers`` as ``ce-specversion`` / ``ce-id`` /
``ce-source`` / ``ce-type`` / ``ce-subject`` / ``ce-time`` /
``ce-dataschema``. ``properties.content_type`` carries ``datacontenttype``.

On consume, headers + body are reassembled into an :class:`Envelope`
for the handler. Pre-bus messages that lack ``ce-*`` headers are
wrapped in a synthetic envelope with neutral defaults — the bus
stays lossless for the transition.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import pika
from pika.exceptions import AMQPConnectionError, ChannelError, StreamLostError

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
    RpcHandler,
    SubscriptionHandle,
    TaskHandler,
)
from magellon_sdk.bus.policy import (
    AuditLogConfig,
    PublishReceipt,
    RpcPolicy,
    TaskConsumerPolicy,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import AckAction, classify_exception
from magellon_sdk.bus.binders.rmq._client import RabbitmqClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------

#: Reconnect backoff bounds for consumer loops (seconds).
_RECONNECT_BACKOFF_INITIAL = 1.0
_RECONNECT_BACKOFF_MAX = 60.0


class _RmqConsumerHandle:
    """:class:`ConsumerHandle` over a pika BlockingConnection.

    ``run_until_shutdown`` calls ``start_consuming`` on the calling
    thread and — unlike a bare pika loop — survives broker drops: when
    the connection dies it reconnects with capped exponential backoff
    and re-runs the ``setup`` closure (queue declare, qos,
    basic_consume) before resuming. ``close`` signals
    ``stop_consuming`` (via ``add_callback_threadsafe``) so the
    blocking loop returns and the reconnect loop exits.

    ``healthy`` is ``False`` while the consumer is disconnected and
    trying to reconnect, so runners can surface a degraded state
    instead of reporting a zombie consumer as OK.
    """

    def __init__(
        self,
        client: RabbitmqClient,
        binder: "RmqBinder",
        setup: Callable[[RabbitmqClient], None],
        description: str,
    ) -> None:
        self._client = client
        self._binder = binder
        self._setup = setup
        self._description = description
        self._stopped = threading.Event()
        self._healthy = True

    @property
    def healthy(self) -> bool:
        """True when connected and consuming (or not yet started)."""
        return self._healthy

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
        backoff = _RECONNECT_BACKOFF_INITIAL
        while not self._stopped.is_set():
            try:
                self._client.start_consuming()
                if self._stopped.is_set():
                    break
                # start_consuming returned without close() — broker
                # cancelled us (queue deleted, forced disconnect).
                # Treat like a drop and reconnect.
                logger.warning(
                    "consume loop for %s returned unexpectedly — reconnecting",
                    self._description,
                )
            except Exception as e:  # noqa: BLE001
                if self._stopped.is_set():
                    break
                logger.warning(
                    "consume loop for %s dropped (%s: %s) — reconnecting",
                    self._description, type(e).__name__, e,
                )

            self._healthy = False
            while not self._stopped.is_set():
                # Event.wait doubles as an interruptible sleep so close()
                # never waits out a full backoff window.
                if self._stopped.wait(backoff):
                    break
                try:
                    try:
                        self._client.close_connection()
                    except Exception:  # noqa: BLE001 — half-dead conn
                        pass
                    self._client.connect()
                    self._setup(self._client)
                    self._healthy = True
                    logger.info("consumer for %s reconnected", self._description)
                    backoff = _RECONNECT_BACKOFF_INITIAL
                    break
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "reconnect for %s failed (%s) — next attempt in %.0fs",
                        self._description, e, min(backoff * 2, _RECONNECT_BACKOFF_MAX),
                    )
                    backoff = min(backoff * 2, _RECONNECT_BACKOFF_MAX)
        self._healthy = False


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
        if self._thread.is_alive():
            self._thread.join(timeout=5)
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
        self._publish_lock = threading.Lock()
        self._started = False

    # -- queue name resolution --------------------------------------------

    def _resolve_queue(self, route: RouteRef) -> str:
        """Pick the physical queue for a publish/consume target.

        Resolution order:

        1. ``route.physical_queue`` (X.1+ backend-pinned override) — the
           dispatcher already knows the destination queue from the
           liveness registry's announce; honor it verbatim and skip
           the legacy map.
        2. ``legacy_queue_map[subject]`` (MB3 production map) —
           translates symbolic subjects (``magellon.tasks.ctf``) to the
           legacy queue names plugins still bind on
           (``ctf_tasks_queue``).
        3. ``subject`` itself — last resort for ad-hoc / test routes
           that carry their own queue name as the subject.
        """
        physical = getattr(route, "physical_queue", None)
        if physical:
            return physical
        return self._queue_map.get(route.subject, route.subject)

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
        queue_name = self._resolve_queue(route)
        write_audit_entry(self._audit, route.subject, envelope)
        body = _body_from_envelope(envelope)
        properties = _ce_properties(envelope)

        def _do_publish() -> None:
            # Declare the queue (idempotent) then basic_publish directly
            # so we control properties. RabbitmqClient.publish_message
            # hard-codes delivery_mode and has no headers slot.
            self._client.declare_queue(queue_name)
            self._client.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=body,
                properties=properties,
            )

        try:
            with self._publish_lock:
                _do_publish()
            return PublishReceipt(ok=True, message_id=str(envelope.id))
        except (AMQPConnectionError, ChannelError, StreamLostError) as first_err:
            # Pika's BlockingConnection doesn't auto-reconnect — once the
            # broker drops us (idle timeout, broker restart, network blip)
            # every subsequent publish fails forever until the binder is
            # rebuilt. Reconnect once and retry; if it still fails, surface
            # the second error so callers see the real cause.
            logger.warning(
                "publish_task: %s on %s — reconnecting once",
                type(first_err).__name__, queue_name,
            )
            try:
                self._client.close_connection()
            except Exception:  # noqa: BLE001 — closing a half-dead conn can throw
                pass
            try:
                with self._publish_lock:
                    self._client.connect()
                    _do_publish()
                return PublishReceipt(ok=True, message_id=str(envelope.id))
            except (AMQPConnectionError, ChannelError, StreamLostError) as second_err:
                logger.error(
                    "publish_task failed for %s after reconnect: %s",
                    queue_name, second_err,
                )
                return PublishReceipt(
                    ok=False, message_id=str(envelope.id), error=str(second_err)
                )

    def consume_tasks(
        self,
        route: RouteRef,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
    ) -> ConsumerHandle:
        self._require_started()
        queue_name = self._resolve_queue(route)

        def _callback(ch, method, properties, body):
            redelivery_count = _redelivery_count(method, properties)
            try:
                envelope = _reconstruct_envelope(body, properties)
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
                    # Republish with an incremented redelivery header +
                    # ack the original. basic_nack(requeue=True) would
                    # lose the count (RMQ only carries a boolean
                    # `redelivered` flag), so the untyped-exception
                    # retry ceiling could never trigger and poison
                    # messages would hot-loop forever.
                    _requeue_with_count(
                        ch, method, properties, body,
                        queue_name=queue_name,
                        redelivery_count=redelivery_count,
                        retry_after_seconds=cls.retry_after_seconds,
                    )
                else:
                    # ACK or DLQ both nack-no-requeue; DLQ topology (if
                    # configured on the queue) routes to the dead-letter
                    # exchange.
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        def _setup(client: RabbitmqClient) -> None:
            client.declare_queue(queue_name)
            if policy.prefetch is not None:
                client.channel.basic_qos(prefetch_count=policy.prefetch)
            client.channel.basic_consume(
                queue=queue_name, on_message_callback=_callback
            )

        # New client so start_consuming can block a dedicated thread
        # without freezing the binder's publish channel.
        client = RabbitmqClient(self._settings)
        client.connect()
        _setup(client)

        handle = _RmqConsumerHandle(client, self, _setup, f"tasks:{queue_name}")
        with self._lock:
            self._consumer_handles.append(handle)
        return handle

    def purge_tasks(self, route: RouteRef) -> int:
        self._require_started()
        queue_name = self._resolve_queue(route)
        # passive=True: fail if the queue doesn't exist (matches today's
        # cancellation_service behavior — intentional safety).
        def _do_purge() -> int:
            frame = self._client.channel.queue_declare(queue=queue_name, passive=True)
            count = frame.method.message_count
            self._client.channel.queue_purge(queue=queue_name)
            return count

        try:
            with self._publish_lock:
                return _do_purge()
        except (AMQPConnectionError, StreamLostError) as first_err:
            logger.warning(
                "purge_tasks: %s on %s — reconnecting once",
                type(first_err).__name__,
                queue_name,
            )
            try:
                self._client.close_connection()
            except Exception:  # noqa: BLE001
                pass
            with self._publish_lock:
                self._client.connect()
                return _do_purge()

    # -- Events ------------------------------------------------------------

    def publish_event(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        self._require_started()
        exchange = exchange_for_subject(route.subject)
        body = _body_from_envelope(envelope)
        properties = _ce_properties(envelope)
        def _do_publish() -> None:
            self._client.channel.basic_publish(
                    exchange=exchange,
                    routing_key=route.subject,
                    body=body,
                    properties=properties,
                )

        try:
            with self._publish_lock:
                _do_publish()
            return PublishReceipt(ok=True, message_id=str(envelope.id))
        except (AMQPConnectionError, ChannelError, StreamLostError) as first_err:
            logger.warning(
                "publish_event: %s on %s/%s — reconnecting once",
                type(first_err).__name__, exchange, route.subject,
            )
            try:
                self._client.close_connection()
            except Exception:  # noqa: BLE001
                pass
            try:
                with self._publish_lock:
                    self._client.connect()
                    declare_event_exchanges(self._client.channel)
                    _do_publish()
                return PublishReceipt(ok=True, message_id=str(envelope.id))
            except (AMQPConnectionError, ChannelError, StreamLostError) as second_err:
                logger.error(
                    "publish_event failed on %s/%s after reconnect: %s",
                    exchange, route.subject, second_err,
                )
                return PublishReceipt(
                    ok=False, message_id=str(envelope.id), error=str(second_err)
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
                envelope = _reconstruct_envelope(body, properties)
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

    # -- RPC ---------------------------------------------------------------

    def call_rpc(self, route: RouteRef, envelope: Envelope, timeout: float) -> Envelope:
        """Blocking request/response over a **dedicated connection**.

        Pika's BlockingConnection is not thread-safe. The old
        implementation shared the binder's publish connection and
        busy-polled ``process_data_events`` on it without taking
        ``_publish_lock`` — a concurrent ``publish_task`` from another
        thread could corrupt the connection. A per-call connection is
        fully isolated (RPC is rare; connection setup is milliseconds)
        and cleans itself up on every path.
        """
        self._require_started()
        queue_name = self._resolve_queue(route)
        body = _body_from_envelope(envelope)
        response: Dict[str, Envelope] = {}
        correlation_id = str(envelope.id)

        client = RabbitmqClient(self._settings)
        client.connect()
        try:
            decl = client.channel.queue_declare(
                queue="", exclusive=True, auto_delete=True
            )
            reply_queue = decl.method.queue

            def _on_response(ch, method, properties, resp_body):
                if getattr(properties, "correlation_id", None) != correlation_id:
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    return
                response["envelope"] = _reconstruct_envelope(resp_body, properties)
                ch.basic_ack(delivery_tag=method.delivery_tag)

            client.channel.basic_consume(
                queue=reply_queue,
                on_message_callback=_on_response,
                auto_ack=False,
            )
            properties = _ce_properties(envelope)
            properties.reply_to = reply_queue
            properties.correlation_id = correlation_id
            client.declare_queue(queue_name)
            client.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=body,
                properties=properties,
            )

            deadline = datetime.now(timezone.utc).timestamp() + timeout
            while "envelope" not in response:
                if datetime.now(timezone.utc).timestamp() >= deadline:
                    raise TimeoutError(
                        f"RPC call to {route.subject!r} timed out after {timeout}s"
                    )
                client.connection.process_data_events(time_limit=0.05)
            return response["envelope"]
        finally:
            client.close_connection()

    def respond_rpc(
        self,
        route: RouteRef,
        handler: RpcHandler,
        policy: RpcPolicy,
    ) -> ConsumerHandle:
        self._require_started()
        queue_name = self._resolve_queue(route)

        def _callback(ch, method, properties, body):
            try:
                request = _reconstruct_envelope(body, properties)
                result = handler(request)
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                reply_to = getattr(properties, "reply_to", None)
                if reply_to:
                    reply_props = _ce_properties(result)
                    reply_props.correlation_id = getattr(properties, "correlation_id", None)
                    ch.basic_publish(
                        exchange="",
                        routing_key=reply_to,
                        body=_body_from_envelope(result),
                        properties=reply_props,
                    )
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                logger.exception("RPC responder failed on %s", queue_name)
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        def _setup(client: RabbitmqClient) -> None:
            client.declare_queue(queue_name)
            if policy.prefetch is not None:
                client.channel.basic_qos(prefetch_count=policy.prefetch)
            client.channel.basic_consume(
                queue=queue_name, on_message_callback=_callback
            )

        client = RabbitmqClient(self._settings)
        client.connect()
        _setup(client)
        handle = _RmqConsumerHandle(client, self, _setup, f"rpc:{queue_name}")
        with self._lock:
            self._consumer_handles.append(handle)
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

_REDELIVERY_HEADER = "x-magellon-redelivery"

#: Cap on how long the consumer thread will honor a RetryableError's
#: retry_after_seconds hint before republishing. Sleeping happens on the
#: consumer thread, so an unbounded hint could stall the whole queue.
_MAX_RETRY_DELAY_S = 30.0


def _redelivery_count(method: Any, properties: Any) -> int:
    """Read the redelivery count from AMQP headers.

    The requeue path republishes with an incremented
    ``x-magellon-redelivery`` header (see :func:`_requeue_with_count`),
    so the count is an honest integer. Legacy messages that arrived via
    a raw ``basic_nack(requeue=True)`` only carry the boolean
    ``redelivered`` flag — fall back to that.
    """
    if properties is not None and properties.headers:
        value = properties.headers.get(_REDELIVERY_HEADER)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return int(bool(getattr(method, "redelivered", False)))


def _requeue_with_count(
    ch: Any,
    method: Any,
    properties: Any,
    body: bytes,
    *,
    queue_name: str,
    redelivery_count: int,
    retry_after_seconds: Optional[float] = None,
) -> None:
    """Requeue by republishing with ``x-magellon-redelivery`` + 1, then
    acking the original delivery.

    This is what makes the untyped-exception retry ceiling real on
    RabbitMQ: ``basic_nack(requeue=True)`` redelivers with only a
    boolean flag, pinning the observable count at 1 forever. Semantics
    stay at-least-once — a crash between publish and ack duplicates the
    message, exactly like a crash before a plain nack would.

    ``retry_after_seconds`` (a RetryableError hint) is honored with a
    bounded sleep on the consumer thread; without it the republish is
    immediate, matching the old nack behavior.
    """
    if retry_after_seconds and retry_after_seconds > 0:
        time.sleep(min(float(retry_after_seconds), _MAX_RETRY_DELAY_S))

    headers: Dict[str, Any] = {}
    content_type = None
    if properties is not None:
        headers = dict(properties.headers or {})
        content_type = properties.content_type
    headers[_REDELIVERY_HEADER] = redelivery_count + 1

    try:
        ch.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=body,
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type=content_type,
                headers=headers,
            ),
        )
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:  # noqa: BLE001
        # Republish failed (connection dropping?) — fall back to a raw
        # nack so the message is never lost; the count stalls for this
        # hop but at-least-once delivery is preserved.
        logger.warning(
            "requeue republish on %s failed (%s); falling back to basic_nack",
            queue_name, e,
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# ---------------------------------------------------------------------------
# CloudEvents 1.0 binary content mode: body = data, headers = metadata
# ---------------------------------------------------------------------------

_CE_SPECVERSION = "ce-specversion"
_CE_ID = "ce-id"
_CE_SOURCE = "ce-source"
_CE_TYPE = "ce-type"
_CE_SUBJECT = "ce-subject"
_CE_TIME = "ce-time"
_CE_DATASCHEMA = "ce-dataschema"


def _body_from_envelope(envelope: Envelope) -> bytes:
    """Serialize ``envelope.data`` as the AMQP body.

    Pydantic model → ``model_dump_json()`` (keeps today's wire format
    for plugins decoding TaskMessage.model_validate_json(body)).
    Dict / list / primitive → ``json.dumps``.
    ``None`` → empty bytes.
    """
    data = envelope.data
    if data is None:
        return b""
    if hasattr(data, "model_dump_json"):
        return data.model_dump_json().encode("utf-8")
    return json.dumps(data).encode("utf-8")


def _ce_properties(envelope: Envelope) -> pika.BasicProperties:
    """Build AMQP properties carrying envelope metadata per CloudEvents
    binary content mode."""
    headers: Dict[str, Any] = {
        _CE_SPECVERSION: envelope.specversion,
        _CE_ID: str(envelope.id),
        _CE_SOURCE: envelope.source,
        _CE_TYPE: envelope.type,
        _CE_TIME: envelope.time.isoformat() if envelope.time else None,
    }
    if envelope.subject is not None:
        headers[_CE_SUBJECT] = envelope.subject
    if envelope.dataschema is not None:
        headers[_CE_DATASCHEMA] = envelope.dataschema
    return pika.BasicProperties(
        delivery_mode=2,
        content_type=envelope.datacontenttype,
        headers=headers,
    )


def _reconstruct_envelope(body: bytes, properties: Any) -> Envelope:
    """Rebuild an :class:`Envelope` from AMQP body + headers.

    If ``ce-*`` headers are absent (legacy publisher, pre-bus test
    fixture), synthesize an envelope with neutral defaults so the
    handler receives a uniform shape. This is the compat seam that
    keeps MB3 from breaking today's plugins.
    """
    headers: Dict[str, Any] = {}
    content_type = "application/json"
    if properties is not None:
        headers = dict(properties.headers or {})
        content_type = properties.content_type or content_type

    try:
        data = json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = body  # last resort — raw bytes; handler must cope

    time = _parse_ce_time(headers.get(_CE_TIME))

    return Envelope(
        specversion=headers.get(_CE_SPECVERSION, "1.0"),
        id=headers.get(_CE_ID) or str(uuid.uuid4()),
        source=headers.get(_CE_SOURCE, "unknown"),
        type=headers.get(_CE_TYPE, "unknown"),
        subject=headers.get(_CE_SUBJECT),
        time=time,
        datacontenttype=content_type,
        dataschema=headers.get(_CE_DATASCHEMA),
        data=data,
    )


def _parse_ce_time(value: Any) -> datetime:
    """Parse an ISO 8601 ``ce-time`` header; fall back to ``now()``."""
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value
    try:
        # pika returns header strings as bytes on some versions
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _invoke(handler: Callable, envelope: Envelope) -> None:
    """Invoke a handler; async handlers are run to completion.

    Sync handlers are first-class. An async handler's coroutine is
    executed with :func:`asyncio.run` on the consumer thread (which has
    no running loop), so its exceptions classify for retry/DLQ exactly
    like a sync handler's. Previously the coroutine was silently
    dropped and the delivery acked as success — a data-loss footgun.
    """
    result = handler(envelope)
    if asyncio.iscoroutine(result):
        asyncio.run(result)
    elif result is not None and hasattr(result, "__await__"):
        # Non-coroutine awaitable (rare) — drive it on a fresh loop too.
        async def _drive():
            return await result
        asyncio.run(_drive())


__all__ = ["RmqBinder"]
