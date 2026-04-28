"""TaskDispatcher — uniform surface for sending a task to its worker.

Background
----------

Today CoreService decides how a task reaches its worker with a
hand-rolled switch in ``core/helper.py::get_queue_name_by_task_type``::

    if task_type.code == 5: return settings.MOTIONCOR_QUEUE_NAME
    if task_type.code == 2: return settings.CTF_QUEUE_NAME
    ...

Adding a new plugin means editing that function, adding two settings
fields (task + result queue), and remembering to update every call site
that cares about queue names. It also bakes in "plugins always run via
RabbitMQ" — the in-process and (eventually) Kubernetes/RunPod paths
would each need their own switch.

The :class:`TaskDispatcher` protocol replaces the switch with one
abstraction: a dispatcher per plugin, looked up by task-type code.

Implementations
---------------

- :class:`RabbitmqTaskDispatcher` wraps
  :func:`magellon_sdk.messaging.publish_message_to_queue`. It's a thin
  wrapper so the current production path works unchanged.
- :class:`InProcessTaskDispatcher` invokes a caller-supplied async
  callable directly (for small jobs, tests, or when the orchestrator
  chooses not to go through RMQ).

Consumers select a dispatcher via :class:`TaskDispatcherRegistry` which
is injected from configuration, not hard-coded.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol, runtime_checkable

from magellon_sdk.models import TaskCategory, TaskMessage

logger = logging.getLogger(__name__)

TaskHandler = Callable[[TaskMessage], Awaitable[bool]]


@runtime_checkable
class TaskDispatcher(Protocol):
    """Anything that can hand a :class:`TaskMessage` to its worker."""

    name: str
    """Short identifier for logs / introspection (e.g. ``"rabbitmq-ctf"``)."""

    def dispatch(self, task: TaskMessage) -> bool:
        """Synchronously dispatch ``task``.

        Returns ``True`` if the task was accepted (queued, executed,
        …), ``False`` on failure. Implementations that do network I/O
        should not raise on transient errors — log and return ``False``
        so the caller can fall back or retry.
        """
        ...


class RabbitmqTaskDispatcher:
    """Dispatch via the shared :class:`RabbitmqClient`.

    ``queue_name`` is owned by the dispatcher — callers no longer need
    to know which queue maps to which task type. ``rabbitmq_settings``
    is anything that quacks like ``BaseAppSettings.rabbitmq_settings``.
    """

    def __init__(self, *, queue_name: str, rabbitmq_settings: Any, name: Optional[str] = None) -> None:
        self.queue_name = queue_name
        self.rabbitmq_settings = rabbitmq_settings
        self.name = name or f"rabbitmq:{queue_name}"

    def dispatch(self, task: TaskMessage) -> bool:
        # Imported lazily so this module doesn't force pika onto every
        # caller — dispatch.py is imported by callers that may never
        # touch RabbitMQ.
        from magellon_sdk.messaging import publish_message_to_queue

        return publish_message_to_queue(task, self.queue_name, rabbitmq_settings=self.rabbitmq_settings)


class InProcessTaskDispatcher:
    """Dispatch by calling ``handler`` directly in the current process.

    ``handler`` may be sync or async. If async, it is run via
    :func:`asyncio.run` from a thread that has no running loop, or via
    :func:`asyncio.run_coroutine_threadsafe` from one that does. This
    matches the pattern already used in the plugin consumer engines.

    Intended for tests and small-job orchestration. Long-running
    workloads should stay on an executor (see
    :mod:`magellon_sdk.executor.base`).
    """

    def __init__(self, *, handler: Callable[[TaskMessage], Any], name: str = "in-process") -> None:
        self.handler = handler
        self.name = name

    def dispatch(self, task: TaskMessage) -> bool:
        try:
            result = self.handler(task)
            if inspect.isawaitable(result):
                self._run_coroutine(result)
            return True
        except Exception as e:  # noqa: BLE001
            logger.exception("InProcessTaskDispatcher(%s) failed: %s", self.name, e)
            return False

    @staticmethod
    def _run_coroutine(coro: Awaitable[Any]) -> Any:
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # There's a running loop on this thread — schedule on it and
        # block. This is unusual for in-process dispatch but keeps the
        # API honest.
        future = asyncio.run_coroutine_threadsafe(coro, running)
        return future.result()


class TaskDispatcherRegistry:
    """Lookup table: ``TaskCategory.code`` → :class:`TaskDispatcher`.

    Built from configuration so CoreService doesn't have to know which
    dispatcher strategy any given plugin uses. Callers do::

        registry = TaskDispatcherRegistry()
        registry.register(CTF_TASK, RabbitmqTaskDispatcher(...))
        registry.register(MOTIONCOR, InProcessTaskDispatcher(...))

        registry.dispatch(task)  # looks up by task.type.code
    """

    def __init__(self) -> None:
        self._by_code: Dict[int, TaskDispatcher] = {}

    def register(self, task_type: TaskCategory, dispatcher: TaskDispatcher) -> None:
        self._by_code[task_type.code] = dispatcher

    def get(self, task_type: TaskCategory) -> Optional[TaskDispatcher]:
        return self._by_code.get(task_type.code)

    def dispatch(self, task: TaskMessage) -> bool:
        if task.type is None:
            logger.error("Task %s has no type — cannot dispatch", task.id)
            return False
        dispatcher = self.get(task.type)
        if dispatcher is None:
            logger.error(
                "No dispatcher registered for task type %s (code=%s)",
                task.type.name,
                task.type.code,
            )
            return False
        return dispatcher.dispatch(task)


__all__ = [
    "InProcessTaskDispatcher",
    "RabbitmqTaskDispatcher",
    "TaskDispatcher",
    "TaskDispatcherRegistry",
    "TaskHandler",
]
