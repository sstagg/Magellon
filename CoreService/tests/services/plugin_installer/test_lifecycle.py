"""Tests for the BackendLifecycle Protocol + impls (Phase 1).

Two impls under test:
  - UvLifecycle wraps the existing Supervisor — behaviour-preserving.
  - DockerLifecycle shells to ``docker start/stop/restart/inspect`` with
    an injected subprocess runner so tests don't need a daemon.

The integration with PluginInstallManager (route by install method) is
covered by ``test_manager_lifecycle.py``.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Tuple

import pytest

from services.plugin_installer.lifecycle import (
    DockerLifecycle,
    LifecycleResult,
    LifecycleStatus,
    NotSupportedError,
    UvLifecycle,
)
from services.plugin_installer.supervisor import (
    NoOpSupervisor,
    SupervisorResult,
)


# ---------------------------------------------------------------------------
# UvLifecycle
# ---------------------------------------------------------------------------


class _RecordingSupervisor:
    name = "rec"

    def __init__(self, *, start_ok=True, stop_ok=True, running=True):
        self.calls: List[str] = []
        self._start_ok = start_ok
        self._stop_ok = stop_ok
        self._running = running

    def install_unit(self, plugin_id, install_dir):
        self.calls.append("install_unit")
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def remove_unit(self, plugin_id):
        self.calls.append("remove_unit")
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def start(self, plugin_id):
        self.calls.append("start")
        return SupervisorResult(
            success=self._start_ok, plugin_id=plugin_id,
            error=None if self._start_ok else "boom",
        )

    def stop(self, plugin_id):
        self.calls.append("stop")
        return SupervisorResult(
            success=self._stop_ok, plugin_id=plugin_id,
            error=None if self._stop_ok else "boom",
        )

    def is_running(self, plugin_id):
        return self._running


def test_uv_lifecycle_start_delegates_to_supervisor():
    sup = _RecordingSupervisor()
    lc = UvLifecycle(sup)

    result = lc.start("p1")

    assert isinstance(result, LifecycleResult)
    assert result.success
    assert result.status == LifecycleStatus.RUNNING
    assert sup.calls == ["start"]


def test_uv_lifecycle_stop_delegates_to_supervisor():
    sup = _RecordingSupervisor()
    lc = UvLifecycle(sup)

    result = lc.stop("p1")

    assert result.success
    assert result.status == LifecycleStatus.STOPPED
    assert sup.calls == ["stop"]


def test_uv_lifecycle_restart_does_stop_then_start():
    """Pre-Phase-1 contract preserved: stop runs unconditionally, then
    start. Stop failures are swallowed (a stop failure usually means
    'already stopped'); the start result is what surfaces."""
    sup = _RecordingSupervisor(stop_ok=False)
    lc = UvLifecycle(sup)

    result = lc.restart("p1")

    assert result.success  # start succeeded; stop failure swallowed
    assert sup.calls == ["stop", "start"]


def test_uv_lifecycle_start_failure_status_unknown():
    """When the supervisor fails to start, status must NOT claim
    RUNNING — operators need to know it isn't up."""
    sup = _RecordingSupervisor(start_ok=False)
    lc = UvLifecycle(sup)

    result = lc.start("p1")

    assert not result.success
    assert result.status == LifecycleStatus.UNKNOWN
    assert result.error == "boom"


def test_uv_lifecycle_status_reflects_is_running():
    lc = UvLifecycle(_RecordingSupervisor(running=True))
    assert lc.status("p1") == LifecycleStatus.RUNNING

    lc = UvLifecycle(_RecordingSupervisor(running=False))
    assert lc.status("p1") == LifecycleStatus.STOPPED


def test_uv_lifecycle_status_unknown_when_supervisor_has_no_is_running():
    """NoOpSupervisor doesn't expose is_running — fall back to UNKNOWN
    so the UI shows a 'state unknown' chip instead of claiming stopped."""
    lc = UvLifecycle(NoOpSupervisor())
    assert lc.status("p1") == LifecycleStatus.UNKNOWN


# ---------------------------------------------------------------------------
# DockerLifecycle
# ---------------------------------------------------------------------------


def _write_state(plugins_dir: Path, plugin_id: str, container_name: str) -> None:
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "install_state.json").write_text(
        json.dumps({
            "plugin_id": plugin_id,
            "version": "1.0.0",
            "method": "docker",
            "image_ref": "img:1",
            "image_was_built": False,
            "container_name": container_name,
        }),
        encoding="utf-8",
    )


class _RecordingDockerRunner:
    """Records every ``docker`` subprocess call so tests can assert
    the right verb + container name landed."""

    def __init__(self, *, returncode=0, stdout="", stderr=""):
        self.calls: List[Tuple[str, ...]] = []
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        # Optional per-cmd override: maps cmd[1] (verb) → (returncode, stdout)
        self.overrides: dict = {}

    def __call__(self, cmd, *args, **kwargs):
        self.calls.append(tuple(cmd))
        verb = cmd[1] if len(cmd) > 1 else ""
        if verb in self.overrides:
            rc, out = self.overrides[verb]
            return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr="")
        return subprocess.CompletedProcess(
            cmd, self.returncode, stdout=self._stdout, stderr=self._stderr,
        )


def test_docker_lifecycle_start_invokes_docker_start(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=0)
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.start("fft")

    assert result.success
    assert result.status == LifecycleStatus.RUNNING
    assert runner.calls == [("docker", "start", "magellon-plugin-fft")]


def test_docker_lifecycle_stop_invokes_docker_stop(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=0)
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.stop("fft")

    assert result.success
    assert result.status == LifecycleStatus.STOPPED
    assert runner.calls == [("docker", "stop", "magellon-plugin-fft")]


def test_docker_lifecycle_restart_uses_native_docker_restart(tmp_path):
    """docker has a native restart verb — use it instead of stop+start
    so the container's restart count metric is meaningful."""
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=0)
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.restart("fft")

    assert result.success
    assert runner.calls == [("docker", "restart", "magellon-plugin-fft")]


def test_docker_lifecycle_missing_state_returns_clean_error(tmp_path):
    """install_state.json is the source of truth for container_name;
    without it we can't act. Surface a clean error rather than guessing."""
    runner = _RecordingDockerRunner()
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.start("never-installed")

    assert not result.success
    assert "install_state.json missing" in (result.error or "")
    assert runner.calls == []  # no docker call attempted


def test_docker_lifecycle_failure_surfaces_stderr(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=1, stderr="container not found")
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.start("fft")

    assert not result.success
    assert "container not found" in (result.error or "")


def test_docker_lifecycle_status_parses_inspect_output(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    for state_str, expected in [
        ("running\n", LifecycleStatus.RUNNING),
        ("paused\n", LifecycleStatus.PAUSED),
        ("exited\n", LifecycleStatus.STOPPED),
        ("created\n", LifecycleStatus.STOPPED),
        ("dead\n", LifecycleStatus.STOPPED),
        ("restarting\n", LifecycleStatus.UNKNOWN),
    ]:
        runner = _RecordingDockerRunner(returncode=0, stdout=state_str)
        lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)
        assert lc.status("fft") == expected, f"state={state_str.strip()}"


def test_docker_lifecycle_status_unknown_on_inspect_failure(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=1, stderr="no such container")
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    assert lc.status("fft") == LifecycleStatus.UNKNOWN


def test_docker_lifecycle_status_unknown_when_state_missing(tmp_path):
    runner = _RecordingDockerRunner()
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    assert lc.status("never-installed") == LifecycleStatus.UNKNOWN
    assert runner.calls == []


# ---------------------------------------------------------------------------
# Pause (Phase 2) — docker only
# ---------------------------------------------------------------------------


def test_docker_lifecycle_pause_invokes_docker_pause(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=0)
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.pause("fft")

    assert result.success
    assert result.status == LifecycleStatus.PAUSED
    assert runner.calls == [("docker", "pause", "magellon-plugin-fft")]


def test_docker_lifecycle_unpause_invokes_docker_unpause(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=0)
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    result = lc.unpause("fft")

    assert result.success
    assert result.status == LifecycleStatus.RUNNING
    assert runner.calls == [("docker", "unpause", "magellon-plugin-fft")]


def test_docker_lifecycle_supports_pause():
    """Capability flag the UI reads to grey out the Pause button per
    install method."""
    assert DockerLifecycle.supports_pause is True
    assert UvLifecycle.supports_pause is False


def test_uv_lifecycle_pause_raises_not_supported():
    """uv plugins can't be paused — psutil-suspend is OS-fragile,
    out of scope until operators ask. Controller maps to HTTP 409."""
    lc = UvLifecycle(_RecordingSupervisor())

    with pytest.raises(NotSupportedError, match="docker-only"):
        lc.pause("p1")


def test_uv_lifecycle_unpause_raises_not_supported():
    lc = UvLifecycle(_RecordingSupervisor())

    with pytest.raises(NotSupportedError, match="docker-only"):
        lc.unpause("p1")


# ---------------------------------------------------------------------------
# logs() — Phase 6
# ---------------------------------------------------------------------------


class _SupervisorWithLogs(_RecordingSupervisor):
    def __init__(self, *, log_text="line1\nline2\nline3", raise_on_logs=False):
        super().__init__()
        self._log_text = log_text
        self._raise = raise_on_logs

    def logs(self, plugin_id, *, tail=200):
        if self._raise:
            raise RuntimeError("boom")
        return "\n".join(self._log_text.splitlines()[-tail:])


def test_uv_lifecycle_logs_delegates_to_supervisor():
    sup = _SupervisorWithLogs(log_text="one\ntwo\nthree\nfour")
    lc = UvLifecycle(sup)
    assert lc.logs("p1", tail=2) == "three\nfour"


def test_uv_lifecycle_logs_returns_empty_on_supervisor_without_logs():
    """NoOpSupervisor doesn't implement logs (or implements a no-op).
    The lifecycle returns empty rather than crashing."""
    lc = UvLifecycle(NoOpSupervisor())
    out = lc.logs("p1", tail=10)
    # NoOpSupervisor returns empty string; the wrapper passes it through.
    assert out == ""


def test_uv_lifecycle_logs_catches_supervisor_exceptions():
    """A supervisor that throws shouldn't 500 the admin endpoint."""
    lc = UvLifecycle(_SupervisorWithLogs(raise_on_logs=True))
    out = lc.logs("p1", tail=10)
    assert out.startswith("<supervisor.logs raised: "), out


def test_docker_lifecycle_logs_invokes_docker_logs(tmp_path):
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(returncode=0, stdout="line1\nline2\n")
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    out = lc.logs("fft", tail=50)

    assert out == "line1\nline2"
    assert runner.calls == [(
        "docker", "logs", "--tail", "50", "magellon-plugin-fft",
    )]


def test_docker_lifecycle_logs_merges_stdout_and_stderr(tmp_path):
    """docker logs --no-follow writes container stdout to our stdout
    and container stderr to our stderr — both belong in the operator's
    view, merged."""
    _write_state(tmp_path, "fft", "magellon-plugin-fft")
    runner = _RecordingDockerRunner(
        returncode=0, stdout="out-line\n", stderr="err-line\n",
    )
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    out = lc.logs("fft", tail=10)
    assert "out-line" in out
    assert "err-line" in out


def test_docker_lifecycle_logs_returns_empty_when_state_missing(tmp_path):
    runner = _RecordingDockerRunner()
    lc = DockerLifecycle(plugins_dir=tmp_path, subprocess_runner=runner)

    assert lc.logs("never-installed", tail=10) == ""
    assert runner.calls == []
