"""Executor contract.

An :class:`Executor` carries a plugin invocation (input payload) to
wherever the compute actually runs — in-process, in a local Docker
container, on a Kubernetes Job, on a RunPod serverless endpoint, on a
SLURM cluster — and surfaces progress + result back to the host.

This module defines the protocol only. Implementations live in Phase 3
and later (see Documentation/IMPLEMENTATION_PLAN.md §3).

Design notes
------------
- The executor is *per-invocation*, not a long-running service. The
  host creates one, calls ``submit``, holds the returned
  :class:`ExecutionHandle`, and later calls ``await_result`` / ``cancel``.
- Progress flows through the supplied :class:`ProgressReporter` — the
  executor does not invent its own event path. This keeps the
  progress story uniform regardless of where the plugin runs.
- Async because every non-trivial executor (Docker, Kubernetes, RunPod)
  does network I/O.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from magellon_sdk.progress import ProgressReporter


class ExecutorSpec(BaseModel):
    """Serializable description of where/how a plugin should run.

    Lives alongside the plugin's input payload on the wire so the
    decision "run on RunPod" vs "run in-process" can travel through
    Temporal / NATS rather than being hard-coded on each host.
    """

    kind: str
    """Executor type, e.g. ``localprocess``, ``localdocker``, ``k8s``,
    ``runpod``, ``slurm``. Executors look themselves up by this key."""

    config: Dict[str, Any] = {}
    """Executor-specific config (image tag, endpoint id, resource
    limits, GPU count, ...). Each executor validates its own slice."""


class ExecutionHandle(BaseModel):
    """Opaque reference to an in-flight execution.

    Concrete executors attach their own identifiers (container id,
    RunPod request id, k8s job name) via ``extra`` so the host doesn't
    need to know implementation details to cancel or poll.
    """

    model_config = {"extra": "allow"}

    executor_kind: str
    execution_id: str


@runtime_checkable
class Executor(Protocol):
    """The minimal surface every executor implements."""

    kind: str
    """Unique identifier — matches :attr:`ExecutorSpec.kind`."""

    async def submit(
        self,
        *,
        plugin_id: str,
        input_payload: Dict[str, Any],
        spec: ExecutorSpec,
        reporter: ProgressReporter,
    ) -> ExecutionHandle:
        """Start the execution and return a handle immediately.

        The host persists the handle so the work survives a host
        restart (Temporal activity resumption, etc.).
        """
        ...

    async def await_result(
        self,
        handle: ExecutionHandle,
        *,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Block until the execution finishes and return its output dict.

        Raises a subclass of :class:`Exception` on failure. The host is
        responsible for mapping that to a domain result.
        """
        ...

    async def cancel(self, handle: ExecutionHandle) -> None:
        """Best-effort cancellation.

        Idempotent: calling cancel on an already-finished execution is
        a no-op, not an error.
        """
        ...


__all__ = ["Executor", "ExecutorSpec", "ExecutionHandle"]
