"""Executor protocols.

Where a plugin *runs* is orthogonal to what it *does*. Plugins are
written against `PluginBase`; executors (local process, local Docker,
Kubernetes Job, RunPod, SLURM, ...) carry a plugin invocation to
wherever the compute lives.

At 0.1.0 this package ships only the protocol stub. Concrete
implementations land in Phase 3.
"""
from __future__ import annotations

from magellon_sdk.executor.base import Executor, ExecutorSpec, ExecutionHandle

__all__ = ["Executor", "ExecutorSpec", "ExecutionHandle"]
