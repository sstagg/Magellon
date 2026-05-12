"""Verify the install pipeline rolls back when health check fails.

The factory wires a real liveness-based health check (Phase 1.1) — an
install that completes the disk side but never announces on the bus
must NOT be left lingering. Pre-1.1 the default was a no-op so this
gap was invisible.

What we pin:

  - ``install()`` with a stub health check that returns False rolls
    back: install dir removed, supervisor unit removed, port released.
  - Health check is honored when ``manifest.health_check.expected_announce``
    is True (the default).
  - Health check is skipped when the manifest opts out (some test
    archives set ``expected_announce: false``).
"""
from __future__ import annotations

import hashlib
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

from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import RuntimeConfig
from services.plugin_installer.supervisor import NoOpSupervisor
from services.plugin_installer.uv_installer import UvInstaller


def _stub_runner(returncode: int = 0):
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout="", stderr="",
        )
    return _run


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(broker_url="amqp://x", gpfs_root="/g")


def _build_archive(
    tmp_path: Path,
    *,
    plugin_id: str = "test-plugin",
    expected_announce: bool = True,
) -> Path:
    files = {
        "pyproject.toml": b'[project]\nname = "x"\nversion = "0.0.1"\n',
        "main.py": b"# noop\n",
    }
    manifest_dict = {
        "manifest_version": "1",
        "plugin_id": plugin_id,
        "archive_id": str(uuid7()),
        "name": "T",
        "version": "0.1.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": [{"method": "uv", "pyproject": "pyproject.toml"}],
        "file_checksums": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        },
        "health_check": {
            "expected_announce": expected_announce,
            "timeout_seconds": 1,  # keep tests fast
        },
    }
    manifest = PluginArchiveManifest.model_validate(manifest_dict)
    yaml_bytes = dump_manifest_yaml(manifest).encode()

    archive = tmp_path / f"{plugin_id}.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
        for name, content in files.items():
            z.writestr(name, content)
    return archive


# ---------------------------------------------------------------------------
# Health check fails → rollback
# ---------------------------------------------------------------------------


class TestHealthCheckFailureRollsBack:
    def test_failed_announce_removes_install_dir(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        inst = UvInstaller(
            plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
        )
        mgr = PluginInstallManager(
            [inst],
            host_info_provider=lambda **_kw: HostInfo(python_version="3.12.0"),
            health_check=lambda plugin_id, timeout: False,  # never announces
            supervisor=NoOpSupervisor(),
        )

        result = mgr.install(_build_archive(tmp_path), _runtime())

        assert not result.success
        assert "did not announce" in (result.error or "").lower() or \
               "rolled back" in (result.error or "").lower()
        # Install dir gone — operator gets a clean slate.
        assert not (plugins_dir / "test-plugin").exists()

    def test_failed_announce_releases_port(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        inst = UvInstaller(
            plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
        )
        mgr = PluginInstallManager(
            [inst],
            host_info_provider=lambda **_kw: HostInfo(python_version="3.12.0"),
            health_check=lambda plugin_id, timeout: False,
            supervisor=NoOpSupervisor(),
        )

        mgr.install(_build_archive(tmp_path), _runtime())

        # Port assignment should be released back. The allocator's
        # state file should not contain the plugin_id.
        state_path = plugins_dir / ".port_assignments.json"
        if state_path.exists():
            import json
            assignments = json.loads(state_path.read_text())
            assert "test-plugin" not in assignments


# ---------------------------------------------------------------------------
# Health check OK → install succeeds
# ---------------------------------------------------------------------------


class TestHealthCheckSuccess:
    def test_successful_announce_keeps_install(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        inst = UvInstaller(
            plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
        )
        mgr = PluginInstallManager(
            [inst],
            host_info_provider=lambda **_kw: HostInfo(python_version="3.12.0"),
            health_check=lambda plugin_id, timeout: True,
            supervisor=NoOpSupervisor(),
        )

        result = mgr.install(_build_archive(tmp_path), _runtime())

        assert result.success, result.error
        assert (plugins_dir / "test-plugin").is_dir()


# ---------------------------------------------------------------------------
# Health check is skipped when manifest opts out
# ---------------------------------------------------------------------------


class TestHealthCheckOptOut:
    def test_manifest_disables_announce_skips_health_check(self, tmp_path):
        """When ``manifest.health_check.expected_announce=False``, the
        manager bypasses the health check entirely. Useful for plugins
        that intentionally don't announce (e.g. one-shot batch tools)."""
        plugins_dir = tmp_path / "installed"
        inst = UvInstaller(
            plugins_dir=plugins_dir, subprocess_runner=_stub_runner(),
        )
        was_called = {"value": False}

        def health(plugin_id, timeout):
            was_called["value"] = True
            return False  # would normally fail

        mgr = PluginInstallManager(
            [inst],
            host_info_provider=lambda **_kw: HostInfo(python_version="3.12.0"),
            health_check=health,
            supervisor=NoOpSupervisor(),
        )

        result = mgr.install(
            _build_archive(tmp_path, expected_announce=False), _runtime(),
        )

        assert result.success, result.error
        assert was_called["value"] is False, (
            "manifest opt-out should skip the health check entirely"
        )
