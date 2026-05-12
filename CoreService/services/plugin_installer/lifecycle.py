"""``BackendLifecycle`` — symmetric start/stop/restart/status across install methods.

The existing :class:`Supervisor` Protocol is uv-focused: ``install_unit``
+ ``remove_unit`` are systemd-shaped, and the install pipeline calls
them on install/uninstall. After install, ``start``/``stop`` route
through whichever supervisor the host picked (systemd / Popen / noop).

That worked when uv was the only path that needed lifecycle control.
With docker installs, the install pipeline starts the container during
``DockerInstaller.install`` and stops it during ``DockerInstaller.uninstall``,
but operators couldn't ``stop`` / ``start`` / ``restart`` a running
container after install. This module closes that gap: one Protocol,
one impl per install method, ``PluginInstallManager`` routes through
the method-indexed registry.

The Protocol also reserves the ``pause`` / ``unpause`` verbs used by
:doc:`Phase 2 <pause>` — :class:`DockerLifecycle` will implement them
via ``docker pause`` (cgroups freezer / SIGSTOP). The uv impl raises
``NotSupportedError`` for those — psutil-suspend is OS-fragile and
out of scope until operators ask for it.
"""
from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

from services.plugin_installer.supervisor import Supervisor, SupervisorResult

logger = logging.getLogger(__name__)


SubprocessRunner = Callable[..., subprocess.CompletedProcess]


def _default_subprocess_runner(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(*args, **kwargs)


class LifecycleStatus(str, Enum):
    """Coarse state. ``UNKNOWN`` covers 'lifecycle can't tell' (e.g. the
    NoOp uv supervisor on Windows dev, where supervision isn't really
    happening). Operators get a chip in the UI; treat ``UNKNOWN`` as
    a hint to look at the bus heartbeat instead."""

    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LifecycleResult:
    """Outcome of one lifecycle operation. Mirrors
    :class:`SupervisorResult` so existing callers can map without
    behaviour change."""

    success: bool
    plugin_id: str
    status: LifecycleStatus = LifecycleStatus.UNKNOWN
    error: Optional[str] = None
    logs: Optional[str] = None


class NotSupportedError(RuntimeError):
    """Raised when a lifecycle verb (e.g. pause on uv) isn't supported
    by this backend. Controller maps to HTTP 409 with an actionable
    message ('pause is docker-only — use stop instead')."""


@runtime_checkable
class BackendLifecycle(Protocol):
    """One install method's lifecycle controller.

    ``method`` matches :attr:`Installer.method` (``"uv"`` / ``"docker"``)
    so ``PluginInstallManager`` can route by string.

    ``supports_pause`` is a class-level capability flag. Docker
    implements pause via ``docker pause`` (cgroups freezer, SIGSTOP);
    uv does not — psutil-based suspend is OS-fragile and out of scope
    until operators ask for it. UI greys out the Pause button when
    this is False.
    """

    method: str
    supports_pause: bool

    def start(self, plugin_id: str) -> LifecycleResult: ...
    def stop(self, plugin_id: str) -> LifecycleResult: ...
    def restart(self, plugin_id: str) -> LifecycleResult: ...
    def pause(self, plugin_id: str) -> LifecycleResult: ...
    def unpause(self, plugin_id: str) -> LifecycleResult: ...
    def status(self, plugin_id: str) -> LifecycleStatus: ...
    def logs(self, plugin_id: str, *, tail: int = 200) -> str:
        """Return the last ``tail`` lines from the plugin's log source.

        Uv plugins read from the supervisor's stdout capture
        (``app.log`` for Popen; ``journalctl`` for systemd-user).
        Docker plugins shell ``docker logs --tail``. Empty string if
        no log source is available.
        """
        ...


# ---------------------------------------------------------------------------
# Uv — wraps the existing Supervisor (systemd / Popen / NoOp)
# ---------------------------------------------------------------------------


class UvLifecycle:
    """Adapter from :class:`BackendLifecycle` onto the existing
    :class:`Supervisor`. No behaviour change vs pre-Phase-1 — uv
    plugins continue to flow through systemd-user (Linux) or Popen
    (Windows/macOS dev) or NoOp (test/CI without supervision).

    ``pause`` raises :class:`NotSupportedError`. The portable way to
    suspend a uv process (``psutil.Process.suspend``) varies in
    behaviour across Linux/macOS/Windows and child-process trees;
    until operators have a use case, declare it unsupported and let
    callers stop+start.
    """

    method = "uv"
    supports_pause = False

    def __init__(self, supervisor: Supervisor) -> None:
        self._supervisor = supervisor

    def start(self, plugin_id: str) -> LifecycleResult:
        return _from_supervisor(self._supervisor.start(plugin_id), LifecycleStatus.RUNNING)

    def stop(self, plugin_id: str) -> LifecycleResult:
        return _from_supervisor(self._supervisor.stop(plugin_id), LifecycleStatus.STOPPED)

    def restart(self, plugin_id: str) -> LifecycleResult:
        # Match the manager's pre-Phase-1 contract: stop errors are
        # swallowed (a stop failure usually means 'already stopped'),
        # the start result is what surfaces.
        self._supervisor.stop(plugin_id)
        return self.start(plugin_id)

    def pause(self, plugin_id: str) -> LifecycleResult:
        raise NotSupportedError(
            "pause is docker-only — uv plugins should be stopped instead",
        )

    def unpause(self, plugin_id: str) -> LifecycleResult:
        raise NotSupportedError(
            "unpause is docker-only — uv plugins should be started instead",
        )

    def status(self, plugin_id: str) -> LifecycleStatus:
        # Best-effort: the Popen/systemd supervisors expose
        # is_running; NoOp does not. Treat absence as UNKNOWN rather
        # than STOPPED so the UI shows the right chip.
        is_running = getattr(self._supervisor, "is_running", None)
        if is_running is None:
            return LifecycleStatus.UNKNOWN
        try:
            return LifecycleStatus.RUNNING if is_running(plugin_id) else LifecycleStatus.STOPPED
        except Exception:  # noqa: BLE001
            return LifecycleStatus.UNKNOWN

    def logs(self, plugin_id: str, *, tail: int = 200) -> str:
        # NoOpSupervisor and any future supervisor that doesn't
        # implement logs returns empty rather than raising.
        fn = getattr(self._supervisor, "logs", None)
        if fn is None:
            return ""
        try:
            return fn(plugin_id, tail=tail)
        except Exception as exc:  # noqa: BLE001
            return f"<supervisor.logs raised: {exc}>"


def _from_supervisor(
    result: SupervisorResult, on_success: LifecycleStatus,
) -> LifecycleResult:
    return LifecycleResult(
        success=result.success,
        plugin_id=result.plugin_id,
        status=on_success if result.success else LifecycleStatus.UNKNOWN,
        error=result.error,
        logs=result.logs,
    )


# ---------------------------------------------------------------------------
# Docker — start/stop/restart against the install-time container
# ---------------------------------------------------------------------------


_STATE_FILENAME = "install_state.json"


class DockerLifecycle:
    """``BackendLifecycle`` over the docker CLI.

    ``DockerInstaller.install`` runs the container; this class manages
    it after. Container name comes from ``install_state.json`` written
    by the installer.

    Pause is implemented via ``docker pause`` (Linux: cgroups freezer;
    other platforms: SIGSTOP). Cheap and reliable — the container's
    memory stays resident so unpause resumes in-flight work
    instantaneously. Use for short maintenance windows (operator wants
    to free GPU briefly); stop is still the right call for longer
    holds where you don't want resident memory pinned.
    """

    method = "docker"
    supports_pause = True

    def __init__(
        self,
        plugins_dir: Path,
        *,
        docker_command: str = "docker",
        subprocess_runner: SubprocessRunner = _default_subprocess_runner,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.docker_command = docker_command
        self._run = subprocess_runner

    def start(self, plugin_id: str) -> LifecycleResult:
        return self._do(plugin_id, "start", LifecycleStatus.RUNNING)

    def stop(self, plugin_id: str) -> LifecycleResult:
        return self._do(plugin_id, "stop", LifecycleStatus.STOPPED)

    def restart(self, plugin_id: str) -> LifecycleResult:
        return self._do(plugin_id, "restart", LifecycleStatus.RUNNING)

    def pause(self, plugin_id: str) -> LifecycleResult:
        return self._do(plugin_id, "pause", LifecycleStatus.PAUSED)

    def unpause(self, plugin_id: str) -> LifecycleResult:
        return self._do(plugin_id, "unpause", LifecycleStatus.RUNNING)

    def status(self, plugin_id: str) -> LifecycleStatus:
        container_name = self._container_name(plugin_id)
        if container_name is None:
            return LifecycleStatus.UNKNOWN
        # ``docker inspect -f '{{.State.Status}}'`` prints one of:
        # created | running | paused | restarting | removing | exited | dead
        result = self._run(
            [self.docker_command, "inspect", "-f", "{{.State.Status}}", container_name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return LifecycleStatus.UNKNOWN
        state = (result.stdout or "").strip().lower()
        if state == "running":
            return LifecycleStatus.RUNNING
        if state == "paused":
            return LifecycleStatus.PAUSED
        if state in ("exited", "created", "dead"):
            return LifecycleStatus.STOPPED
        return LifecycleStatus.UNKNOWN

    def logs(self, plugin_id: str, *, tail: int = 200) -> str:
        """``docker logs --tail N <container>`` — combined stdout+stderr.

        Returns an empty string when the container has no recorded
        state (never installed) or docker errors. The follow=True
        path is handled by the Socket.IO streamer in
        :mod:`core.plugin_log_stream` rather than here.
        """
        container_name = self._container_name(plugin_id)
        if container_name is None:
            return ""
        result = self._run(
            [
                self.docker_command, "logs",
                "--tail", str(max(1, tail)), container_name,
            ],
            capture_output=True, text=True,
        )
        # ``docker logs`` writes the container's stdout to OUR stdout
        # and its stderr to OUR stderr. Merge them so the operator
        # sees the interleaving (the container's own stream order is
        # already lost, but at least nothing's hidden).
        out = (result.stdout or "") + (result.stderr or "")
        return out.rstrip()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _do(
        self, plugin_id: str, verb: str, on_success: LifecycleStatus,
    ) -> LifecycleResult:
        container_name = self._container_name(plugin_id)
        if container_name is None:
            return LifecycleResult(
                success=False, plugin_id=plugin_id,
                status=LifecycleStatus.UNKNOWN,
                error=f"plugin {plugin_id!r}: install_state.json missing — "
                      f"can't resolve container name",
            )
        result = self._run(
            [self.docker_command, verb, container_name],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return LifecycleResult(
                success=False, plugin_id=plugin_id,
                status=self.status(plugin_id),
                error=f"docker {verb} {container_name} failed: "
                      f"{(result.stderr or result.stdout or '').strip()}",
                logs=result.stdout,
            )
        return LifecycleResult(
            success=True, plugin_id=plugin_id,
            status=on_success, logs=result.stdout,
        )

    def _container_name(self, plugin_id: str) -> Optional[str]:
        state_path = self.plugins_dir / plugin_id / _STATE_FILENAME
        if not state_path.is_file():
            return None
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            return state.get("container_name")
        except (OSError, ValueError) as exc:
            logger.warning(
                "docker lifecycle: failed to read %s: %s", state_path, exc,
            )
            return None


__all__ = [
    "BackendLifecycle",
    "DockerLifecycle",
    "LifecycleResult",
    "LifecycleStatus",
    "NotSupportedError",
    "UvLifecycle",
]
