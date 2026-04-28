"""In-memory broker binder — real broker semantics, no RabbitMQ needed.

``MockBinder`` (see :mod:`magellon_sdk.bus.binders.mock`) dispatches
synchronously inside the publish call. That's right for unit tests
that assert shape, but wrong for integration tests that want the
broker's actual behavior: producers and consumers on different
threads, queue-backed delivery, ack/nack routing, DLQ on poison.

:class:`InMemoryBinder` fills that gap. A pure-Python broker-shaped
binder with:

- one :class:`queue.Queue` per task subject (point-to-point, round-robin
  when multiple consumers compete)
- one :class:`queue.Queue` per event subscriber (fanout — publish walks
  all matching subscribers and pushes into each one's queue)
- consumer / subscriber threads that block on their queue and dispatch
  to the handler as deliveries arrive
- ack / nack / DLQ honored via :func:`classify_exception` — identical
  routing logic to :class:`RmqBinder`
- redelivery counter tracked in the ``x-magellon-redelivery`` header
  (same header name as RMQ; incremented on requeue so classify has a
  truthful count)
- :meth:`wait_for_drain` — test utility that blocks until every queue
  is empty and every in-flight handler has returned; the usual
  assertion point for integration-style tests.

Not a drop-in for load tests: this lives inside one Python process
and inherits the GIL. It's a correctness-test aid, not a benchmark
target.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from magellon_sdk.bus.binders.mock import _matches
from magellon_sdk.bus.interfaces import (
    ConsumerHandle,
    EventHandler,
    PatternRef,
    RouteRef,
    SubscriptionHandle,
    TaskHandler,
)
from magellon_sdk.bus.policy import PublishReceipt, TaskConsumerPolicy
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import AckAction, classify_exception

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Delivery record — body + headers, the in-memory analogue of an AMQP frame
# ---------------------------------------------------------------------------

class _Delivery:
    """One message sitting on an in-memory queue.

    Carries body bytes + the ``ce-*`` header dict so consumers can
    reconstruct an :class:`Envelope` the same way the RMQ binder does.
    Redelivery tracking is mutable on the delivery itself (not a new
    object) so a requeue keeps identity — easier to reason about in
    tests.
    """

    __slots__ = ("body", "headers", "content_type", "redelivery_count", "subject")

    def __init__(
        self,
        *,
        body: bytes,
        headers: Dict[str, Any],
        content_type: str,
        subject: str,
    ) -> None:
        self.body = body
        self.headers = headers
        self.content_type = content_type
        self.subject = subject
        self.redelivery_count = 0


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------

class _InMemoryConsumerHandle:
    def __init__(
        self,
        binder: "InMemoryBinder",
        subject: str,
        thread: threading.Thread,
        stop_event: threading.Event,
    ) -> None:
        self._binder = binder
        self._subject = subject
        self._thread = thread
        self._stop = stop_event
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        # Push a sentinel so the blocking get() returns immediately.
        self._binder._task_queues[self._subject].put(_STOP_SENTINEL)
        self._thread.join(timeout=5)

    def run_until_shutdown(self) -> None:
        """Block until ``close()`` is called. Matches the RMQ binder's
        semantic — consumer threads continue in the background either
        way; this just waits."""
        self._stop.wait()


class _InMemorySubscriptionHandle:
    def __init__(
        self,
        binder: "InMemoryBinder",
        entry_id: str,
        thread: threading.Thread,
        stop_event: threading.Event,
    ) -> None:
        self._binder = binder
        self._entry_id = entry_id
        self._thread = thread
        self._stop = stop_event
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        # Enqueue a sentinel on the subscriber's personal queue.
        sub_queue = self._binder._subscriber_queues.pop(self._entry_id, None)
        if sub_queue is not None:
            sub_queue.put(_STOP_SENTINEL)
        self._binder._remove_subscriber(self._entry_id)
        self._thread.join(timeout=5)


_STOP_SENTINEL = object()


# ---------------------------------------------------------------------------
# InMemoryBinder
# ---------------------------------------------------------------------------

class InMemoryBinder:
    """Broker-like binder backed by :class:`queue.Queue` + threads."""

    name = "inmemory"

    def __init__(self) -> None:
        self._started = False
        self._lock = threading.Lock()

        # Task queues: subject → FIFO Queue[_Delivery | _STOP_SENTINEL]
        self._task_queues: Dict[str, "queue.Queue"] = defaultdict(queue.Queue)
        # Subject → list of consumer registration records
        self._task_consumers: Dict[str, List[Tuple[TaskHandler, TaskConsumerPolicy, _InMemoryConsumerHandle]]] = defaultdict(list)
        # DLQ storage: subject → list of deliveries routed to DLQ
        self._dlq: Dict[str, List[_Delivery]] = defaultdict(list)

        # Event subscribers: per-subscriber personal queue so fanout
        # writes into N queues and each subscriber's thread drains its
        # own. entry_id → (glob, handler, queue)
        self._subscribers: Dict[str, Tuple[str, EventHandler, "queue.Queue"]] = {}
        self._subscriber_queues: Dict[str, "queue.Queue"] = {}

        # In-flight counter for wait_for_drain.
        self._in_flight = 0
        self._in_flight_cond = threading.Condition(self._lock)

        # Captures for assertions.
        self.published_tasks: List[Tuple[str, Envelope]] = []
        self.published_events: List[Tuple[str, Envelope]] = []

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._started = True

    def close(self) -> None:
        # Copy to avoid mutation-during-iteration; handles remove
        # themselves from the list as they close.
        with self._lock:
            handles_to_close: List[Any] = []
            for subj_consumers in self._task_consumers.values():
                for _handler, _policy, handle in subj_consumers:
                    handles_to_close.append(handle)
            for entry_id in list(self._subscribers.keys()):
                handles_to_close.append(entry_id)  # close via subscriber lookup
        for item in handles_to_close:
            if isinstance(item, _InMemoryConsumerHandle):
                item.close()
            else:
                # subscriber entry_id path: find & close
                pass  # handled via _remove_subscriber
        self._started = False

    # -- Work queue --------------------------------------------------------

    def publish_task(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        # X.7+: backend-pinned routes carry a physical_queue override.
        # Mirror the RMQ binder's _resolve_queue so test doubles are
        # faithful — a backend-pinned task lands on the resolver's
        # queue, not the symbolic subject.
        physical_queue = getattr(route, "physical_queue", None)
        queue_key = physical_queue or route.subject
        # Audit & inspection still keep the symbolic subject so test
        # assertions can grep for it; tests that want the physical
        # destination read it off the queue dict keys.
        subject = route.subject
        self.published_tasks.append((subject, envelope))
        delivery = _delivery_from_envelope(envelope, subject)
        # Only count toward in-flight if a consumer is registered —
        # otherwise the message sits in the queue with no side effect
        # to wait for and wait_for_drain would hang forever. Tests
        # that want to inspect un-consumed publishes assert on
        # ``published_tasks`` directly.
        with self._in_flight_cond:
            has_consumer = bool(self._task_consumers.get(queue_key))
            if has_consumer:
                self._in_flight += 1
        self._task_queues[queue_key].put(delivery)
        if not has_consumer:
            # Tag delivery so the consumer loop knows not to decrement
            # if it shows up later. Simplest: mark on the delivery.
            delivery.headers.setdefault("_inmemory_uncounted", True)
        return PublishReceipt(ok=True, message_id=str(envelope.id))

    def consume_tasks(
        self,
        route: RouteRef,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
    ) -> ConsumerHandle:
        subject = route.subject
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._consumer_loop,
            args=(subject, handler, policy, stop_event),
            name=f"inmemory-consumer-{subject}",
            daemon=True,
        )
        handle = _InMemoryConsumerHandle(self, subject, thread, stop_event)
        with self._lock:
            self._task_consumers[subject].append((handler, policy, handle))
        thread.start()
        return handle

    def purge_tasks(self, route: RouteRef) -> int:
        q = self._task_queues.get(route.subject)
        if q is None:
            return 0
        count = 0
        with self._in_flight_cond:
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    break
                if item is _STOP_SENTINEL:
                    q.put(_STOP_SENTINEL)  # put back; consumer needs this to exit
                    break
                count += 1
                self._in_flight -= 1
            self._in_flight_cond.notify_all()
        return count

    # -- Events ------------------------------------------------------------

    def publish_event(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        subject = route.subject
        self.published_events.append((subject, envelope))
        # Fanout: find every subscriber whose glob matches, push into
        # their personal queue.
        with self._lock:
            matching = [
                (eid, g)
                for eid, (g, _h, _q) in self._subscribers.items()
                if _matches(g, subject)
            ]
        for entry_id, _glob in matching:
            sub_queue = self._subscriber_queues.get(entry_id)
            if sub_queue is None:
                continue
            delivery = _delivery_from_envelope(envelope, subject)
            with self._in_flight_cond:
                self._in_flight += 1
            sub_queue.put(delivery)
        return PublishReceipt(ok=True, message_id=str(envelope.id))

    def subscribe_events(
        self, pattern: PatternRef, handler: EventHandler
    ) -> SubscriptionHandle:
        entry_id = str(uuid.uuid4())
        sub_queue: "queue.Queue" = queue.Queue()
        with self._lock:
            self._subscribers[entry_id] = (pattern.subject_glob, handler, sub_queue)
            self._subscriber_queues[entry_id] = sub_queue
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._subscriber_loop,
            args=(entry_id, handler, stop_event),
            name=f"inmemory-subscriber-{pattern.subject_glob}",
            daemon=True,
        )
        handle = _InMemorySubscriptionHandle(self, entry_id, thread, stop_event)
        thread.start()
        return handle

    # -- Consumer / subscriber loops --------------------------------------

    def _consumer_loop(
        self,
        subject: str,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
        stop_event: threading.Event,
    ) -> None:
        q = self._task_queues[subject]
        while not stop_event.is_set():
            try:
                item = q.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is _STOP_SENTINEL:
                return
            delivery: _Delivery = item
            uncounted = delivery.headers.pop("_inmemory_uncounted", False)
            try:
                self._dispatch_task_delivery(delivery, handler, policy)
            finally:
                if not uncounted:
                    with self._in_flight_cond:
                        self._in_flight -= 1
                        self._in_flight_cond.notify_all()

    def _dispatch_task_delivery(
        self,
        delivery: _Delivery,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
    ) -> None:
        try:
            envelope = _envelope_from_delivery(delivery)
            result = handler(envelope)
            # If the handler returned an awaitable, the in-memory binder
            # doesn't drive an event loop — log and move on (matches
            # RmqBinder behavior).
            if result is not None and hasattr(result, "__await__"):
                logger.debug(
                    "InMemoryBinder: handler returned awaitable on %s; dropping",
                    delivery.subject,
                )
            # Success → ack (nothing to do in memory; removal from queue already happened)
        except Exception as exc:
            cls = classify_exception(
                exc, redelivery_count=delivery.redelivery_count
            )
            logger.debug(
                "InMemoryBinder[%s]: %s → %s (%s)",
                delivery.subject,
                type(exc).__name__,
                cls.action.value,
                cls.reason,
            )
            if cls.action is AckAction.REQUEUE:
                delivery.redelivery_count += 1
                delivery.headers["x-magellon-redelivery"] = delivery.redelivery_count
                with self._in_flight_cond:
                    self._in_flight += 1  # re-enqueued, still in-flight
                self._task_queues[delivery.subject].put(delivery)
            else:
                # ACK or DLQ — DLQ routing if policy enabled.
                if policy.dlq_enabled:
                    self._dlq[delivery.subject].append(delivery)

    def _subscriber_loop(
        self,
        entry_id: str,
        handler: EventHandler,
        stop_event: threading.Event,
    ) -> None:
        sub_queue = self._subscriber_queues.get(entry_id)
        if sub_queue is None:
            return
        while not stop_event.is_set():
            try:
                item = sub_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is _STOP_SENTINEL:
                return
            delivery: _Delivery = item
            try:
                envelope = _envelope_from_delivery(delivery)
                handler(envelope)
            except Exception:
                logger.exception(
                    "InMemoryBinder: event handler failed on %s",
                    delivery.subject,
                )
            finally:
                with self._in_flight_cond:
                    self._in_flight -= 1
                    self._in_flight_cond.notify_all()

    def _remove_subscriber(self, entry_id: str) -> None:
        with self._lock:
            self._subscribers.pop(entry_id, None)

    # -- Test helpers ------------------------------------------------------

    def wait_for_drain(self, timeout: float = 5.0) -> bool:
        """Block until every queue is empty and every handler returned.

        Returns ``True`` if drained cleanly, ``False`` if the timeout
        elapsed first. The canonical assertion point for tests that
        publish through real code paths and want to inspect the effect
        without sleeping."""
        deadline = time.monotonic() + timeout
        with self._in_flight_cond:
            while self._in_flight > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._in_flight_cond.wait(timeout=remaining)
        return True

    def dlq_for(self, subject: str) -> List[_Delivery]:
        """Deliveries routed to this subject's DLQ (inspect in tests)."""
        return list(self._dlq.get(subject, []))


# ---------------------------------------------------------------------------
# Serialization helpers — same wire shape as RmqBinder
# ---------------------------------------------------------------------------

def _delivery_from_envelope(envelope: Envelope, subject: str) -> _Delivery:
    data = envelope.data
    if data is None:
        body = b""
    elif hasattr(data, "model_dump_json"):
        body = data.model_dump_json().encode("utf-8")
    else:
        body = json.dumps(data).encode("utf-8")

    headers: Dict[str, Any] = {
        "ce-specversion": envelope.specversion,
        "ce-id": str(envelope.id),
        "ce-source": envelope.source,
        "ce-type": envelope.type,
        "ce-time": envelope.time.isoformat() if envelope.time else None,
    }
    if envelope.subject is not None:
        headers["ce-subject"] = envelope.subject
    if envelope.dataschema is not None:
        headers["ce-dataschema"] = envelope.dataschema
    return _Delivery(
        body=body,
        headers=headers,
        content_type=envelope.datacontenttype,
        subject=subject,
    )


def _envelope_from_delivery(delivery: _Delivery) -> Envelope:
    try:
        data = json.loads(delivery.body.decode("utf-8")) if delivery.body else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = delivery.body

    headers = delivery.headers
    return Envelope(
        specversion=headers.get("ce-specversion", "1.0"),
        id=headers.get("ce-id") or str(uuid.uuid4()),
        source=headers.get("ce-source", "unknown"),
        type=headers.get("ce-type", "unknown"),
        subject=headers.get("ce-subject"),
        time=_parse_time(headers.get("ce-time")),
        datacontenttype=delivery.content_type,
        dataschema=headers.get("ce-dataschema"),
        data=data,
    )


def _parse_time(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


__all__ = ["InMemoryBinder"]
