"""In-memory binder for unit tests.

``MockBinder`` satisfies the :class:`Binder` Protocol without touching
any broker. Publishes dispatch synchronously to registered handlers
and capture lists (``published_tasks``, ``published_events``) let
tests assert what went over the wire.

Wildcard matching is NATS-style: ``*`` = exactly one segment, ``>`` =
one-or-more tail segments. Matches what ``EventPattern`` documents
and what the RMQ binder will translate.
"""
from __future__ import annotations

import inspect
import threading
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from magellon_sdk.bus.interfaces import (
    Binder,
    ConsumerHandle,
    EventHandler,
    PatternRef,
    RouteRef,
    SubscriptionHandle,
    TaskHandler,
)
from magellon_sdk.bus.policy import PublishReceipt, TaskConsumerPolicy
from magellon_sdk.envelope import Envelope


# ---------------------------------------------------------------------------
# Subject glob matching
# ---------------------------------------------------------------------------

def _matches(glob: str, subject: str) -> bool:
    """Match a NATS-style glob against a dot-separated subject.

    ``*`` matches exactly one segment; ``>`` matches any tail (one or
    more segments — though this helper also accepts zero tail segments,
    matching RMQ ``#`` semantics, which is the more permissive of the
    two and safe for our use because every route has at least one
    non-wildcard prefix segment).
    """
    g_parts = glob.split(".")
    s_parts = subject.split(".")
    i = 0
    while i < len(g_parts):
        if g_parts[i] == ">":
            return i == len(g_parts) - 1
        if i >= len(s_parts):
            return False
        if g_parts[i] != "*" and g_parts[i] != s_parts[i]:
            return False
        i += 1
    return i == len(s_parts)


# ---------------------------------------------------------------------------
# Handles
# ---------------------------------------------------------------------------

class _MockConsumerHandle:
    """Implements :class:`ConsumerHandle` for the mock binder.

    ``close()`` unregisters the handler and unblocks any pending
    ``run_until_shutdown`` on this handle. Safe to call twice.
    """

    def __init__(self, binder: "MockBinder", subject: str, handler: TaskHandler) -> None:
        self._binder = binder
        self._subject = subject
        self._handler = handler
        self._closed = threading.Event()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._binder._unregister_consumer(self._subject, self._handler)
        self._closed.set()

    def run_until_shutdown(self) -> None:
        """Block until ``close()`` is called. For synchronous tests
        this is almost always called with a pre-set close event."""
        self._closed.wait()


class _MockSubscriptionHandle:
    """Implements :class:`SubscriptionHandle` for the mock binder."""

    def __init__(
        self, binder: "MockBinder", entry: Tuple[str, EventHandler]
    ) -> None:
        self._binder = binder
        self._entry = entry
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._binder._unregister_subscription(self._entry)
        self._closed = True


# ---------------------------------------------------------------------------
# MockBinder
# ---------------------------------------------------------------------------

class MockBinder:
    """In-process binder for tests. No broker I/O, no threads.

    Attributes exposed for assertions:

    - ``published_tasks``    — list of ``(subject, envelope)`` tuples, in publish order
    - ``published_events``   — list of ``(subject, envelope)`` tuples, in publish order
    - ``handler_returns``    — non-``None`` envelopes returned from task handlers
    - ``purge_counts``       — list of ``(subject, count)`` tuples, in purge order
    """

    name = "mock"

    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self._task_consumers: Dict[str, List[Tuple[TaskHandler, TaskConsumerPolicy]]] = defaultdict(list)
        self._event_subscribers: List[Tuple[str, EventHandler]] = []
        self.published_tasks: List[Tuple[str, Envelope]] = []
        self.published_events: List[Tuple[str, Envelope]] = []
        self.handler_returns: List[Envelope] = []
        self.purge_counts: List[Tuple[str, int]] = []

    # -- Binder lifecycle --------------------------------------------------

    def start(self) -> None:
        self.started = True

    def close(self) -> None:
        self.closed = True

    # -- Work queue --------------------------------------------------------

    def publish_task(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        subject = route.subject
        self.published_tasks.append((subject, envelope))
        for handler, _policy in list(self._task_consumers.get(subject, [])):
            result = handler(envelope)
            if inspect.isawaitable(result):
                # Mock binder doesn't run an event loop — tests that
                # register async handlers must drive them themselves.
                # We silently drop the awaitable here; assertions on
                # ``handler_returns`` would notice if this happened.
                continue
            if result is not None:
                self.handler_returns.append(result)
        return _receipt()

    def consume_tasks(
        self,
        route: RouteRef,
        handler: TaskHandler,
        policy: TaskConsumerPolicy,
    ) -> ConsumerHandle:
        self._task_consumers[route.subject].append((handler, policy))
        return _MockConsumerHandle(self, route.subject, handler)

    def purge_tasks(self, route: RouteRef) -> int:
        subject = route.subject
        count = sum(1 for s, _ in self.published_tasks if s == subject)
        self.published_tasks = [(s, e) for s, e in self.published_tasks if s != subject]
        self.purge_counts.append((subject, count))
        return count

    # -- Events ------------------------------------------------------------

    def publish_event(self, route: RouteRef, envelope: Envelope) -> PublishReceipt:
        subject = route.subject
        self.published_events.append((subject, envelope))
        for glob, handler in list(self._event_subscribers):
            if _matches(glob, subject):
                result = handler(envelope)
                if inspect.isawaitable(result):
                    continue
        return _receipt()

    def subscribe_events(
        self,
        pattern: PatternRef,
        handler: EventHandler,
    ) -> SubscriptionHandle:
        entry = (pattern.subject_glob, handler)
        self._event_subscribers.append(entry)
        return _MockSubscriptionHandle(self, entry)

    # -- internals ---------------------------------------------------------

    def _unregister_consumer(self, subject: str, handler: TaskHandler) -> None:
        self._task_consumers[subject] = [
            (h, p) for h, p in self._task_consumers[subject] if h is not handler
        ]

    def _unregister_subscription(self, entry: Tuple[str, EventHandler]) -> None:
        try:
            self._event_subscribers.remove(entry)
        except ValueError:
            pass


def _new_id() -> str:
    return str(uuid.uuid4())


def _receipt() -> PublishReceipt:
    return PublishReceipt(ok=True, message_id=_new_id())


__all__ = ["MockBinder"]
