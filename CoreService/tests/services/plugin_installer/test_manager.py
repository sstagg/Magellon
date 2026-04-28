"""Tests for ``PluginInstallManager`` (P4).

The manager doesn't itself install — it picks the right Installer
per the host's capabilities and dispatches. What we pin here:

  - Walks ``manifest.install`` in order; first match wins.
  - Refuses if no install method matches; the error names every
    method's failed predicates so operators can debug.
  - Refuses if the plugin is already installed under any installer.
  - Health-check rollback: install succeeds but plugin doesn't
    announce → manager calls uninstall and reports failure.
  - Cross-installer uninstall: any registered installer that claims
    the plugin handles its uninstall.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

from magellon_sdk.archive.manifest import (
    InstallSpec,
    PluginArchiveManifest,
    dump_manifest_yaml,
    uuid7,
)

from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import (
    InstallResult,
    Installer,
    RuntimeConfig,
    UninstallResult,
)


# ---------------------------------------------------------------------------
# Fakes — we mock both Installer and host info so manager tests don't
# touch the filesystem or invoke uv.
# ---------------------------------------------------------------------------

class _FakeInstaller:
    """Stand-in for an Installer with knobs the manager tests poke."""

    def __init__(
        self,
        method: str,
        *,
        supports_failures: List[str] | None = None,
        installed_plugins: set[str] | None = None,
        install_result: InstallResult | None = None,
        uninstall_result: UninstallResult | None = None,
    ) -> None:
        self.method = method
        self._supports_failures = supports_failures or []
        self._installed = installed_plugins or set()
        self._install_result = install_result
        self._uninstall_result = uninstall_result
        self.install_calls: list = []
        self.uninstall_calls: list = []

    def supports(self, spec, host):
        if spec.method != self.method:
            return [f"method != {self.method}"]
        return list(self._supports_failures)

    def install(self, archive_path, manifest, install_spec, runtime):
        self.install_calls.append((archive_path, manifest, install_spec, runtime))
        if self._install_result is not None:
            return self._install_result
        self._installed.add(manifest.plugin_id)
        return InstallResult(
            success=True,
            plugin_id=manifest.plugin_id,
            install_method=self.method,
        )

    def uninstall(self, plugin_id, *, preserve_as_backup=False):
        self.uninstall_calls.append((plugin_id, preserve_as_backup))
        if self._uninstall_result is not None:
            return self._uninstall_result
        self._installed.discard(plugin_id)
        return UninstallResult(success=True, plugin_id=plugin_id)

    def is_installed(self, plugin_id):
        return plugin_id in self._installed


def _build_archive(tmp_path: Path, install_methods: List[dict]) -> Path:
    """Build a minimal .mpn whose manifest declares the given install
    methods (in order)."""
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


def _no_failures_host(_required_binaries):
    """Default host_info_provider: every probe pretends to succeed.
    Tests override per-test for the failure cases."""
    return HostInfo(
        docker_daemon=True,
        binaries_on_path=["ctffind4", "MotionCor2"],
        python_version="3.12.0",
        gpu_count=4,
        os="linux",
        arch="x86_64",
    )


# ---------------------------------------------------------------------------
# Picking
# ---------------------------------------------------------------------------

def test_picks_first_install_method_whose_predicates_pass(tmp_path):
    """Order in the manifest is preference. Manager walks top to
    bottom; first method whose support is empty wins."""
    archive = _build_archive(tmp_path, [
        {"method": "docker", "image": "x:1", "requires": [{"docker_daemon": True}]},
        {"method": "uv", "pyproject": "pyproject.toml"},
    ])
    docker = _FakeInstaller("docker")
    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager(
        [docker, uv], host_info_provider=_no_failures_host,
    )

    mgr.install(archive, _runtime())

    assert len(docker.install_calls) == 1
    assert len(uv.install_calls) == 0


def test_falls_through_to_next_install_method_when_first_fails_predicates(tmp_path):
    """Plugin's preferred method is docker but host has no daemon →
    fall through to uv."""
    archive = _build_archive(tmp_path, [
        {"method": "docker", "image": "x:1", "requires": [{"docker_daemon": True}]},
        {"method": "uv", "pyproject": "pyproject.toml"},
    ])
    docker = _FakeInstaller("docker", supports_failures=["docker_daemon: want True, got False"])
    uv = _FakeInstaller("uv")

    def host_no_docker(_):
        return HostInfo(docker_daemon=False, python_version="3.12.0")

    mgr = PluginInstallManager(
        [docker, uv], host_info_provider=host_no_docker,
    )
    mgr.install(archive, _runtime())

    assert len(docker.install_calls) == 0
    assert len(uv.install_calls) == 1


def test_skips_install_methods_with_no_registered_installer(tmp_path):
    """Plugin says ``method: subprocess`` but no SubprocessInstaller
    is registered → manager moves on to the next method instead of
    crashing."""
    archive = _build_archive(tmp_path, [
        {"method": "subprocess", "pyproject": "pyproject.toml"},
        {"method": "uv", "pyproject": "pyproject.toml"},
    ])
    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager([uv], host_info_provider=_no_failures_host)

    result = mgr.install(archive, _runtime())

    assert result.success
    assert len(uv.install_calls) == 1


# ---------------------------------------------------------------------------
# No match — explanatory error
# ---------------------------------------------------------------------------

def test_install_refused_when_no_method_matches(tmp_path):
    archive = _build_archive(tmp_path, [
        {"method": "docker", "image": "x:1", "requires": [{"docker_daemon": True}]},
    ])
    docker = _FakeInstaller("docker", supports_failures=["docker_daemon: want True, got False"])

    def host_no_docker(_):
        return HostInfo(docker_daemon=False)

    mgr = PluginInstallManager([docker], host_info_provider=host_no_docker)
    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "no install method matched" in result.error
    assert "docker_daemon" in result.error  # operator-debugging surface


def test_install_refused_when_no_method_has_a_registered_installer(tmp_path):
    """Plugin requires only methods we don't support — the error
    must point at the missing impls."""
    archive = _build_archive(tmp_path, [
        {"method": "subprocess", "pyproject": "x"},
    ])
    mgr = PluginInstallManager([], host_info_provider=_no_failures_host)

    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "no installer registered" in result.error


# ---------------------------------------------------------------------------
# Already-installed refusal
# ---------------------------------------------------------------------------

def test_install_refuses_when_plugin_already_installed_under_same_method(tmp_path):
    """The upgrade flow (P6) handles version replacement; install
    must not silently overwrite a live plugin."""
    archive = _build_archive(tmp_path, [
        {"method": "uv", "pyproject": "pyproject.toml"},
    ])
    uv = _FakeInstaller("uv", installed_plugins={"tp"})
    mgr = PluginInstallManager([uv], host_info_provider=_no_failures_host)

    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "already installed" in result.error
    assert len(uv.install_calls) == 0


def test_install_refuses_when_plugin_already_installed_under_different_method(tmp_path):
    """Operator installed via Docker, then archive only declares uv —
    must still refuse, not double-install. Avoiding the case where
    one plugin runs in two install modes simultaneously."""
    archive = _build_archive(tmp_path, [
        {"method": "uv", "pyproject": "pyproject.toml"},
    ])
    docker = _FakeInstaller("docker", installed_plugins={"tp"})
    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager([docker, uv], host_info_provider=_no_failures_host)

    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "already installed" in result.error


# ---------------------------------------------------------------------------
# Health check rollback
# ---------------------------------------------------------------------------

def test_install_rolls_back_when_health_check_fails(tmp_path):
    """Plugin installs successfully but never announces. An
    installed-but-dead plugin is worse than no plugin — operators
    see a stale 'installed' state in the UI. The manager calls
    uninstall to clean up."""
    archive = _build_archive(tmp_path, [
        {"method": "uv", "pyproject": "pyproject.toml"},
    ])
    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager(
        [uv],
        host_info_provider=_no_failures_host,
        health_check=lambda _id, _t: False,  # never announces
    )

    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "did not announce" in result.error
    # rolled back — health-check failure issues a non-backup uninstall
    assert ("tp", False) in uv.uninstall_calls


def test_install_skips_health_check_when_manifest_opts_out(tmp_path):
    """Future plugins with ``expected_announce: false`` (e.g. cron
    plugins, post-install hooks) shouldn't be rolled back for not
    announcing."""
    manifest = PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": "tp",
        "archive_id": str(uuid7()),
        "name": "t",
        "version": "0.1.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": [{"method": "uv", "pyproject": "pyproject.toml"}],
        "health_check": {"timeout_seconds": 30, "expected_announce": False},
    })
    yaml_bytes = dump_manifest_yaml(manifest).encode()
    archive = tmp_path / "tp.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)

    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager(
        [uv],
        host_info_provider=_no_failures_host,
        health_check=lambda _id, _t: False,
    )

    result = mgr.install(archive, _runtime())

    assert result.success
    assert uv.uninstall_calls == []  # no rollback


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def test_install_reports_manifest_load_failure(tmp_path):
    """A malformed archive (no manifest at all) must be rejected
    with a clear error before any installer logic runs."""
    archive = tmp_path / "broken.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("README.md", b"no manifest here")

    mgr = PluginInstallManager(
        [_FakeInstaller("uv")], host_info_provider=_no_failures_host,
    )
    result = mgr.install(archive, _runtime())

    assert not result.success
    assert "manifest" in result.error.lower()


def test_install_falls_back_to_legacy_plugin_yaml(tmp_path):
    """v0 archives have only plugin.yaml, no manifest.yaml. The
    manager must read it (matching the pack CLI's read fallback)."""
    manifest = PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": "tp",
        "archive_id": str(uuid7()),
        "name": "t",
        "version": "0.1.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": [{"method": "uv", "pyproject": "x"}],
    })
    archive = tmp_path / "v0.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("plugin.yaml", dump_manifest_yaml(manifest).encode())  # legacy only

    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager([uv], host_info_provider=_no_failures_host)
    result = mgr.install(archive, _runtime())

    assert result.success


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def test_uninstall_finds_owning_installer(tmp_path):
    """Plugin was installed via uv; uninstall is called without
    knowing the method. Manager probes each installer; the one that
    claims the plugin handles uninstall."""
    docker = _FakeInstaller("docker")
    uv = _FakeInstaller("uv", installed_plugins={"tp"})
    mgr = PluginInstallManager([docker, uv], host_info_provider=_no_failures_host)

    result = mgr.uninstall("tp")

    assert result.success
    assert uv.uninstall_calls == [("tp", False)]
    assert docker.uninstall_calls == []


def test_uninstall_reports_not_installed(tmp_path):
    docker = _FakeInstaller("docker")
    uv = _FakeInstaller("uv")
    mgr = PluginInstallManager([docker, uv], host_info_provider=_no_failures_host)

    result = mgr.uninstall("nothing")

    assert not result.success
    assert "not installed" in result.error
