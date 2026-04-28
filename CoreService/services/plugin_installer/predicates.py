"""Host predicate detection + evaluation (P4).

The archive manifest's ``install[i].requires:`` list says what the
host must offer for an install method to apply (``docker_daemon``,
``binary: ctffind4``, ``python: ">=3.11"``, ``gpu_count_min: 1``,
``os: linux``, ``arch: x86_64``).

This module:

  - :class:`HostInfo` — what we know about the running host, gathered
    once per install attempt.
  - :func:`detect_host_info` — populates a ``HostInfo`` by probing
    the system. Best-effort: a probe that fails (e.g. ``nvidia-smi``
    not installed) reports zero/None rather than raising — the
    install method's ``requires`` then refuses to match, which is
    what we want.
  - :func:`evaluate_predicates` — given a list of predicates and a
    HostInfo, returns the failed ones (empty = all pass).
"""
from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from magellon_sdk.archive.manifest import SdkCompatError, check_sdk_compat

logger = logging.getLogger(__name__)


@dataclass
class HostInfo:
    """Snapshot of the host's install-relevant capabilities."""

    docker_daemon: bool = False
    """``docker info`` succeeds."""

    binaries_on_path: List[str] = field(default_factory=list)
    """Names of binaries the host claims have available — populated
    lazily by :func:`detect_host_info` from a caller-supplied probe
    list, since enumerating all of PATH is wasteful."""

    python_version: str = ""
    """e.g. ``3.12.3``. The running interpreter's version, used to
    decide if a ``python: ">=3.11"`` predicate passes for uv installs."""

    gpu_count: int = 0
    """nvidia-smi reports ≥ this many GPUs. 0 means no GPU OR
    nvidia-smi missing — treat as same in predicates."""

    os: str = ""
    """``linux`` / ``windows`` / ``macos``."""

    arch: str = ""
    """``x86_64`` / ``arm64`` / ``aarch64`` per ``platform.machine()``
    (lowercased)."""


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

_OS_MAP = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}


def _check_docker_daemon() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        completed = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return completed.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _check_gpu_count() -> int:
    """Probe nvidia-smi for visible GPU count. Returns 0 on absence
    or any error — a missing tool is the same as "no GPU" for
    predicate purposes."""
    if not shutil.which("nvidia-smi"):
        return 0
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--list-gpus"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            return 0
        # One line per GPU.
        return sum(1 for line in completed.stdout.splitlines() if line.strip())
    except (subprocess.SubprocessError, OSError):
        return 0


def detect_host_info(*, probe_binaries: Optional[List[str]] = None) -> HostInfo:
    """Build a HostInfo describing the running machine.

    ``probe_binaries`` is an optional list of binary names to look
    up on PATH. Pass the union of every ``binary:`` predicate across
    the manifest's install entries — we don't enumerate all of PATH
    because that's slow and pointless.
    """
    found_binaries: List[str] = []
    for name in probe_binaries or []:
        if shutil.which(name):
            found_binaries.append(name)

    return HostInfo(
        docker_daemon=_check_docker_daemon(),
        binaries_on_path=found_binaries,
        python_version=".".join(map(str, sys.version_info[:3])),
        gpu_count=_check_gpu_count(),
        os=_OS_MAP.get(platform.system(), platform.system().lower()),
        arch=platform.machine().lower(),
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_predicates(
    predicates: List[Dict[str, Any]], host: HostInfo,
) -> List[str]:
    """Return descriptions of failed predicates. Empty = all passed.

    Each predicate is a single-key dict. Unknown predicate keys fail
    closed (refuse the install) — better to refuse a poorly-typed
    manifest than to silently bypass a check the author meant.
    """
    failed: List[str] = []
    for pred in predicates:
        if not isinstance(pred, dict) or len(pred) != 1:
            failed.append(f"malformed predicate {pred!r}")
            continue
        key, value = next(iter(pred.items()))
        ok, reason = _check_predicate(key, value, host)
        if not ok:
            failed.append(reason or f"{key}={value!r}")
    return failed


def collect_required_binaries(predicates_lists: List[List[Dict[str, Any]]]) -> List[str]:
    """Walk every install entry's ``requires:`` and collect the
    distinct ``binary:`` names. Used to bound :func:`detect_host_info`'s
    binary probe — we only check what the manifest cares about."""
    out: set[str] = set()
    for predicates in predicates_lists:
        for pred in predicates:
            if isinstance(pred, dict) and len(pred) == 1:
                key, value = next(iter(pred.items()))
                if key == "binary" and isinstance(value, str):
                    out.add(value)
    return sorted(out)


def _check_predicate(
    key: str, value: Any, host: HostInfo,
) -> tuple[bool, Optional[str]]:
    if key == "docker_daemon":
        expected = bool(value)
        actual = host.docker_daemon
        if actual == expected:
            return True, None
        return False, f"docker_daemon: want {expected}, got {actual}"

    if key == "binary":
        if value in host.binaries_on_path:
            return True, None
        return False, f"binary {value!r} not on PATH"

    if key == "python":
        if not isinstance(value, str):
            return False, f"python predicate must be a SemVer range string, got {value!r}"
        try:
            check_sdk_compat(value, host.python_version)
            return True, None
        except SdkCompatError as exc:
            return False, f"python {host.python_version}: {exc}"

    if key == "gpu_count_min":
        try:
            required = int(value)
        except (TypeError, ValueError):
            return False, f"gpu_count_min must be int, got {value!r}"
        if host.gpu_count >= required:
            return True, None
        return False, f"gpu_count_min: want ≥{required}, got {host.gpu_count}"

    if key == "os":
        if host.os == value:
            return True, None
        return False, f"os: want {value!r}, got {host.os!r}"

    if key == "arch":
        if host.arch == value:
            return True, None
        return False, f"arch: want {value!r}, got {host.arch!r}"

    # Unknown predicate. Fail closed — a typo'd predicate name should
    # not silently let an install through.
    return False, f"unknown predicate {key!r}"
