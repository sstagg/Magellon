"""Bundled executor implementations.

These are dormant — no code path in CoreService or any plugin instantiates
them today. Plugin / host authors opt in by constructing the executor
and threading it through their own dispatch path. The contract every
impl satisfies is :class:`magellon_sdk.executor.Executor`.

Implementations carry plugin invocations to different compute targets:

* :class:`LocalProcessExecutor` — subprocess on the calling host. The
  default / reference impl; matches what a plugin author would do if
  they called the algorithm directly.
* :class:`LocalDockerExecutor` — ``docker run`` on the calling host.
  Useful when the algorithm has a heavy runtime (CUDA, vendored
  binaries) that's awkward to install on the host.
* :class:`SlurmExecutor` — ``sbatch`` onto a Slurm-managed cluster.
  Useful for HPC deployments where the host doesn't own GPUs directly.

Common error types live alongside in :mod:`magellon_sdk.executor.impls`.
"""
from __future__ import annotations

from magellon_sdk.executor.impls._common import (
    ExecutionFailed,
    ExecutionNotFound,
    ExecutorError,
    ProcessRunner,
)
from magellon_sdk.executor.impls.local_docker import LocalDockerExecutor
from magellon_sdk.executor.impls.local_process import LocalProcessExecutor
from magellon_sdk.executor.impls.slurm import SlurmExecutor

__all__ = [
    "ExecutionFailed",
    "ExecutionNotFound",
    "ExecutorError",
    "LocalDockerExecutor",
    "LocalProcessExecutor",
    "ProcessRunner",
    "SlurmExecutor",
]
