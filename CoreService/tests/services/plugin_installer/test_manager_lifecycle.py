"""Manager × BackendLifecycle routing tests (Phase 1).

Pins the rule: ``manager.start/stop/restart`` looks up the owning
installer's ``method``, then routes through the matching
:class:`BackendLifecycle`. Pre-Phase-1 the manager always used the
single supervisor; that was fine for uv but blind to docker.
"""
from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from services.plugin_installer.lifecycle import (
    LifecycleResult,
    LifecycleStatus,
    NotSupportedError,
)
from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import (
    InstallResult,
    UninstallResult,
)


def _no_failures_host(*, probe_binaries=None):
    return HostInfo(
        docker_daemon=True,
        binaries_on_path=list(probe_binaries or []),
        python_version="3.12.0",
        os="linux",
        arch="x86_64",
    )


class _FakeInstaller:
    def __init__(self, method: str, *, installed: set):
        self.method = method
        self._installed = installed

    def supports(self, spec, host):
        return [] if spec.method == self.method else ["wrong method"]

    def install(self, archive_path, manifest, install_spec, runtime):
        self._installed.add(manifest.plugin_id)
        return InstallResult(
            success=True, plugin_id=manifest.plugin_id,
            install_method=self.method, install_dir=Path("/x"),
        )

    def uninstall(self, plugin_id, *, preserve_as_backup=False):
        self._installed.discard(plugin_id)
        return UninstallResult(success=True, plugin_id=plugin_id)

    def is_installed(self, plugin_id):
        return plugin_id in self._installed


class _FakeLifecycle:
    def __init__(self, method: str, *, supports_pause: bool = True):
        self.method = method
        self.supports_pause = supports_pause
        self.calls: List[str] = []

    def start(self, plugin_id):
        self.calls.append("start")
        return LifecycleResult(success=True, plugin_id=plugin_id, status=LifecycleStatus.RUNNING)

    def stop(self, plugin_id):
        self.calls.append("stop")
        return LifecycleResult(success=True, plugin_id=plugin_id, status=LifecycleStatus.STOPPED)

    def restart(self, plugin_id):
        self.calls.append("restart")
        return LifecycleResult(success=True, plugin_id=plugin_id, status=LifecycleStatus.RUNNING)

    def pause(self, plugin_id):
        if not self.supports_pause:
            raise NotSupportedError("pause not supported on this backend")
        self.calls.append("pause")
        return LifecycleResult(success=True, plugin_id=plugin_id, status=LifecycleStatus.PAUSED)

    def unpause(self, plugin_id):
        if not self.supports_pause:
            raise NotSupportedError("unpause not supported on this backend")
        self.calls.append("unpause")
        return LifecycleResult(success=True, plugin_id=plugin_id, status=LifecycleStatus.RUNNING)

    def status(self, plugin_id):
        return LifecycleStatus.RUNNING


def _mgr_with(installed_method: str):
    """Build a manager with both uv + docker installers; only the given
    method has the plugin installed."""
    uv = _FakeInstaller("uv", installed=set())
    docker = _FakeInstaller("docker", installed=set())
    uv_lc = _FakeLifecycle("uv", supports_pause=False)
    docker_lc = _FakeLifecycle("docker", supports_pause=True)

    mgr = PluginInstallManager(
        [uv, docker],
        host_info_provider=_no_failures_host,
        lifecycles=[uv_lc, docker_lc],
    )
    # Pretend the plugin is installed under one method only.
    if installed_method == "uv":
        uv._installed.add("p1")
    else:
        docker._installed.add("p1")
    return mgr, uv_lc, docker_lc


def test_start_routes_to_uv_lifecycle_for_uv_install():
    mgr, uv_lc, docker_lc = _mgr_with("uv")

    result = mgr.start("p1")

    assert result.success
    assert uv_lc.calls == ["start"]
    assert docker_lc.calls == []


def test_start_routes_to_docker_lifecycle_for_docker_install():
    """The core Phase 1 invariant — docker plugins get a real start."""
    mgr, uv_lc, docker_lc = _mgr_with("docker")

    result = mgr.start("p1")

    assert result.success
    assert docker_lc.calls == ["start"]
    assert uv_lc.calls == []


def test_stop_routes_by_method():
    mgr, uv_lc, docker_lc = _mgr_with("docker")
    mgr.stop("p1")
    assert docker_lc.calls == ["stop"]
    assert uv_lc.calls == []


def test_restart_routes_by_method():
    mgr, uv_lc, docker_lc = _mgr_with("docker")
    mgr.restart("p1")
    assert docker_lc.calls == ["restart"]
    assert uv_lc.calls == []


def test_lifecycle_on_uninstalled_plugin_returns_clean_error():
    mgr, _, _ = _mgr_with("uv")

    result = mgr.start("never-installed")

    assert not result.success
    assert "not installed" in (result.error or "")


def test_status_routes_by_method():
    mgr, _, docker_lc = _mgr_with("docker")
    docker_lc.status = MagicMock(return_value=LifecycleStatus.PAUSED)

    assert mgr.status("p1") == LifecycleStatus.PAUSED


def test_status_unknown_when_not_installed():
    mgr, _, _ = _mgr_with("uv")
    assert mgr.status("never-installed") == LifecycleStatus.UNKNOWN


def test_is_running_returns_true_only_for_running_status():
    mgr, _, docker_lc = _mgr_with("docker")
    docker_lc.status = MagicMock(return_value=LifecycleStatus.RUNNING)
    assert mgr.is_running("p1") is True

    docker_lc.status = MagicMock(return_value=LifecycleStatus.PAUSED)
    assert mgr.is_running("p1") is False

    docker_lc.status = MagicMock(return_value=LifecycleStatus.STOPPED)
    assert mgr.is_running("p1") is False


def test_pause_routes_to_docker_lifecycle():
    mgr, _, docker_lc = _mgr_with("docker")
    result = mgr.pause("p1")
    assert result.success
    assert result.status == LifecycleStatus.PAUSED
    assert docker_lc.calls == ["pause"]


def test_pause_on_uv_raises_not_supported():
    """Controller maps NotSupportedError → HTTP 409 with the docker-only
    message; the manager re-raises so the controller can map cleanly."""
    mgr, _, _ = _mgr_with("uv")
    with pytest.raises(NotSupportedError, match="not supported"):
        mgr.pause("p1")


def test_unpause_on_uv_raises_not_supported():
    mgr, _, _ = _mgr_with("uv")
    with pytest.raises(NotSupportedError, match="not supported"):
        mgr.unpause("p1")


def test_supports_pause_reflects_install_method():
    mgr_uv, _, _ = _mgr_with("uv")
    assert mgr_uv.supports_pause("p1") is False

    mgr_docker, _, _ = _mgr_with("docker")
    assert mgr_docker.supports_pause("p1") is True


def test_supports_pause_false_for_uninstalled():
    mgr, _, _ = _mgr_with("uv")
    assert mgr.supports_pause("never-installed") is False


def test_manager_synthesizes_uv_lifecycle_when_lifecycles_arg_omitted():
    """Back-compat: pre-Phase-1 callers passing only ``supervisor=`` get
    a UvLifecycle wrapping it auto-synthesized so manager.start still
    routes through the supervisor for uv installs."""
    from services.plugin_installer.supervisor import NoOpSupervisor

    installed: set = {"p1"}
    uv = _FakeInstaller("uv", installed=installed)
    mgr = PluginInstallManager(
        [uv], host_info_provider=_no_failures_host,
        supervisor=NoOpSupervisor(),
    )
    # NoOp's start always reports success; the synthesized UvLifecycle
    # passes that through.
    result = mgr.start("p1")
    assert result.success
