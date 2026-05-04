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
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


SubprocessRunner = Callable[..., subprocess.CompletedProcess]


def _default_subprocess_runner(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(*args, **kwargs)


@dataclass(frozen=True)
class SupervisorResult:
    """Outcome of one supervisor operation."""

    success: bool
    plugin_id: str
    error: Optional[str] = None
    logs: Optional[str] = None


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
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def remove_unit(self, plugin_id: str) -> SupervisorResult:
        logger.info("noop supervisor: remove_unit(%s) — no-op", plugin_id)
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def start(self, plugin_id: str) -> SupervisorResult:
        logger.info("noop supervisor: start(%s) — no-op", plugin_id)
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def stop(self, plugin_id: str) -> SupervisorResult:
        logger.info("noop supervisor: stop(%s) — no-op", plugin_id)
        return SupervisorResult(success=True, plugin_id=plugin_id)


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
    """

    name = "systemd-user"

    def __init__(
        self,
        *,
        units_dir: Optional[Path] = None,
        systemctl: str = "systemctl",
        subprocess_runner: SubprocessRunner = _default_subprocess_runner,
    ) -> None:
        if units_dir is None:
            xdg = os.environ.get("XDG_CONFIG_HOME")
            home_config = Path(xdg) if xdg else (Path.home() / ".config")
            units_dir = home_config / "systemd" / "user"
        self.units_dir = Path(units_dir)
        self.systemctl = systemctl
        self._run = subprocess_runner

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
# Factory — picks the right impl per host
# ---------------------------------------------------------------------------


def default_supervisor() -> Supervisor:
    """Return a supervisor appropriate for the current host.

    Linux with systemctl on PATH → :class:`SystemdUserSupervisor`.
    Anything else → :class:`NoOpSupervisor` (dev fallback; install
    pipeline still works, the operator just runs the plugin manually).
    """
    if platform.system() == "Linux" and shutil.which("systemctl"):
        return SystemdUserSupervisor()
    return NoOpSupervisor()


__all__ = [
    "NoOpSupervisor",
    "Supervisor",
    "SupervisorResult",
    "SystemdUserSupervisor",
    "default_supervisor",
]
