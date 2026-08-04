"""Audited process execution boundary.

All new external-process calls should go through this module.  Commands are
argument vectors, never shell strings, and failures retain the executable and
return code while avoiding accidental secret leakage in logs.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

logger = logging.getLogger(__name__)


class ProcessExecutionError(RuntimeError):
    def __init__(self, command: Sequence[str], message: str, returncode: int | None = None):
        self.command = tuple(command)
        self.returncode = returncode
        executable = self.command[0] if self.command else "<empty>"
        super().__init__(f"{executable} failed: {message}")


def run_process(
    command: Sequence[str],
    *,
    timeout: float = 60.0,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    if not command or any(not isinstance(part, str) or not part for part in command):
        raise ValueError("command must be a non-empty sequence of non-empty strings")
    try:
        result = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise ProcessExecutionError(command, str(exc)) from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "no output").strip()
        logger.warning("external_process_failed executable=%s returncode=%s", command[0], result.returncode)
        raise ProcessExecutionError(command, detail, result.returncode)
    return result

