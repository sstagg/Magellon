"""Tests for plugin process supervision (PI-2).

Subprocess is stubbed throughout — we don't actually shell out to
systemctl. The contract under test is "the right command lines reach
the runner, in the right order, and the unit file ends up where we
expect it."
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from services.plugin_installer.supervisor import (
    NoOpSupervisor,
    SupervisorResult,
    SystemdUserSupervisor,
    _unit_name,
    default_supervisor,
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _stub_runner(returncode: int = 0, stdout: str = "", stderr: str = ""):
    calls: list[list[str]] = []

    def _run(cmd, **_kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr=stderr,
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


# ---------------------------------------------------------------------------
# NoOpSupervisor
# ---------------------------------------------------------------------------


def test_noop_supervisor_returns_success_for_every_op():
    sup = NoOpSupervisor()
    assert sup.install_unit("ctf", Path("/x")).success
    assert sup.start("ctf").success
    assert sup.stop("ctf").success
    assert sup.remove_unit("ctf").success


# ---------------------------------------------------------------------------
# SystemdUserSupervisor
# ---------------------------------------------------------------------------


def test_systemd_install_unit_writes_file_and_calls_daemon_reload(tmp_path):
    runner = _stub_runner()
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)

    result = sup.install_unit("template-picker", Path("/opt/plugins/template-picker"))

    assert result.success, result.error
    unit = tmp_path / "magellon-plugin-template-picker.service"
    assert unit.is_file()
    body = unit.read_text(encoding="utf-8")
    assert "Description=Magellon plugin: template-picker" in body
    assert "WorkingDirectory=/opt/plugins/template-picker" in body
    assert "EnvironmentFile=/opt/plugins/template-picker/runtime.env" in body
    assert "ExecStart=/opt/plugins/template-picker/.venv/bin/python /opt/plugins/template-picker/main.py" in body
    assert "Restart=on-failure" in body

    # daemon-reload + enable must both have run.
    cmds = [" ".join(c) for c in runner.calls]
    assert any("daemon-reload" in c for c in cmds)
    assert any("enable magellon-plugin-template-picker.service" in c for c in cmds)


def test_systemd_install_unit_rolls_up_daemon_reload_failure(tmp_path):
    """If daemon-reload fails the unit was written but systemd doesn't
    know about it. Surface as failure so the manager rolls back."""
    runner = _stub_runner(returncode=1, stderr="dbus connection closed")
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)

    result = sup.install_unit("ctf", Path("/x"))

    assert not result.success
    assert "daemon-reload" in (result.error or "")


def test_systemd_remove_unit_disables_and_deletes_file(tmp_path):
    """Inverse of install_unit. Idempotent — missing file is not an
    error since uninstall() may run after a partial install."""
    runner = _stub_runner()
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    unit_path = tmp_path / "magellon-plugin-ctf.service"
    unit_path.write_text("placeholder", encoding="utf-8")

    result = sup.remove_unit("ctf")

    assert result.success
    assert not unit_path.exists()
    cmds = [" ".join(c) for c in runner.calls]
    assert any("disable magellon-plugin-ctf.service" in c for c in cmds)


def test_systemd_remove_unit_is_idempotent_when_file_missing(tmp_path):
    runner = _stub_runner()
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.remove_unit("never-installed")
    assert result.success


def test_systemd_start_invokes_systemctl_start(tmp_path):
    runner = _stub_runner()
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.start("ctf")
    assert result.success
    cmds = [" ".join(c) for c in runner.calls]
    assert any("start magellon-plugin-ctf.service" in c for c in cmds)


def test_systemd_stop_invokes_systemctl_stop(tmp_path):
    runner = _stub_runner()
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.stop("ctf")
    assert result.success
    cmds = [" ".join(c) for c in runner.calls]
    assert any("stop magellon-plugin-ctf.service" in c for c in cmds)


def test_systemd_start_surfaces_failure_text(tmp_path):
    """``systemctl start`` exit ≠ 0 → failure with stderr surfaced.
    Pinned because operators reading the install logs need the real
    error, not a generic 'start failed'."""
    runner = _stub_runner(
        returncode=5,
        stderr="Failed to start magellon-plugin-ctf.service: Unit file not found.",
    )
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.start("ctf")
    assert not result.success
    assert "Unit file not found" in (result.error or "")


# ---------------------------------------------------------------------------
# Unit name escaping
# ---------------------------------------------------------------------------


def test_unit_name_escapes_slashes_and_spaces():
    assert _unit_name("ctf") == "magellon-plugin-ctf.service"
    assert _unit_name("pp/template-picker") == "magellon-plugin-pp-template-picker.service"
    assert _unit_name("name with space") == "magellon-plugin-name_with_space.service"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_default_supervisor_returns_noop_off_linux(monkeypatch):
    """Anything not Linux → NoOp. Pinned so a Windows / macOS dev
    environment can still install plugins (without auto-start) and
    so unit tests outside Linux don't accidentally try to run
    systemctl."""
    monkeypatch.setattr("platform.system", lambda: "Windows")
    sup = default_supervisor()
    assert isinstance(sup, NoOpSupervisor)


def test_default_supervisor_returns_systemd_on_linux_with_systemctl(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/systemctl")
    sup = default_supervisor()
    assert isinstance(sup, SystemdUserSupervisor)


def test_default_supervisor_returns_noop_on_linux_without_systemctl(monkeypatch):
    """A minimal Linux container without systemd installed (CI runners,
    Alpine images) → NoOp rather than failing every install."""
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("shutil.which", lambda name: None)
    sup = default_supervisor()
    assert isinstance(sup, NoOpSupervisor)


# ---------------------------------------------------------------------------
# Reviewer K: linger precondition
# ---------------------------------------------------------------------------


def _stub_runner_with_responses(responses):
    """Subprocess runner that returns responses by command-prefix match."""
    calls: list[list[str]] = []

    def _run(cmd, **_kwargs):
        calls.append(list(cmd))
        for prefix, (rc, stdout, stderr) in responses.items():
            if all(p in cmd for p in prefix):
                return subprocess.CompletedProcess(
                    args=cmd, returncode=rc, stdout=stdout, stderr=stderr,
                )
        return subprocess.CompletedProcess(
            args=cmd, returncode=1, stdout="", stderr="no canned response",
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def test_check_preconditions_returns_success_when_systemctl_reachable(tmp_path):
    """Happy path: systemctl --user is-system-running returns 0."""
    runner = _stub_runner_with_responses({
        ("is-system-running",): (0, "running\n", ""),
    })
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.check_preconditions()
    assert result.success
    assert "running" in (result.logs or "")


def test_check_preconditions_flags_missing_linger_with_actionable_message(
    tmp_path, monkeypatch,
):
    """systemctl probe fails AND linger is disabled → return a
    success=False with the loginctl enable-linger fix in the
    error message. Pinned because operators reading the install
    log shouldn't have to grep for the right command."""
    monkeypatch.setenv("USER", "magellon")
    runner = _stub_runner_with_responses({
        ("is-system-running",): (1, "", "Failed to connect to bus"),
        ("show-user", "magellon"): (0, "Linger=no\n", ""),
    })
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.check_preconditions()
    assert not result.success
    assert "linger" in (result.error or "").lower()
    assert "enable-linger magellon" in (result.error or "")


def test_check_preconditions_flags_unreachable_systemctl_when_linger_unknown(
    tmp_path, monkeypatch,
):
    """systemctl unreachable + loginctl can't determine linger →
    actionable but generic error (don't recommend the wrong fix)."""
    monkeypatch.setenv("USER", "magellon")
    runner = _stub_runner_with_responses({
        ("is-system-running",): (1, "", "Failed to connect"),
        ("show-user", "magellon"): (1, "", "no such user"),
    })
    sup = SystemdUserSupervisor(units_dir=tmp_path, subprocess_runner=runner)
    result = sup.check_preconditions()
    assert not result.success
    assert "is unreachable" in (result.error or "")
