"""Transport-neutral result-consumer registration (MB4.B).

Every service that projects plugin results into its own data store
(CoreService's ``TaskOutputProcessor``, the self-hosted
``magellon_result_processor`` plugin, a future analytics consumer)
registers the same shape on the bus:

1. Iterate a set of :class:`TaskRoute` subjects.
2. Call ``bus.tasks.consumer(route, handler)`` per subject.
3. Keep the returned :class:`ConsumerHandle` objects around so
   shutdown can close them cleanly.

That's all this module does. The *handler* is caller-supplied and
owns everything transport-specific to the consumer's domain (envelope
decoding into a Pydantic shape, DB session handling, file projection,
exception classification). The bus is passed in explicitly — this
service never calls :func:`get_bus` itself, which keeps callers free
to inject a mock bus in tests without having to patch the service's
own module namespace.

MB4.B moved this out of ``CoreService/core/result_consumer.py`` so the
same code paths back the in-process result consumer and any
out-of-process processor that wants to ride the bus. CoreService's
wrapper at ``core/result_consumer.py`` now delegates here.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Iterable, List

from magellon_sdk.bus.interfaces import ConsumerHandle, MessageBus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.envelope import Envelope

logger = logging.getLogger(__name__)


# Handler protocol: takes one decoded :class:`Envelope`, returns
# ``None`` on success (binder acks) or raises (binder's classifier
# decides ack / requeue / DLQ based on the exception type).
ResultHandler = Callable[[Envelope], None]


def start_result_consumers(
    routes: Iterable[TaskRoute],
    handler: ResultHandler,
    bus: MessageBus,
) -> List[ConsumerHandle]:
    """Register one ``bus.tasks.consumer`` per route.

    Returns the list of :class:`ConsumerHandle` objects so the caller
    (typically a startup module) can close them cleanly on shutdown.
    Caller is responsible for de-duplicating routes — calling twice on
    overlapping sets produces duplicate consumers, which splits each
    delivery round-robin (see ``project_result_processor_double_consume``
    memory).

    An empty ``routes`` iterable is a no-op: returns an empty list
    without touching the bus. Callers that want a dormancy log line
    should emit it themselves before calling this function — the
    wording depends on which config surface produced the empty list.
    """
    handles: List[ConsumerHandle] = []
    for route in routes:
        handles.append(bus.tasks.consumer(route, handler))
        logger.info("result_consumer: subscribed to %s", route.subject)
    return handles


def result_consumer_engine(
    routes: Iterable[TaskRoute],
    handler: ResultHandler,
    bus: MessageBus,
) -> None:
    """Register consumers and block the caller's thread until shutdown.

    Intended as a ``threading.Thread(target=...)`` target. Returns
    immediately (no-op) if ``routes`` is empty. On ``KeyboardInterrupt``
    or when any consumer thread exits, closes all handles and returns.

    Each ``ConsumerHandle`` owns its own pika connection and needs its
    own ``run_until_shutdown`` loop. Pre-2026-05-13 this function only
    called ``handles[0].run_until_shutdown()`` — every additional
    route's queue was declared and the consumer registered, but the
    consume loop never started, so RMQ delivered exactly zero of its
    messages even though the management UI showed the queue had
    publishes. Symptom: ``ctf_out_tasks_queue`` (first in the OUT_QUEUES
    list) processed results; ``particle_extraction_out_tasks_queue`` /
    ``two_d_classification_out_tasks_queue`` accumulated unread
    messages and ``TaskOutputProcessor._maybe_write_artifact`` never
    fired, so downstream classifier dispatches couldn't find their
    ``particle_stack`` artifact.
    """
    handles = start_result_consumers(routes, handler, bus)
    if not handles:
        return
    # Spawn a daemon thread per handle so every consumer's loop runs.
    # First handle stays on this thread for ``threading.Thread`` callers
    # that pass this function as ``target=`` and expect it to block.
    extra_threads: List[threading.Thread] = []
    for h in handles[1:]:
        t = threading.Thread(
            target=h.run_until_shutdown,
            name=f"result-consumer-{id(h):x}",
            daemon=True,
        )
        t.start()
        extra_threads.append(t)
    try:
        handles[0].run_until_shutdown()
    except KeyboardInterrupt:
        logger.info("result_consumer: interrupted, exiting")
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:  # noqa: BLE001 — shutdown best-effort
                logger.exception("result_consumer: handle close failed")


__all__ = [
    "ResultHandler",
    "result_consumer_engine",
    "start_result_consumers",
]
