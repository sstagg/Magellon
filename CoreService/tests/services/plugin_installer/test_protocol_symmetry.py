"""Symmetry probes for the ``Installer`` and ``BackendLifecycle`` Protocols.

The Strategy seam works only if every impl behaves consistently for the
verbs they share. These tests parametrize over both impls and pin the
shared contract — anything that breaks symmetry surfaces here before it
breaks operator workflows.

Verbs we cover:
  - ``install`` → ``is_installed`` returns True.
  - ``uninstall`` → ``is_installed`` returns False.
  - ``start`` / ``stop`` / ``restart`` → ``LifecycleResult.success`` consistent.
  - ``status`` returns a ``LifecycleStatus`` value (typed, never None).
  - ``pause`` raises ``NotSupportedError`` on uv; returns ``LifecycleResult``
    on docker.
  - ``logs`` returns ``str`` for both methods (empty when no source).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

import pytest

from magellon_sdk.archive.manifest import (
    PluginArchiveManifest,
    dump_manifest_yaml,
    uuid7,
)

from services.plugin_installer.docker_installer import DockerInstaller
from services.plugin_installer.lifecycle import (
    DockerLifecycle,
    LifecycleResult,
    LifecycleStatus,
    NotSupportedError,
    UvLifecycle,
)
from services.plugin_installer.supervisor import NoOpSupervisor
from services.plugin_installer.protocol import RuntimeConfig
from services.plugin_installer.uv_installer import UvInstaller


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _stub_runner(returncode: int = 0, stdout: str = ""):
    calls: list[dict] = []

    def _run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr="",
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(broker_url="amqp://x", gpfs_root="/g")


def _build_archive(
    tmp_path: Path,
    *,
    plugin_id: str,
    method: str,
    version: str = "0.1.0",
) -> tuple[Path, PluginArchiveManifest]:
    """Build a minimal .mpn for the requested install method."""
    if method == "uv":
        install = [{"method": "uv", "pyproject": "pyproject.toml"}]
        files = {
            "pyproject.toml": b'[project]\nname = "x"\nversion = "0.0.1"\n',
            "main.py": b"# noop\n",
        }
    elif method == "docker":
        install = [{"method": "docker", "image": "ghcr.io/test/x:1"}]
        files = {"Dockerfile": b"FROM python:3.12\n"}
    else:
        raise ValueError(f"unknown method: {method!r}")

    manifest = PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": plugin_id,
        "archive_id": str(uuid7()),
        "name": plugin_id,
        "version": version,
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": install,
        "file_checksums": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        } if method == "uv" else {},
    })
    yaml_bytes = dump_manifest_yaml(manifest).encode()

    archive = tmp_path / f"{plugin_id}-{method}.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
        for name, content in files.items():
            z.writestr(name, content)
    return archive, manifest


@pytest.fixture(params=["uv", "docker"])
def installer_method(request):
    return request.param


@pytest.fixture()
def installed_plugin(tmp_path, installer_method):
    """Yields ``(installer, plugin_id, manifest)`` with the plugin
    already installed under ``tmp_path / "installed"``."""
    plugins_dir = tmp_path / "installed"
    if installer_method == "uv":
        inst = UvInstaller(
            plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
        )
    else:
        inst = DockerInstaller(
            plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
        )

    plugin_id = "sym-plugin"
    archive, manifest = _build_archive(
        tmp_path, plugin_id=plugin_id, method=installer_method,
    )
    result = inst.install(archive, manifest, manifest.install[0], _runtime())
    assert result.success, f"setup install failed: {result.error}"
    return inst, plugin_id, manifest


# ---------------------------------------------------------------------------
# Installer Protocol shared contract
# ---------------------------------------------------------------------------


class TestInstallerSymmetry:
    def test_is_installed_true_after_install(self, installed_plugin):
        inst, plugin_id, _ = installed_plugin
        assert inst.is_installed(plugin_id) is True

    def test_is_installed_false_for_unknown_plugin(self, installed_plugin):
        inst, _, _ = installed_plugin
        assert inst.is_installed("does-not-exist") is False

    def test_install_refuses_duplicate(self, tmp_path, installer_method):
        """Second install of the same plugin_id must fail with a
        meaningful error — both methods refuse, neither corrupts."""
        plugins_dir = tmp_path / "installed"
        if installer_method == "uv":
            inst = UvInstaller(
                plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
            )
        else:
            inst = DockerInstaller(
                plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
            )

        archive, manifest = _build_archive(
            tmp_path, plugin_id="dup-plugin", method=installer_method,
        )
        first = inst.install(archive, manifest, manifest.install[0], _runtime())
        assert first.success

        second = inst.install(archive, manifest, manifest.install[0], _runtime())
        assert not second.success
        assert "already installed" in (second.error or "").lower()

    def test_uninstall_removes_state(self, installed_plugin):
        inst, plugin_id, _ = installed_plugin
        result = inst.uninstall(plugin_id)
        assert result.success, result.error
        assert inst.is_installed(plugin_id) is False

    def test_uninstall_unknown_plugin_returns_failure(self, tmp_path, installer_method):
        plugins_dir = tmp_path / "installed"
        plugins_dir.mkdir()
        if installer_method == "uv":
            inst = UvInstaller(
                plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
            )
        else:
            inst = DockerInstaller(
                plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
            )

        result = inst.uninstall("never-installed")
        assert not result.success
        assert "not installed" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# BackendLifecycle Protocol shared contract
# ---------------------------------------------------------------------------


@pytest.fixture(params=["uv", "docker"])
def lifecycle_method(request):
    return request.param


@pytest.fixture()
def lifecycle(tmp_path, lifecycle_method):
    """A lifecycle controller with a plugin already 'installed' on
    disk — for DockerLifecycle this means a sentinel install_state.json,
    for UvLifecycle a stub supervisor."""
    plugins_dir = tmp_path / "installed"
    plugin_id = "sym-plugin"
    if lifecycle_method == "uv":
        return UvLifecycle(NoOpSupervisor()), plugin_id
    plugin_dir = plugins_dir / plugin_id
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "install_state.json").write_text(json.dumps({
        "plugin_id": plugin_id,
        "version": "0.1.0",
        "method": "docker",
        "image_ref": "ghcr.io/test/x:1",
        "image_was_built": False,
        "container_name": f"magellon-plugin-{plugin_id}",
        "replicas": [{
            "replica_id": 0,
            "container_name": f"magellon-plugin-{plugin_id}",
            "host_port": 18000,
        }],
        "restart_policy": "on-failure",
        "restart_max_retries": 5,
    }))
    return (
        DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=_stub_runner()),
        plugin_id,
    )


class TestLifecycleSymmetry:
    def test_start_returns_lifecycle_result(self, lifecycle):
        lc, plugin_id = lifecycle
        result = lc.start(plugin_id)
        assert isinstance(result, LifecycleResult)
        assert result.plugin_id == plugin_id

    def test_stop_returns_lifecycle_result(self, lifecycle):
        lc, plugin_id = lifecycle
        result = lc.stop(plugin_id)
        assert isinstance(result, LifecycleResult)

    def test_restart_returns_lifecycle_result(self, lifecycle):
        lc, plugin_id = lifecycle
        result = lc.restart(plugin_id)
        assert isinstance(result, LifecycleResult)

    def test_status_returns_lifecycle_status_enum(self, lifecycle):
        lc, plugin_id = lifecycle
        status = lc.status(plugin_id)
        # Never None — the API contract is a typed enum.
        assert isinstance(status, LifecycleStatus)

    def test_logs_returns_string(self, lifecycle):
        """``logs()`` returns ``str``, never ``None`` — saves callers
        from needing to None-check."""
        lc, plugin_id = lifecycle
        out = lc.logs(plugin_id, tail=50)
        assert isinstance(out, str)

    def test_supports_pause_is_boolean(self, lifecycle):
        """``supports_pause`` is a class flag the manager + UI read.
        Must be a concrete bool, not None."""
        lc, _ = lifecycle
        assert isinstance(lc.supports_pause, bool)


# ---------------------------------------------------------------------------
# Asymmetric verbs — pause/unpause: docker-only
# ---------------------------------------------------------------------------


class TestPauseAsymmetry:
    """Pause is docker-only — uv raises ``NotSupportedError`` so the
    controller can map to HTTP 409 with an actionable message. These
    pin both halves so neither side drifts."""

    def test_uv_pause_raises_not_supported(self):
        lc = UvLifecycle(NoOpSupervisor())
        assert lc.supports_pause is False
        with pytest.raises(NotSupportedError) as exc_info:
            lc.pause("any-plugin")
        # Message must mention what to do instead.
        msg = str(exc_info.value).lower()
        assert "docker" in msg or "stop" in msg

    def test_uv_unpause_raises_not_supported(self):
        lc = UvLifecycle(NoOpSupervisor())
        with pytest.raises(NotSupportedError):
            lc.unpause("any-plugin")

    def test_docker_pause_returns_lifecycle_result(self, tmp_path):
        """DockerLifecycle's pause goes through the same docker subprocess
        path as start/stop — returns a LifecycleResult either way."""
        plugins_dir = tmp_path / "installed"
        plugin_dir = plugins_dir / "x"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "install_state.json").write_text(json.dumps({
            "plugin_id": "x", "version": "1",
            "method": "docker", "image_ref": "i:1", "image_was_built": False,
            "container_name": "magellon-plugin-x",
            "replicas": [{
                "replica_id": 0, "container_name": "magellon-plugin-x",
                "host_port": 18000,
            }],
        }))
        lc = DockerLifecycle(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
        assert lc.supports_pause is True
        result = lc.pause("x")
        assert isinstance(result, LifecycleResult)
        # Stub returncode=0 → success.
        assert result.success


# ---------------------------------------------------------------------------
# Method consistency — installer.method == lifecycle.method
# ---------------------------------------------------------------------------


class TestMethodNamingConsistency:
    """The manager indexes by ``installer.method`` and routes lifecycle
    by the same string. If these drift the manager breaks silently."""

    def test_uv_installer_and_lifecycle_share_method_string(self):
        assert UvInstaller.method == "uv"
        assert UvLifecycle.method == "uv"

    def test_docker_installer_and_lifecycle_share_method_string(self):
        assert DockerInstaller.method == "docker"
        assert DockerLifecycle.method == "docker"


# ---------------------------------------------------------------------------
# Clean-rollback symmetry — failed install leaves no residue
# ---------------------------------------------------------------------------


class TestFailedInstallCleanup:
    """A failed install must leave neither installer with a positive
    ``is_installed()`` answer. Otherwise the next install would 409."""

    def test_uv_install_failure_clears_state(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        # Make uv venv fail.
        inst = UvInstaller(
            plugins_dir=plugins_dir,
            subprocess_runner=_stub_runner(returncode=1),
        )
        archive, manifest = _build_archive(
            tmp_path, plugin_id="ufail", method="uv",
        )
        result = inst.install(archive, manifest, manifest.install[0], _runtime())
        assert not result.success
        # After failure, plugin must not be reported as installed.
        assert inst.is_installed("ufail") is False
        # No leftover directory.
        assert not (plugins_dir / "ufail").exists()

    def test_docker_install_failure_clears_state(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        # Make docker pull fail.
        inst = DockerInstaller(
            plugins_dir=plugins_dir,
            subprocess_runner=_stub_runner(returncode=1),
        )
        archive, manifest = _build_archive(
            tmp_path, plugin_id="dfail", method="docker",
        )
        result = inst.install(archive, manifest, manifest.install[0], _runtime())
        assert not result.success
        assert inst.is_installed("dfail") is False
        assert not (plugins_dir / "dfail").exists()
