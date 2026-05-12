"""Run a plugin invocation as a local subprocess on the host that calls
:meth:`submit`.

Configuration via :attr:`ExecutorSpec.config`:

* ``command`` — argv template. ``{payload}`` / ``{result}`` / ``{run_dir}``
  / ``{log}`` placeholders are substituted before exec. Required.
* ``env`` — extra env vars layered over ``os.environ`` for the child.
* ``cwd`` — working directory for the child (defaults to ``run_dir``).

The child writes its result to ``{result}`` (``result.json``); stdout +
stderr are merged into ``{log}`` so failures surface a tail of the
captured output.

This executor exists for two cases: development boxes without Docker,
and as the canonical reference impl other executors can mirror.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from magellon_sdk.executor.base import ExecutionHandle, ExecutorSpec
from magellon_sdk.executor.impls._common import (
    ExecutionFailed,
    ExecutionNotFound,
    read_result,
    substitute_placeholders,
    tail,
    write_payload,
)
from magellon_sdk.progress import ProgressReporter


class LocalProcessExecutor:
    """Spawn the plugin invocation as a child process; track by PID."""

    kind = "localprocess"

    def __init__(self, work_dir: Optional[Path] = None) -> None:
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.gettempdir()) / "magellon-localproc"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._procs: Dict[str, asyncio.subprocess.Process] = {}

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
            raise ValueError("localprocess executor requires spec.config['command']")

        execution_id = uuid.uuid4().hex
        run_dir = self.work_dir / execution_id
        payload_path = write_payload(run_dir, input_payload)
        result_path = run_dir / "result.json"
        log_path = run_dir / "stdout.log"

        argv = substitute_placeholders(
            list(command_template),
            payload=str(payload_path),
            result=str(result_path),
            run_dir=str(run_dir),
            log=str(log_path),
        )

        env = os.environ.copy()
        for k, v in (spec.config.get("env") or {}).items():
            env[str(k)] = str(v)

        cwd = spec.config.get("cwd") or str(run_dir)

        log_f = log_path.open("wb")
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=log_f,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
                cwd=cwd,
            )
        except FileNotFoundError as exc:
            log_f.close()
            raise ExecutionFailed("exec-not-found", str(exc)) from exc

        self._procs[execution_id] = proc
        reporter.report(0, f"localprocess pid={proc.pid}")

        return ExecutionHandle(
            executor_kind=self.kind,
            execution_id=execution_id,
            pid=proc.pid,
            result_path=str(result_path),
            log_path=str(log_path),
            run_dir=str(run_dir),
        )

    async def await_result(
        self,
        handle: ExecutionHandle,
        *,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        proc = self._procs.get(handle.execution_id)
        if proc is None:
            raise ExecutionNotFound(handle.execution_id)

        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            raise

        log_text = _read_log(handle)

        if proc.returncode != 0:
            raise ExecutionFailed(f"exit-{proc.returncode}", tail(log_text))

        return read_result(Path(handle.result_path))

    async def cancel(self, handle: ExecutionHandle) -> None:
        proc = self._procs.get(handle.execution_id)
        if proc is None or proc.returncode is not None:
            return  # not running — idempotent
        try:
            proc.terminate()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


def _read_log(handle: ExecutionHandle) -> str:
    log_path = getattr(handle, "log_path", None)
    if not log_path:
        return ""
    p = Path(log_path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


__all__ = ["LocalProcessExecutor"]
