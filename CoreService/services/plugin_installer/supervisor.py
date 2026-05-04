"""Plugin process supervision (PI-2).

The install pipeline lays out a per-plugin uv venv under
``<plugins_dir>/<plugin_id>/``; this module is what actually keeps
the plugin process alive after install finishes.

Two impls today:

  * :class:`SystemdUserSupervisor` — writes
    ``~/.config/systemd/user/magellon-plugin-<id>.service`` and uses
    ``systemctl --user`` to enable/start/stop/disable. Per-user units
    don't need root; the plugin survives independently of the
    CoreService process; systemd's restart policy handles crashes.
    The production target on Linux deployments.

  * :class:`NoOpSupervisor` — logs the lifecycle calls but does
    nothing. The dev fallback for non-Linux hosts (Windows / macOS
    where systemd doesn't exist), and the test default so unit
    tests don't shell out.

A future :class:`SystemSupervisor` (system-wide unit, root-owned)
or a Windows service variant can plug into the same Protocol.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


SubprocessRunner = Callable[..., subprocess.CompletedProcess]


def _default_subprocess_runner(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(*args, **kwargs)


@dataclass(frozen=True)
class SupervisorResult:
    """Outcome of one supervisor operation.

    ``intent_only`` (R1 C, 2026-05-04): True when the supervisor
    recorded the intent without actually doing the work — the
    NoOpSupervisor returns this so callers don't conflate "install
    succeeded" with "plugin is running." The install pipeline can
    surface a hint in the response ("manual launch required on
    Windows / macOS dev").
    """

    success: bool
    plugin_id: str
    error: Optional[str] = None
    logs: Optional[str] = None
    intent_only: bool = False


@runtime_checkable
class Supervisor(Protocol):
    """Process-lifecycle controller for an installed plugin.

    The install pipeline calls ``install_unit`` + ``start`` after a
    successful ``Installer.install``; ``stop`` + ``remove_unit``
    before ``Installer.uninstall`` reclaims the install directory.
    """

    name: str

    def install_unit(self, plugin_id: str, install_dir: Path) -> SupervisorResult: ...
    def remove_unit(self, plugin_id: str) -> SupervisorResult: ...
    def start(self, plugin_id: str) -> SupervisorResult: ...
    def stop(self, plugin_id: str) -> SupervisorResult: ...


# ---------------------------------------------------------------------------
# NoOp — dev / Windows / test default
# ---------------------------------------------------------------------------


class NoOpSupervisor:
    """Records intent without acting on it. Use on hosts where
    systemd doesn't exist (Windows / macOS dev) or in tests where
    actual process supervision is out of scope."""

    name = "noop"

    def install_unit(self, plugin_id: str, install_dir: Path) -> SupervisorResult:
        logger.info("noop supervisor: install_unit(%s, %s) — no-op", plugin_id, install_dir)
        return SupervisorResult(
            success=True, plugin_id=plugin_id, intent_only=True,
            logs="noop: no unit file written; manual launch required",
        )

    def remove_unit(self, plugin_id: str) -> SupervisorResult:
        logger.info("noop supervisor: remove_unit(%s) — no-op", plugin_id)
        return SupervisorResult(
            success=True, plugin_id=plugin_id, intent_only=True,
        )

    def start(self, plugin_id: str) -> SupervisorResult:
        logger.info("noop supervisor: start(%s) — no-op", plugin_id)
        return SupervisorResult(
            success=True, plugin_id=plugin_id, intent_only=True,
            logs=(
                "noop: plugin process not started. Launch manually "
                f"(e.g. ``python <plugins_dir>/{plugin_id}/main.py``) "
                "or deploy on Linux with systemd."
            ),
        )

    def stop(self, plugin_id: str) -> SupervisorResult:
        logger.info("noop supervisor: stop(%s) — no-op", plugin_id)
        return SupervisorResult(
            success=True, plugin_id=plugin_id, intent_only=True,
        )


# ---------------------------------------------------------------------------
# systemd --user
# ---------------------------------------------------------------------------


_UNIT_TEMPLATE = """\
[Unit]
Description=Magellon plugin: {plugin_id}
After=network-online.target

[Service]
Type=simple
WorkingDirectory={install_dir}
EnvironmentFile={install_dir}/runtime.env
ExecStart={venv_python} {install_dir}/main.py
Restart=on-failure
RestartSec=5

# Reasonable resource hygiene — operator can override per-plugin by
# editing the unit before reload, or by drop-in.
LimitNOFILE=65536

[Install]
WantedBy=default.target
"""


def _unit_name(plugin_id: str) -> str:
    """Map plugin_id → systemd unit filename. Sanitized: systemd unit
    names allow [A-Za-z0-9:-_.\\] only; plugin_id is already a
    manifest-validated slug, but escape just in case."""
    safe = plugin_id.replace("/", "-").replace(" ", "_")
    return f"magellon-plugin-{safe}.service"


class SystemdUserSupervisor:
    """Per-user systemd supervisor. Production target on Linux.

    Layout: writes the unit file under
    ``$XDG_CONFIG_HOME/systemd/user/`` (defaulting to
    ``~/.config/systemd/user/``) and uses ``systemctl --user`` to
    drive enable/start/stop/disable transitions.

    Subprocess runner is injectable so tests don't shell out.

    Reviewer K: ``systemctl --user`` requires either an active login
    session OR ``loginctl enable-linger <user>``. Containerized
    CoreService running as a non-interactive service account has
    neither — operations fail with "Failed to connect to bus" and
    the operator's left guessing. :meth:`check_preconditions`
    surfaces the misconfig with an actionable error.
    """

    name = "systemd-user"

    def __init__(
        self,
        *,
        units_dir: Optional[Path] = None,
        systemctl: str = "systemctl",
        loginctl: str = "loginctl",
        subprocess_runner: SubprocessRunner = _default_subprocess_runner,
    ) -> None:
        if units_dir is None:
            xdg = os.environ.get("XDG_CONFIG_HOME")
            home_config = Path(xdg) if xdg else (Path.home() / ".config")
            units_dir = home_config / "systemd" / "user"
        self.units_dir = Path(units_dir)
        self.systemctl = systemctl
        self.loginctl = loginctl
        self._run = subprocess_runner

    # ------------------------------------------------------------------
    # Reviewer K: linger precondition probe
    # ------------------------------------------------------------------

    def check_preconditions(self) -> SupervisorResult:
        """Verify ``systemctl --user`` is reachable for the current user.

        Returns ``success=False`` with an actionable error when the
        user has no active session and linger is disabled — the
        configuration that would later cause every install to fail
        with an opaque "Failed to connect to bus" message. Callers
        (the install pipeline factory) call this once at startup.
        """
        # ``systemctl --user is-system-running`` is the standard probe;
        # it returns 0 with ``running``/``degraded`` stdout when the
        # user manager is alive, non-0 otherwise.
        probe = self._systemctl("is-system-running")
        if probe.success:
            return SupervisorResult(
                success=True, plugin_id="",
                logs=f"systemctl --user reachable: {probe.logs}",
            )

        # Probe failed. Distinguish "user manager not running" from
        # "user lacks linger" — both surface the same downstream
        # symptom but the fix differs.
        username = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        linger = self._linger_status(username)
        if linger is False:
            return SupervisorResult(
                success=False, plugin_id="",
                error=(
                    "systemctl --user is unreachable AND user "
                    f"{username!r} has linger disabled. Run "
                    f"`sudo loginctl enable-linger {username}` so the "
                    "user manager survives without an active session — "
                    "required for non-interactive deploys "
                    "(containerized CoreService, systemd service "
                    "running as a service account)."
                ),
            )
        return SupervisorResult(
            success=False, plugin_id="",
            error=(
                "systemctl --user is unreachable. Verify the user "
                f"manager is running (loginctl show-user {username!r}) "
                "and the deployment has either an active login session "
                "or linger enabled."
            ),
        )

    def _linger_status(self, username: str) -> Optional[bool]:
        """Return True/False if linger state is determinable, None on
        loginctl failure."""
        if not username:
            return None
        cmd = [self.loginctl, "show-user", username, "--property=Linger"]
        try:
            result = self._run(cmd, capture_output=True, text=True)
        except Exception:  # noqa: BLE001
            return None
        if result.returncode != 0:
            return None
        # stdout is "Linger=yes\n" or "Linger=no\n".
        for line in (result.stdout or "").splitlines():
            if line.startswith("Linger="):
                return line.split("=", 1)[1].strip().lower() == "yes"
        return None

    def _unit_path(self, plugin_id: str) -> Path:
        return self.units_dir / _unit_name(plugin_id)

    def _venv_python(self, install_dir: Path) -> Path:
        # systemd-managed plugins are Linux-only, so the bin/ layout
        # is fixed (no Scripts\\python.exe fallback needed).
        return install_dir / ".venv" / "bin" / "python"

    def _systemctl(self, *args: str) -> SupervisorResult:
        cmd = [self.systemctl, "--user", *args]
        result = self._run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return SupervisorResult(
                success=True,
                plugin_id="",
                logs=(result.stdout or "").rstrip(),
            )
        return SupervisorResult(
            success=False,
            plugin_id="",
            error=(result.stderr or result.stdout or "").rstrip()
                  or f"{' '.join(cmd)} returned {result.returncode}",
            logs=(result.stdout or "").rstrip(),
        )

    def install_unit(self, plugin_id: str, install_dir: Path) -> SupervisorResult:
        """Write the .service file and reload the user daemon.

        Paths in the unit file are emitted POSIX-style — systemd is
        Linux-only, so a Windows dev that wants to inspect the
        generated unit (or Linux deployment that built it on a
        Windows packager) sees portable paths.
        """
        try:
            self.units_dir.mkdir(parents=True, exist_ok=True)
            unit_path = self._unit_path(plugin_id)
            install_dir = Path(install_dir)
            unit_path.write_text(
                _UNIT_TEMPLATE.format(
                    plugin_id=plugin_id,
                    install_dir=install_dir.as_posix(),
                    venv_python=self._venv_python(install_dir).as_posix(),
                ),
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            return SupervisorResult(
                success=False,
                plugin_id=plugin_id,
                error=f"failed to write unit file: {exc}",
            )
        # Reload so systemd notices the new file.
        reload = self._systemctl("daemon-reload")
        if not reload.success:
            return SupervisorResult(
                success=False,
                plugin_id=plugin_id,
                error=f"daemon-reload failed: {reload.error}",
            )
        # enable: start on next login + create the wants/ symlink.
        enable = self._systemctl("enable", _unit_name(plugin_id))
        if not enable.success:
            return SupervisorResult(
                success=False,
                plugin_id=plugin_id,
                error=f"enable failed: {enable.error}",
            )
        return SupervisorResult(
            success=True,
            plugin_id=plugin_id,
            logs=f"wrote {unit_path}; daemon-reload + enable ok",
        )

    def remove_unit(self, plugin_id: str) -> SupervisorResult:
        """Disable + delete the unit file. Idempotent — missing unit is
        not an error since uninstall() may run after a partial install."""
        unit = _unit_name(plugin_id)
        # disable first (best-effort — fails-quiet if already disabled).
        self._systemctl("disable", unit)
        unit_path = self._unit_path(plugin_id)
        try:
            if unit_path.exists():
                unit_path.unlink()
        except Exception as exc:  # noqa: BLE001
            return SupervisorResult(
                success=False,
                plugin_id=plugin_id,
                error=f"failed to delete unit file: {exc}",
            )
        self._systemctl("daemon-reload")
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def start(self, plugin_id: str) -> SupervisorResult:
        result = self._systemctl("start", _unit_name(plugin_id))
        return SupervisorResult(
            success=result.success,
            plugin_id=plugin_id,
            error=result.error,
            logs=result.logs,
        )

    def stop(self, plugin_id: str) -> SupervisorResult:
        result = self._systemctl("stop", _unit_name(plugin_id))
        return SupervisorResult(
            success=result.success,
            plugin_id=plugin_id,
            error=result.error,
            logs=result.logs,
        )


# ---------------------------------------------------------------------------
# Windows / cross-platform Popen supervisor
# ---------------------------------------------------------------------------
#
# Manages the plugin process directly via ``subprocess.Popen`` and
# persists the PID under ``<install_dir>/.pid``. Used on Windows
# (where systemd doesn't exist) and as a portable fallback on macOS.
# Linux production deployments still prefer ``SystemdUserSupervisor``
# because user units survive ssh-disconnect / reboot via lingering;
# Popen plugins die with the parent CoreService.


def _read_runtime_env(install_dir: Path) -> Dict[str, str]:
    """Parse the plugin's ``runtime.env`` (KEY=VALUE per line) so the
    spawned process inherits the install-time deployment values."""
    env: Dict[str, str] = {}
    runtime_env = install_dir / "runtime.env"
    if not runtime_env.is_file():
        return env
    for line in runtime_env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


class PopenSupervisor:
    """Direct ``subprocess.Popen`` supervisor — Windows-friendly.

    Launches the plugin's ``main.py`` via ``uvicorn`` inside the
    plugin's own ``.venv``. Stdout/stderr are appended to
    ``<install_dir>/app.log`` so operators have something to inspect.

    Liveness model: the PID is persisted to
    ``<install_dir>/.pid`` at start and removed on stop. Liveness
    check uses ``psutil.pid_exists`` plus a name verification (the
    PID could have been recycled by an unrelated process after a
    crash).
    """

    name = "popen"

    def __init__(
        self,
        *,
        plugins_dir: Path,
        subprocess_runner: SubprocessRunner = _default_subprocess_runner,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self._run = subprocess_runner

    def _install_dir(self, plugin_id: str) -> Path:
        return self.plugins_dir / plugin_id

    def _pid_file(self, plugin_id: str) -> Path:
        return self._install_dir(plugin_id) / ".pid"

    def _venv_python(self, install_dir: Path) -> Path:
        # Windows + uv venv layout. ``Scripts/`` on Windows,
        # ``bin/`` on POSIX.
        win = install_dir / ".venv" / "Scripts" / "python.exe"
        if win.exists():
            return win
        return install_dir / ".venv" / "bin" / "python"

    def install_unit(self, plugin_id: str, install_dir: Path) -> SupervisorResult:
        # Popen has no install step — start() is direct. Always succeeds.
        return SupervisorResult(success=True, plugin_id=plugin_id, logs="popen: no unit needed")

    def remove_unit(self, plugin_id: str) -> SupervisorResult:
        pid_file = self._pid_file(plugin_id)
        try:
            if pid_file.exists():
                pid_file.unlink()
        except Exception as exc:  # noqa: BLE001
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"failed to remove pid file: {exc}",
            )
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def is_running(self, plugin_id: str) -> bool:
        pid = self._read_live_pid(plugin_id)
        return pid is not None

    def _read_live_pid(self, plugin_id: str) -> Optional[int]:
        """Return the persisted PID iff the process is still alive.
        Stale PID files (process gone) are cleaned up as a side effect."""
        pid_file = self._pid_file(plugin_id)
        if not pid_file.exists():
            return None
        try:
            pid = int(pid_file.read_text(encoding="utf-8").strip())
        except Exception:  # noqa: BLE001
            pid_file.unlink(missing_ok=True)
            return None
        if not _pid_alive(pid):
            pid_file.unlink(missing_ok=True)
            return None
        return pid

    def start(self, plugin_id: str) -> SupervisorResult:
        existing = self._read_live_pid(plugin_id)
        if existing is not None:
            return SupervisorResult(
                success=True, plugin_id=plugin_id,
                logs=f"already running (PID {existing})",
            )

        install_dir = self._install_dir(plugin_id)
        if not install_dir.is_dir():
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"plugin not installed at {install_dir}",
            )

        venv_python = self._venv_python(install_dir)
        if not venv_python.exists():
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"venv python missing: {venv_python}",
            )

        env = {**os.environ, **_read_runtime_env(install_dir)}
        port = env.get("MAGELLON_PLUGIN_PORT", "8000")
        host = env.get("MAGELLON_PLUGIN_HOST", "0.0.0.0")

        log_path = install_dir / "app.log"
        try:
            log_fh = open(log_path, "ab")
        except Exception as exc:  # noqa: BLE001
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"cannot open log {log_path}: {exc}",
            )

        cmd = [
            str(venv_python), "-m", "uvicorn", "main:app",
            "--host", host, "--port", str(port),
        ]
        # Detach from CoreService's process group so an operator
        # restarting CoreService doesn't take the plugin down with it.
        # Windows: CREATE_NEW_PROCESS_GROUP. POSIX: start_new_session.
        popen_kwargs: Dict[str, Any] = dict(
            cwd=str(install_dir),
            env=env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
        except Exception as exc:  # noqa: BLE001
            log_fh.close()
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"Popen failed: {exc}",
            )

        # We persist the PID immediately and let the file handle
        # detach when our reference drops; uvicorn will keep writing
        # to the OS-level fd. Closing too eagerly truncates output.
        try:
            self._pid_file(plugin_id).write_text(
                str(proc.pid), encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"started PID {proc.pid} but failed to persist: {exc}",
            )

        return SupervisorResult(
            success=True, plugin_id=plugin_id,
            logs=f"started PID {proc.pid} on {host}:{port} (logs -> {log_path.name})",
        )

    def stop(self, plugin_id: str) -> SupervisorResult:
        pid = self._read_live_pid(plugin_id)
        if pid is None:
            # Idempotent: stopping a stopped plugin is success.
            return SupervisorResult(
                success=True, plugin_id=plugin_id, logs="not running",
            )

        try:
            _terminate_pid(pid)
        except Exception as exc:  # noqa: BLE001
            return SupervisorResult(
                success=False, plugin_id=plugin_id,
                error=f"terminate failed for PID {pid}: {exc}",
            )

        # Wait briefly for graceful shutdown; force-kill if it lingers.
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.2)
        if _pid_alive(pid):
            try:
                _kill_pid(pid)
            except Exception:  # noqa: BLE001
                pass

        self._pid_file(plugin_id).unlink(missing_ok=True)
        return SupervisorResult(
            success=True, plugin_id=plugin_id, logs=f"stopped PID {pid}",
        )


def _pid_alive(pid: int) -> bool:
    """Cross-platform 'is this PID a live process?' check."""
    try:
        import psutil
        if not psutil.pid_exists(pid):
            return False
        # Defensive: zombie check
        proc = psutil.Process(pid)
        return proc.status() != psutil.STATUS_ZOMBIE
    except Exception:  # noqa: BLE001
        # Without psutil, fall back to os.kill(pid, 0).
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _terminate_pid(pid: int) -> None:
    """Send SIGTERM on POSIX; on Windows, taskkill without /F first."""
    if platform.system() == "Windows":
        # /T = also terminate child processes (uvicorn workers).
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            capture_output=True, timeout=5,
        )
    else:
        import signal
        os.kill(pid, signal.SIGTERM)


def _kill_pid(pid: int) -> None:
    """Force-kill — Windows /F or SIGKILL."""
    if platform.system() == "Windows":
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid), "/T"],
            capture_output=True, timeout=5,
        )
    else:
        import signal
        os.kill(pid, signal.SIGKILL)


# ---------------------------------------------------------------------------
# Factory — picks the right impl per host
# ---------------------------------------------------------------------------


def default_supervisor(plugins_dir: Optional[Path] = None) -> Supervisor:
    """Return a supervisor appropriate for the current host.

    - Linux with systemctl on PATH → :class:`SystemdUserSupervisor`
    - Other (Windows / macOS) when ``plugins_dir`` is provided → :class:`PopenSupervisor`
    - Fallback → :class:`NoOpSupervisor`
    """
    if platform.system() == "Linux" and shutil.which("systemctl"):
        return SystemdUserSupervisor()
    if plugins_dir is not None:
        return PopenSupervisor(plugins_dir=plugins_dir)
    return NoOpSupervisor()


__all__ = [
    "NoOpSupervisor",
    "PopenSupervisor",
    "Supervisor",
    "SupervisorResult",
    "SystemdUserSupervisor",
    "default_supervisor",
]
