"""Manager × supervisor integration tests (PI-2).

Pins the lifecycle order: install_unit + start AFTER successful
install but BEFORE health-check; stop + remove_unit BEFORE
uninstall (so systemd has released the install dir). Failures in
the supervisor roll back the install — half-supervised state is
worse than no install.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

from magellon_sdk.archive.manifest import (
    PluginArchiveManifest,
    dump_manifest_yaml,
    uuid7,
)

from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
    UninstallResult,
)
from services.plugin_installer.supervisor import SupervisorResult


def _build_archive(tmp_path: Path, install_methods: List[dict]) -> Path:
    manifest = PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": "tp",
        "archive_id": str(uuid7()),
        "name": "t",
        "version": "0.1.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": install_methods,
    })
    yaml_bytes = dump_manifest_yaml(manifest).encode()
    archive = tmp_path / "tp.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
    return archive


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(broker_url="amqp://x", gpfs_root="/g")


def _no_failures_host(*, probe_binaries=None):
    return HostInfo(
        docker_daemon=True,
        binaries_on_path=list(probe_binaries or []),
        python_version="3.12.0",
        os="linux",
        arch="x86_64",
    )


class _FakeUvInstaller:
    """Returns success for install/uninstall; tracks calls. Pretends
    to materialize an install_dir so the supervisor branch fires."""

    method = "uv"

    def __init__(self):
        self.install_calls = []
        self.uninstall_calls = []
        self._installed = set()

    def supports(self, spec, host):
        return [] if spec.method == "uv" else ["wrong method"]

    def install(self, archive_path, manifest, install_spec, runtime):
        self.install_calls.append((manifest.plugin_id,))
        self._installed.add(manifest.plugin_id)
        return InstallResult(
            success=True,
            plugin_id=manifest.plugin_id,
            install_method="uv",
            install_dir=Path("/fake/installed/") / manifest.plugin_id,
        )

    def uninstall(self, plugin_id, *, preserve_as_backup=False):
        self.uninstall_calls.append((plugin_id, preserve_as_backup))
        self._installed.discard(plugin_id)
        return UninstallResult(success=True, plugin_id=plugin_id)

    def is_installed(self, plugin_id):
        return plugin_id in self._installed


class _RecordingSupervisor:
    """Tracks every call so tests can assert ordering."""

    name = "recording"

    def __init__(self, *, fail_on=None):
        self.calls: list[tuple[str, str]] = []
        self._fail_on = fail_on  # ('install_unit' | 'start' | None)

    def install_unit(self, plugin_id, install_dir):
        self.calls.append(("install_unit", plugin_id))
        if self._fail_on == "install_unit":
            return SupervisorResult(success=False, plugin_id=plugin_id, error="boom")
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def remove_unit(self, plugin_id):
        self.calls.append(("remove_unit", plugin_id))
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def start(self, plugin_id):
        self.calls.append(("start", plugin_id))
        if self._fail_on == "start":
            return SupervisorResult(success=False, plugin_id=plugin_id, error="exec failed")
        return SupervisorResult(success=True, plugin_id=plugin_id)

    def stop(self, plugin_id):
        self.calls.append(("stop", plugin_id))
        return SupervisorResult(success=True, plugin_id=plugin_id)


# ---------------------------------------------------------------------------
# Install path
# ---------------------------------------------------------------------------


def test_install_calls_supervisor_install_unit_then_start_in_order(tmp_path):
    archive = _build_archive(tmp_path, [{"method": "uv", "pyproject": "pyproject.toml"}])
    installer = _FakeUvInstaller()
    sup = _RecordingSupervisor()
    mgr = PluginInstallManager(
        [installer], host_info_provider=_no_failures_host, supervisor=sup,
    )

    result = mgr.install(archive, _runtime())

    assert result.success, result.error
    # Installer ran first, then supervisor saw install_unit, then start.
    op_names = [op for op, _ in sup.calls]
    assert op_names == ["install_unit", "start"]


def test_install_unit_failure_rolls_back_installer(tmp_path):
    archive = _build_archive(tmp_path, [{"method": "uv", "pyproject": "pyproject.toml"}])
    installer = _FakeUvInstaller()
    sup = _RecordingSupervisor(fail_on="install_unit")
    mgr = PluginInstallManager(
        [installer], host_info_provider=_no_failures_host, supervisor=sup,
    )

    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "supervisor install_unit failed" in (result.error or "")
    # Rollback: uninstall was called.
    assert installer.uninstall_calls == [("tp", False)]


def test_start_failure_rolls_back_unit_and_installer(tmp_path):
    """If start fails, leave neither a unit file nor an install
    directory behind. A failed install must be cleanly retryable."""
    archive = _build_archive(tmp_path, [{"method": "uv", "pyproject": "pyproject.toml"}])
    installer = _FakeUvInstaller()
    sup = _RecordingSupervisor(fail_on="start")
    mgr = PluginInstallManager(
        [installer], host_info_provider=_no_failures_host, supervisor=sup,
    )

    result = mgr.install(archive, _runtime())

    assert not result.success
    op_names = [op for op, _ in sup.calls]
    # remove_unit must have run after the failed start.
    assert "remove_unit" in op_names
    assert installer.uninstall_calls == [("tp", False)]


def test_uninstall_stops_and_removes_unit_before_reclaiming_dir(tmp_path):
    """Lifecycle ordering on the way down: stop → remove_unit →
    installer.uninstall. systemd would otherwise hold open file
    descriptors and the rmtree fails."""
    archive = _build_archive(tmp_path, [{"method": "uv", "pyproject": "pyproject.toml"}])
    installer = _FakeUvInstaller()
    sup = _RecordingSupervisor()
    mgr = PluginInstallManager(
        [installer], host_info_provider=_no_failures_host, supervisor=sup,
    )

    mgr.install(archive, _runtime())  # set up the installed state
    # Reset the tracker so we only see uninstall-side ops.
    sup.calls.clear()

    mgr.uninstall("tp")

    op_names = [op for op, _ in sup.calls]
    assert op_names == ["stop", "remove_unit"]
    assert installer.uninstall_calls == [("tp", False)]


# ---------------------------------------------------------------------------
# Docker installs skip supervision (container has its own lifecycle)
# ---------------------------------------------------------------------------


def test_docker_install_does_not_invoke_supervisor(tmp_path):
    """Docker containers are their own process supervisors.
    Supervisor is only relevant for uv installs."""
    archive = _build_archive(tmp_path, [{"method": "docker", "image": "img:1"}])

    class _FakeDocker(_FakeUvInstaller):
        method = "docker"

        def supports(self, spec, host):
            return [] if spec.method == "docker" else ["wrong method"]

        def install(self, archive_path, manifest, install_spec, runtime):
            self.install_calls.append((manifest.plugin_id,))
            self._installed.add(manifest.plugin_id)
            return InstallResult(
                success=True,
                plugin_id=manifest.plugin_id,
                install_method="docker",
                install_dir=None,
            )

    installer = _FakeDocker()
    sup = _RecordingSupervisor()
    mgr = PluginInstallManager(
        [installer], host_info_provider=_no_failures_host, supervisor=sup,
    )

    result = mgr.install(archive, _runtime())

    assert result.success
    assert sup.calls == []
