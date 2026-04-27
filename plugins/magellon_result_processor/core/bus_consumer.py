"""MB4.4 cutover: subscribe to result queues via the bus.

Replaces the hand-rolled ``rabbitmq_consumer_engine.py`` (legacy
:class:`RabbitmqClient.consume` loop) with one ``bus.tasks.consumer``
subscription per ``OUT_QUEUES`` entry. The binder owns the pika loop,
ack/nack/DLQ classification, and reconnection. This module owns:

* what to subscribe to (each ``OUT_QUEUES.name`` becomes a
  ``TaskRoute.named(...)``),
* what handler to run on each delivery (decode envelope to
  :class:`TaskResultMessage`, run the existing ``do_execute``).

Mirrors :mod:`CoreService.core.result_consumer` (MB4.5) — same shape,
different container. Kept here so the out-of-tree result_processor
plugin stays self-hostable for deployments that still use it.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import List

from magellon_sdk.bus import ConsumerHandle, get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

from magellon_sdk.models import TaskResultMessage
from core.settings import AppSettingsSingleton
from services.service import do_execute

logger = logging.getLogger(__name__)

# One long-lived loop on a daemon thread for running the async
# ``do_execute`` from the binder's sync handler invocation. Same
# rationale as plugin/plugin.py in the FFT plugin: asyncio.run() per
# delivery would burn a fresh loop each time.
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(
    target=_loop.run_forever, name="result-processor-loop", daemon=True,
)
_loop_thread.start()


def _make_handler():
    """Bind a bus-shaped handler that decodes one envelope and runs the
    existing ``do_execute`` to project the result into the DB + on-disk
    output dirs."""

    def _on_envelope(envelope: Envelope) -> None:
        try:
            task_result = TaskResultMessage.model_validate(envelope.data)
        except Exception as exc:
            # Malformed payload won't decode on retry — DLQ via PermanentError.
            raise PermanentError(f"undecodable TaskResultMessage: {exc}") from exc

        future = asyncio.run_coroutine_threadsafe(do_execute(task_result), _loop)
        try:
            future.result()
        except Exception as exc:
            # do_execute swallows its own exceptions today, but be
            # defensive — surfacing as PermanentError lets the binder
            # DLQ instead of redelivering forever.
            raise PermanentError(f"processor failed: {exc}") from exc

    return _on_envelope


def start_result_consumers() -> List[ConsumerHandle]:
    """Register one bus consumer per ``OUT_QUEUES`` entry.

    Empty ``OUT_QUEUES`` returns an empty list — the plugin then runs
    as an HTTP-only surface (``/execute`` still works). ``main.py``
    calls this once at startup; the handles are kept on app.state so
    shutdown can close them.
    """
    out_queues = AppSettingsSingleton.get_instance().rabbitmq_settings.OUT_QUEUES
    if not out_queues:
        logger.info(
            "result_processor: OUT_QUEUES empty — staying dormant. "
            "Add entries to rabbitmq_settings.OUT_QUEUES to enable."
        )
        return []

    handler = _make_handler()
    bus = get_bus()
    handles: List[ConsumerHandle] = []
    for q in out_queues:
        route = TaskRoute.named(q.name)
        handles.append(bus.tasks.consumer(route, handler))
        logger.info("result_processor: subscribed to %s", q.name)
    return handles


__all__ = ["start_result_consumers"]
