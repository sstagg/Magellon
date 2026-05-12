"""Submit a plugin invocation to a Slurm cluster via ``sbatch``.

Lifecycle:

1. ``submit`` writes the input payload + a generated sbatch script into
   ``run_dir`` on the shared filesystem and runs
   ``sbatch --parsable submit.sh``. Returns once the scheduler has
   accepted the job — the job itself may sit in the queue for hours
   before running.
2. ``await_result`` polls ``squeue`` for active state; once the job is
   no longer in the queue, ``sacct`` provides the terminal state.
   Returns the result on ``COMPLETED``; raises :class:`ExecutionFailed`
   otherwise.
3. ``cancel`` shells out to ``scancel``.

Configuration via :attr:`ExecutorSpec.config`:

* ``command`` — argv template (required). Same placeholders as the local
  executors. Quoted with :func:`shlex.join` before being written into
  the sbatch body.
* ``partition``, ``cpus``, ``gpus``, ``memory``, ``time``, ``account``,
  ``qos``, ``nodes``, ``constraint`` — translated into matching
  ``#SBATCH`` directives.
* ``pre_script`` — list of shell lines emitted before the command
  (``module load …`` / ``source activate …``).
* ``extra_sbatch`` — list of additional raw ``#SBATCH …`` lines for
  options this executor doesn't model explicitly.

The shared filesystem assumption is intentional: Magellon's data plane
already assumes a POSIX namespace visible to every plugin worker
(see ``Documentation/DATA_PLANE.md``). ``run_dir`` MUST land somewhere
the compute nodes can read.
"""
from __future__ import annotations

import asyncio
import os
import shlex
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from magellon_sdk.executor.base import ExecutionHandle, ExecutorSpec
from magellon_sdk.executor.impls._common import (
    ExecutionFailed,
    ExecutionNotFound,
    ProcessRunner,
    default_run_cmd,
    read_result,
    substitute_placeholders,
    tail,
    write_payload,
)
from magellon_sdk.progress import ProgressReporter


SUCCESS_STATES = frozenset({"COMPLETED"})
FAILURE_STATES = frozenset(
    {
        "FAILED",
        "TIMEOUT",
        "CANCELLED",
        "NODE_FAIL",
        "BOOT_FAIL",
        "DEADLINE",
        "OUT_OF_MEMORY",
        "PREEMPTED",
        "REVOKED",
    }
)
TERMINAL_STATES = SUCCESS_STATES | FAILURE_STATES


class SlurmExecutor:
    """Carry a plugin invocation onto a Slurm cluster via ``sbatch``."""

    kind = "slurm"

    def __init__(
        self,
        work_dir: Optional[Path] = None,
        *,
        sbatch: str = "sbatch",
        squeue: str = "squeue",
        scancel: str = "scancel",
        sacct: str = "sacct",
        poll_interval_s: float = 10.0,
        process_runner: ProcessRunner = default_run_cmd,
    ) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.gettempdir()) / "magellon-slurm"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.sbatch = sbatch
        self.squeue = squeue
        self.scancel = scancel
        self.sacct = sacct
        self.poll_interval_s = poll_interval_s
        self._run = process_runner
        self._known: Dict[str, ExecutionHandle] = {}

    async def submit(
        self,
        *,
        plugin_id: str,
        input_payload: Dict[str, Any],
        spec: ExecutorSpec,
        reporter: ProgressReporter,
    ) -> ExecutionHandle:
        command_template = spec.config.get("command")
        if not command_template:
            raise ValueError("slurm executor requires spec.config['command']")

        execution_id = uuid.uuid4().hex
        run_dir = self.work_dir / execution_id
        payload_path = write_payload(run_dir, input_payload)
        result_path = run_dir / "result.json"
        log_path = run_dir / "slurm.out"
        script_path = run_dir / "submit.sh"

        argv = substitute_placeholders(
            list(command_template),
            payload=str(payload_path),
            result=str(result_path),
            run_dir=str(run_dir),
            log=str(log_path),
        )

        script = self._render_sbatch_script(
            plugin_id=plugin_id,
            argv=argv,
            log_path=log_path,
            config=spec.config,
        )
        script_path.write_text(script, encoding="utf-8")
        try:
            os.chmod(script_path, 0o755)
        except OSError:
            pass  # Windows fs / read-only mounts; sbatch reads the file directly

        rc, stdout, stderr = await self._run(
            [self.sbatch, "--parsable", str(script_path)]
        )
        if rc != 0:
            raise ExecutionFailed(
                f"sbatch-{rc}",
                tail(stderr.decode("utf-8", "replace")),
            )
        # --parsable prints "JOBID" or "JOBID;CLUSTER"
        slurm_job_id = stdout.decode("utf-8", "replace").strip().split(";")[0]
        if not slurm_job_id:
            raise ExecutionFailed("sbatch-no-jobid", tail(stderr.decode("utf-8", "replace")))

        reporter.report(0, f"slurm job {slurm_job_id} submitted")

        handle = ExecutionHandle(
            executor_kind=self.kind,
            execution_id=execution_id,
            slurm_job_id=slurm_job_id,
            result_path=str(result_path),
            log_path=str(log_path),
            script_path=str(script_path),
            run_dir=str(run_dir),
        )
        self._known[execution_id] = handle
        return handle

    async def await_result(
        self,
        handle: ExecutionHandle,
        *,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        slurm_job_id = getattr(handle, "slurm_job_id", None)
        if not slurm_job_id:
            raise ExecutionNotFound(handle.execution_id)

        deadline = None if timeout_s is None else time.monotonic() + timeout_s

        while True:
            state = await self._job_state(slurm_job_id)
            if state in TERMINAL_STATES:
                break
            if deadline is not None and time.monotonic() >= deadline:
                raise asyncio.TimeoutError(
                    f"slurm job {slurm_job_id} did not finish within {timeout_s}s"
                )
            await asyncio.sleep(self.poll_interval_s)

        if state not in SUCCESS_STATES:
            log = _read_text(getattr(handle, "log_path", None))
            raise ExecutionFailed(state, tail(log))

        return read_result(Path(handle.result_path))

    async def cancel(self, handle: ExecutionHandle) -> None:
        slurm_job_id = getattr(handle, "slurm_job_id", None)
        if not slurm_job_id:
            return
        await self._run([self.scancel, slurm_job_id])

    # -- internal -----------------------------------------------------------

    def _render_sbatch_script(
        self,
        *,
        plugin_id: str,
        argv: List[str],
        log_path: Path,
        config: Dict[str, Any],
    ) -> str:
        safe_plugin = plugin_id.replace("/", "-").replace(" ", "_")
        lines: List[str] = ["#!/bin/bash"]
        lines.append(f"#SBATCH --job-name=magellon-{safe_plugin}")
        lines.append(f"#SBATCH --output={log_path}")
        lines.append(f"#SBATCH --error={log_path}")
        lines.append("#SBATCH --ntasks=1")

        directive_map = [
            ("partition", "--partition"),
            ("account", "--account"),
            ("qos", "--qos"),
            ("cpus", "--cpus-per-task"),
            ("memory", "--mem"),
            ("time", "--time"),
            ("nodes", "--nodes"),
            ("constraint", "--constraint"),
        ]
        for key, flag in directive_map:
            value = config.get(key)
            if value is None or value == "":
                continue
            lines.append(f"#SBATCH {flag}={value}")

        gpus = config.get("gpus")
        if gpus:
            lines.append(f"#SBATCH --gres=gpu:{gpus}")

        for extra in config.get("extra_sbatch") or []:
            extra = str(extra).strip()
            if not extra.startswith("#SBATCH"):
                extra = "#SBATCH " + extra
            lines.append(extra)

        lines.append("")
        lines.append("set -euo pipefail")

        for pre in config.get("pre_script") or []:
            lines.append(str(pre))

        lines.append("")
        lines.append(shlex.join(argv))
        lines.append("")
        return "\n".join(lines)

    async def _job_state(self, slurm_job_id: str) -> str:
        # squeue covers PENDING / RUNNING / SUSPENDED. A finished job
        # falls off the queue, at which point sacct is the source of
        # truth for the terminal state. We intentionally try squeue
        # first since it's cheaper than sacct on busy clusters.
        rc, stdout, _ = await self._run(
            [self.squeue, "-h", "-j", slurm_job_id, "-o", "%T"]
        )
        if rc == 0:
            text = stdout.decode("utf-8", "replace").strip()
            if text:
                return text.splitlines()[0].split()[0].upper()

        rc, stdout, _ = await self._run(
            [self.sacct, "-j", slurm_job_id, "-n", "-X", "-o", "State", "-P"]
        )
        if rc != 0:
            return "UNKNOWN"
        text = stdout.decode("utf-8", "replace").strip()
        if not text:
            return "UNKNOWN"
        # sacct may emit e.g. "CANCELLED by 1001" — take the first token
        return text.splitlines()[0].split()[0].upper()


def _read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


__all__ = ["SlurmExecutor", "SUCCESS_STATES", "FAILURE_STATES", "TERMINAL_STATES"]
