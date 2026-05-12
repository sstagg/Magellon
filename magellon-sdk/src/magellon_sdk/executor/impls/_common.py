"""Internal helpers shared by the bundled executor implementations.

Three things live here:

* ``ProcessRunner`` / ``default_run_cmd`` — the seam every executor uses to
  shell out. Tests inject a fake; production uses the asyncio subprocess
  default. Keeping it pluggable lets us unit-test Docker / Slurm executors
  without those CLIs installed.
* Error types raised by all executor impls.
* ``substitute_placeholders`` — formats ``{payload}`` / ``{result}`` /
  ``{run_dir}`` / ``{log}`` tokens inside a command template.

This module is private; callers should import from
``magellon_sdk.executor.impls``.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Tuple

ProcessRunner = Callable[..., Awaitable[Tuple[int, bytes, bytes]]]
"""``(argv, *, env=None) -> (returncode, stdout, stderr)``.

A short-lived shellout. Long-running processes (the LocalProcess case)
go through :func:`asyncio.create_subprocess_exec` directly so the caller
keeps the ``Process`` handle for terminate/kill.
"""


async def default_run_cmd(
    argv: List[str],
    *,
    env: Optional[Mapping[str, str]] = None,
) -> Tuple[int, bytes, bytes]:
    """Run ``argv`` to completion, returning ``(rc, stdout, stderr)``."""
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=dict(env) if env is not None else None,
    )
    out, err = await proc.communicate()
    return (proc.returncode if proc.returncode is not None else -1), out, err


class ExecutorError(Exception):
    """Base for executor failures."""


class ExecutionNotFound(ExecutorError):
    """Handle does not correspond to a known submission on this executor."""


class ExecutionFailed(ExecutorError):
    """Underlying compute exited non-zero or entered a terminal error state.

    ``reason`` is a short tag (the exit code, Slurm state, etc.).
    ``log_tail`` is the last few KB of captured output, when available.
    """

    def __init__(self, reason: str, log_tail: str = "") -> None:
        self.reason = reason
        self.log_tail = log_tail
        msg = f"executor failed: {reason}"
        if log_tail:
            msg += f"\n--- log tail ---\n{log_tail}"
        super().__init__(msg)


def substitute_placeholders(
    template: List[str],
    **values: str,
) -> List[str]:
    """Expand ``{payload}`` / ``{result}`` / etc. in a command template.

    Unknown placeholders are left intact so a typo surfaces in the
    executed command rather than silently disappearing.
    """
    out: List[str] = []
    for arg in template:
        try:
            out.append(arg.format(**values))
        except (KeyError, IndexError):
            out.append(arg)
    return out


def write_payload(run_dir: Path, payload: Dict[str, Any]) -> Path:
    """Materialize the input payload as ``input.json`` inside ``run_dir``."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "input.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def read_result(result_path: Path) -> Dict[str, Any]:
    """Load the executor's ``result.json``, raising ExecutionFailed if absent."""
    if not result_path.exists():
        raise ExecutionFailed("missing-result", f"no result.json at {result_path}")
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExecutionFailed("malformed-result", str(exc)) from exc


def tail(text: str, max_chars: int = 4000) -> str:
    """Return the last ``max_chars`` of a text blob for error display."""
    if len(text) <= max_chars:
        return text
    return "...[truncated]...\n" + text[-max_chars:]


__all__ = [
    "ExecutionFailed",
    "ExecutionNotFound",
    "ExecutorError",
    "ProcessRunner",
    "default_run_cmd",
    "read_result",
    "substitute_placeholders",
    "tail",
    "write_payload",
]
