"""Broker-native CTF plugin built on the SDK ``PluginBrokerRunner`` (MB4.2).

Replaces ``core/rabbitmq_consumer_engine.py``. The runner now owns the
pika loop, ack/nack/DLQ classification, discovery, heartbeat, dynamic
config, provenance stamping, and reconnection — this module declares
the plugin's identity, its input schema, and the wrapper that calls
the existing ``do_ctf`` compute.

Pragmatic wrapping vs. the cleaner FFT pattern:

The FFT plugin's ``execute()`` returns a typed ``FftOutput`` that
``build_fft_result`` then wraps in a TaskResultMessage. CTF can't follow
that pattern verbatim without a 200-line refactor of
``service/ctf_service.py``, which today builds the full TaskResultMessage
inline (three separate branches for the success / eval-failed / error
cases). Instead we use ``CtfPluginOutput`` as a thin wrapper around
the TaskResultMessage that ``do_ctf`` already returns; ``build_ctf_result``
unwraps it. The compute logic stays untouched.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from contextvars import ContextVar
from typing import Optional, Type

from pydantic import BaseModel, ConfigDict

from magellon_sdk.base import PluginBase
from magellon_sdk.models import (
    PluginInfo,
    TaskMessage,
    TaskResultMessage,
)
from magellon_sdk.models.manifest import (
    Capability,
    IsolationLevel,
    ResourceHints,
    Transport,
)
from magellon_sdk.models.tasks import CtfInput
from magellon_sdk.progress import NullReporter, ProgressReporter
from magellon_sdk.runner import PluginBrokerRunner

from service.ctf_service import do_ctf
from service.step_events import (
    STEP_NAME,
    get_publisher,
    safe_emit_completed,
    safe_emit_failed,
    safe_emit_progress,
    safe_emit_started,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Active-task context
# ---------------------------------------------------------------------------
# Same pattern FFT uses. Set by CtfBrokerRunner._handle_task / _process
# before the inner execute() runs; cleared in finally.
_active_task: ContextVar[Optional[TaskMessage]] = ContextVar(
    "_ctf_active_task", default=None
)


def get_active_task() -> Optional[TaskMessage]:
    return _active_task.get()


# ---------------------------------------------------------------------------
# Daemon-thread asyncio loop for ``do_ctf`` (async) + step-event emits.
# One per process — see plugin/plugin.py in the FFT plugin for the rationale.
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is not None:
        return _loop
    with _loop_lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            t = threading.Thread(
                target=_loop.run_forever, name="ctf-runner-loop", daemon=True,
            )
            t.start()
    return _loop


# ---------------------------------------------------------------------------
# Output wrapper
# ---------------------------------------------------------------------------

class CtfPluginOutput(BaseModel):
    """Pydantic shell carrying the TaskResultMessage that ``do_ctf`` builds.

    Why a wrapper rather than a typed ``CtfOutput`` from the SDK: see
    the module docstring. ``build_ctf_result`` unwraps this into the
    TaskResultMessage the bus publishes.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    result_dto: TaskResultMessage


# ---------------------------------------------------------------------------
# CtfPlugin
# ---------------------------------------------------------------------------

class CtfPlugin(PluginBase[CtfInput, CtfPluginOutput]):
    """Broker-native CTF plugin.

    ``execute()`` is sync — invoked from the binder's pika consumer
    thread. ``do_ctf`` is async, so we bridge via the daemon loop.
    Step events follow the same best-effort pattern as the rest of the
    plugin: a failed emit must never abort the CTF compute.
    """

    capabilities = [
        Capability.CPU_INTENSIVE,
        Capability.IDEMPOTENT,
    ]
    supported_transports = [
        Transport.RMQ,
        Transport.NATS,
        Transport.HTTP,
    ]
    default_transport = Transport.RMQ
    isolation = IsolationLevel.CONTAINER
    resource_hints = ResourceHints(
        memory_mb=1_000, cpu_cores=1, typical_duration_seconds=10.0,
    )
    tags = ["ctf", "imaging"]

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="CTF Plugin",
            version="1.0.2",
            developer="Behdad Khoshbin b.khoshbin@gmail.com & Puneeth Reddy",
            description="Defocus/astigmatism estimation via the ctffind4 binary",
        )

    @classmethod
    def input_schema(cls) -> Type[CtfInput]:
        return CtfInput

    @classmethod
    def output_schema(cls) -> Type[CtfPluginOutput]:
        return CtfPluginOutput

    # ------------------------------------------------------------------
    # Step-event helpers (sync wrappers around the async safe_emit_*)
    # ------------------------------------------------------------------

    def _emit(self, coro) -> None:
        loop = _get_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            future.result(timeout=15.0)
        except Exception:
            logger.exception("step-event emit failed (non-fatal)")

    def _publisher(self):
        loop = _get_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(get_publisher(), loop)
            return future.result(timeout=15.0)
        except Exception:
            logger.exception("step-event publisher init failed (non-fatal)")
            return None

    # ------------------------------------------------------------------
    # Core execute
    # ------------------------------------------------------------------

    def execute(
        self,
        input_data: CtfInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> CtfPluginOutput:
        task = _active_task.get()
        if task is None:
            # Direct call without the runner setting context — happens
            # in unit tests. Fall back to running do_ctf synchronously
            # against a synthesized TaskMessage if needed; for now we raise
            # since plugin tests always go through the runner.
            raise RuntimeError("CtfPlugin.execute called outside CtfBrokerRunner context")

        publisher = self._publisher()
        job_id, task_id = task.job_id, task.id
        self._emit(safe_emit_started(publisher, job_id=job_id, task_id=task_id))
        try:
            self._emit(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=10.0, message="running ctffind",
            ))
            # do_ctf is async — bridge via the daemon loop.
            future = asyncio.run_coroutine_threadsafe(do_ctf(task), _get_loop())
            result_dto: TaskResultMessage = future.result()

            self._emit(safe_emit_progress(
                publisher, job_id=job_id, task_id=task_id,
                percent=85.0, message="publishing result",
            ))
            self._emit(safe_emit_completed(publisher, job_id=job_id, task_id=task_id))
            return CtfPluginOutput(result_dto=result_dto)
        except Exception as exc:
            self._emit(safe_emit_failed(
                publisher, job_id=job_id, task_id=task_id, error=str(exc),
            ))
            raise


# ---------------------------------------------------------------------------
# CtfBrokerRunner
# ---------------------------------------------------------------------------

class CtfBrokerRunner(PluginBrokerRunner):
    """Runner subclass that exposes the active TaskMessage via ContextVar.

    Same shape as FftBrokerRunner — overrides ``_handle_task`` (MB4
    bus path) and ``_process`` (legacy bytes path used by tests) to
    wrap the inner execution in a ContextVar set/reset.
    """

    def _handle_task(self, envelope) -> None:
        task = self._task_from_envelope(envelope)
        token = _active_task.set(task)
        try:
            super()._handle_task(envelope)
        finally:
            _active_task.reset(token)

    def _process(self, body: bytes) -> bytes:
        text = body.decode("utf-8")
        task = TaskMessage.model_validate_json(text)
        token = _active_task.set(task)
        try:
            self._apply_pending_config()
            input_schema = self.plugin.input_schema()
            validated = input_schema.model_validate(task.data)
            plugin_output = self.plugin.run(validated)
            result = self.result_factory(task, plugin_output)
            self._stamp_provenance(result)
            return result.model_dump_json().encode("utf-8")
        finally:
            _active_task.reset(token)


# ---------------------------------------------------------------------------
# Result factory
# ---------------------------------------------------------------------------

def build_ctf_result(task: TaskMessage, output: CtfPluginOutput) -> TaskResultMessage:
    """Unwrap the CtfPluginOutput shell. ``do_ctf`` already built the
    full TaskResultMessage inside; this just hands it to the runner for
    publishing."""
    return output.result_dto


__all__ = [
    "CtfBrokerRunner",
    "CtfPlugin",
    "CtfPluginOutput",
    "build_ctf_result",
    "get_active_task",
]
