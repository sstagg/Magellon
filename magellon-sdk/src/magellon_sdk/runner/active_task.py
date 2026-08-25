"""Plugin-runner shared plumbing: active task + step-event helpers.

Pre-2.1 every plugin (FFT, MotionCor, CTF, topaz, ptolemy) duplicated
~80 lines of identical glue:

* a ContextVar holding the currently-processing :class:`TaskMessage`
  so :meth:`PluginBase.execute` can recover ``job_id`` / ``task_id``
  for step events;
* a daemon-thread asyncio loop so synchronous ``execute()`` running
  inside pika's consumer thread can ``await`` the async step-event
  publisher without spinning up + tearing down a loop per task (which
  stalled pika heartbeats);
* an ``_emit(coro)`` helper that swallows publisher failures so a
  flaky observability path can't abort a successful compute;
* a ``_make_reporter()`` helper that pulls the active task, lazily
  initialises the publisher, and binds a :class:`BoundStepReporter`.

This module owns those four. :class:`PluginBrokerRunner` populates the
ContextVar on each delivery; plugin code calls
:func:`make_step_reporter` and :func:`emit_step` directly.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from contextvars import ContextVar, Token
from typing import Awaitable, Callable, Optional

from magellon_sdk.events import BoundStepReporter, StepEventPublisher
from magellon_sdk.models import TaskMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active-task ContextVar
# ---------------------------------------------------------------------------
# The runner sets this before each delivery via :func:`set_active_task` and
# resets it via the token returned. ContextVar (rather than thread-local)
# so the value follows the logical task even if a future async refactor
# moves work between threads.

_active_task: ContextVar[Optional[TaskMessage]] = ContextVar(
    "magellon_active_task", default=None
)


def current_task() -> Optional[TaskMessage]:
    """Return the :class:`TaskMessage` for the in-flight delivery, or
    ``None`` outside of a runner-driven context (tests, REPL)."""
    return _active_task.get()


def set_active_task(task: Optional[TaskMessage]) -> Token:
    """Set the active task; returns a token the caller passes to
    :func:`reset_active_task`. The runner uses these inside a
    try/finally; plugin code rarely needs them."""
    return _active_task.set(task)


def reset_active_task(token: Token) -> None:
    """Clear the active task back to its prior value."""
    _active_task.reset(token)


# ---------------------------------------------------------------------------
# Daemon-thread asyncio loop for step-event emission
# ---------------------------------------------------------------------------
# One long-lived loop per process. ``asyncio.run()`` per emit would spin
# up + tear down a loop for every task and stall pika's heartbeat long
# enough for the broker to drop the connection (the gotcha the old
# rabbitmq_consumer_engine tripped over).

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def get_step_event_loop() -> asyncio.AbstractEventLoop:
    """Singleton daemon-thread event loop for async step-event work."""
    global _loop
    if _loop is not None:
        return _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(
                target=_loop.run_forever,
                name="magellon-step-events",
                daemon=True,
            ).start()
    return _loop


# ---------------------------------------------------------------------------
# Sync-from-async helpers used by plugin.execute()
# ---------------------------------------------------------------------------

def emit_step(coro: Awaitable, *, timeout: float = 5.0) -> None:
    """Run a step-event coroutine on the daemon loop, blocking up to
    ``timeout`` seconds. Swallow + log any failure — a flaky observability
    path must never abort an otherwise-successful compute.

    On timeout, explicitly cancels the underlying task. Without this,
    future.result(timeout=...) only stops *waiting* — the coroutine
    keeps running (and, for a publisher stuck retrying a broken
    connection, keeps failing and retrying) on the shared daemon loop
    forever. Under concurrent callers sharing this loop (e.g. a plugin
    running multiple broker-runner threads that all emit through it —
    ptolemy runs one for square detection and one for hole detection),
    these orphaned tasks piled up and were the direct cause of an
    unbounded memory leak in production (confirmed live: RSS climbing
    to 1-1.5GB within minutes, tracking one-to-one with a burst of NATS
    "no responders" publish failures).
    """
    loop = get_step_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        logger.warning("step-event emit timed out after %.1fs — cancelled", timeout)
    except Exception:
        logger.exception("step-event emit failed (non-fatal)")


PublisherFactory = Callable[[], Awaitable[Optional[StepEventPublisher]]]


def make_step_reporter(
    step_name: str,
    publisher_factory: PublisherFactory,
    *,
    init_timeout: float = 15.0,
) -> Optional[BoundStepReporter]:
    """Build a :class:`BoundStepReporter` for the active task.

    Returns ``None`` when:
      * there is no active task (running outside the runner — REPL, test)
      * the publisher factory raised or returned None (step events
        disabled or transport unavailable)

    ``init_timeout`` covers the cold-start path that pays for NATS
    JetStream ``add_stream`` + RMQ exchange declare. After the first
    successful call, ``publisher_factory`` is module-cached and returns
    in microseconds.
    """
    task = current_task()
    if task is None:
        return None
    loop = get_step_event_loop()
    future = asyncio.run_coroutine_threadsafe(publisher_factory(), loop)
    try:
        publisher = future.result(timeout=init_timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        logger.warning(
            "step-event publisher init timed out after %.1fs — cancelled", init_timeout
        )
        return None
    except Exception:
        logger.exception("step-event publisher init failed (non-fatal)")
        return None
    if publisher is None:
        return None
    return BoundStepReporter(
        publisher,
        job_id=task.job_id,
        task_id=task.id,
        step=step_name,
    )


__all__ = [
    "current_task",
    "set_active_task",
    "reset_active_task",
    "get_step_event_loop",
    "emit_step",
    "make_step_reporter",
    "PublisherFactory",
]
