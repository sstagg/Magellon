"""Upgrade-rollback probes — guarantees the upgrade path actually
preserves operator state across the cases the docstring claims.

What we pin:

  - A successful upgrade leaves at most ONE .bak on disk (the
    upgrade that just finished). Stale .bak from before isn't
    silently retained — that would accumulate across cycles.
  - A failed upgrade with an in-progress new install leaves the
    old version restored and no half-state.
  - Cross-method upgrade (uv → docker) — the new install switches
    methods; the rollback path knows to restore the old (uv) .bak.
  - The manifest version mismatch refusal happens BEFORE the old
    install is touched.
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
from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import RuntimeConfig
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
    version: str = "0.1.0",
    method: str = "uv",
    archive_name: Optional[str] = None,
) -> Path:
    if method == "uv":
        install = [{"method": "uv", "pyproject": "pyproject.toml"}]
        files = {
            "pyproject.toml": b'[project]\nname = "x"\nversion = "0.0.1"\n',
            "main.py": b"# noop\n",
        }
        checksums = {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        }
    else:
        install = [{"method": "docker", "image": "ghcr.io/test/x:1"}]
        files = {"Dockerfile": b"FROM python:3.12\n"}
        checksums = {}

    manifest = PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": plugin_id,
        "archive_id": str(uuid7()),
        "name": "T",
        "version": version,
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": install,
        "file_checksums": checksums,
    })
    yaml_bytes = dump_manifest_yaml(manifest).encode()

    archive = tmp_path / (archive_name or f"{plugin_id}-{version}-{method}.mpn")
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
        for name, content in files.items():
            z.writestr(name, content)
    return archive


def _make_uv_manager(plugins_dir: Path):
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    return PluginInstallManager(
        [inst],
        host_info_provider=lambda **_kw: HostInfo(python_version="3.12.0"),
    ), inst


def _make_dual_manager(plugins_dir: Path):
    uv = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    dock = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    return PluginInstallManager(
        [uv, dock],
        host_info_provider=lambda **_kw: HostInfo(
            python_version="3.12.0", docker_daemon=True,
        ),
    ), uv, dock


# ---------------------------------------------------------------------------
# .bak accumulation after successful upgrade
# ---------------------------------------------------------------------------


class TestBackupHygiene:
    def test_successful_upgrade_leaves_one_bak(self, tmp_path):
        """After ONE upgrade, exactly the most-recent .bak exists.
        Three upgrades → still only one .bak. The plan's hypothesis
        was that a successful upgrade might leave the .bak forever —
        this test confirms the actual behaviour."""
        plugins_dir = tmp_path / "installed"
        mgr, _ = _make_uv_manager(plugins_dir)

        mgr.install(_build_archive(tmp_path, version="0.1.0"), _runtime())
        mgr.upgrade(
            "test-plugin",
            _build_archive(tmp_path, version="0.2.0"),
            _runtime(),
        )
        mgr.upgrade(
            "test-plugin",
            _build_archive(tmp_path, version="0.3.0"),
            _runtime(),
        )
        mgr.upgrade(
            "test-plugin",
            _build_archive(tmp_path, version="0.4.0"),
            _runtime(),
        )

        baks = sorted(
            p.name for p in plugins_dir.iterdir() if p.name.endswith(".bak")
        )
        # Exactly one .bak — the previous upgrade's pre-upgrade state.
        assert len(baks) == 1, (
            f"expected single .bak after three upgrades, found: {baks}"
        )
        # And it's the immediately-prior version.
        assert baks == ["test-plugin.0.3.0.bak"]

    def test_uninstall_does_not_create_bak(self, tmp_path):
        """Plain uninstall (not via upgrade) should NOT leave a .bak —
        only the upgrade flow uses preserve_as_backup=True."""
        plugins_dir = tmp_path / "installed"
        mgr, _ = _make_uv_manager(plugins_dir)

        mgr.install(_build_archive(tmp_path, version="0.1.0"), _runtime())
        mgr.uninstall("test-plugin")

        baks = [p for p in plugins_dir.iterdir() if p.name.endswith(".bak")]
        assert baks == []


# ---------------------------------------------------------------------------
# Failure rollback details
# ---------------------------------------------------------------------------


class TestFailureRollback:
    def test_plugin_id_mismatch_does_not_touch_old_install(self, tmp_path):
        """Upload an archive whose plugin_id is for a different plugin.
        The refusal must come BEFORE the old install's .bak is created."""
        plugins_dir = tmp_path / "installed"
        mgr, _ = _make_uv_manager(plugins_dir)

        mgr.install(_build_archive(tmp_path, plugin_id="alpha", version="0.1.0"), _runtime())
        other = _build_archive(tmp_path, plugin_id="beta", version="0.5.0")
        result = mgr.upgrade("alpha", other, _runtime())

        assert not result.success
        # Old install absolutely untouched.
        assert (plugins_dir / "alpha").is_dir()
        # No .bak should have been created — refusal was upfront.
        baks = [p for p in plugins_dir.iterdir() if p.name.endswith(".bak")]
        assert baks == [], f"plugin_id refusal should not create .bak: {baks}"

    def test_version_refusal_does_not_touch_old_install(self, tmp_path):
        """Same idea: an older version is refused upfront."""
        plugins_dir = tmp_path / "installed"
        mgr, _ = _make_uv_manager(plugins_dir)

        mgr.install(_build_archive(tmp_path, version="0.5.0"), _runtime())
        older = _build_archive(
            tmp_path, version="0.1.0", archive_name="older.mpn",
        )
        result = mgr.upgrade("test-plugin", older, _runtime())

        assert not result.success
        assert (plugins_dir / "test-plugin").is_dir()
        baks = [p for p in plugins_dir.iterdir() if p.name.endswith(".bak")]
        assert baks == [], f"version refusal should not create .bak: {baks}"


# ---------------------------------------------------------------------------
# Cross-method upgrade — uv → docker (manager allows it per docstring)
# ---------------------------------------------------------------------------


class TestCrossMethodUpgrade:
    """The manager's upgrade docstring claims cross-method upgrades are
    permitted (operator pinning the new method). The .bak comes from
    the OLD installer's uninstall path; the new install runs on the
    NEW installer. Rollback must restore from the .bak the OLD installer
    created."""

    def test_uv_to_docker_upgrade_succeeds(self, tmp_path):
        plugins_dir = tmp_path / "installed"
        mgr, uv, dock = _make_dual_manager(plugins_dir)

        # Install old via uv.
        mgr.install(_build_archive(
            tmp_path, plugin_id="hybrid", version="0.1.0", method="uv",
        ), _runtime())
        assert uv.is_installed("hybrid")
        assert not dock.is_installed("hybrid")

        # Upgrade pinning docker as the new method.
        new = _build_archive(
            tmp_path, plugin_id="hybrid", version="0.2.0", method="docker",
        )
        result = mgr.upgrade(
            "hybrid", new, _runtime(), preferred_method="docker",
        )

        assert result.success, result.error
        assert dock.is_installed("hybrid")
        assert not uv.is_installed("hybrid")
        # The .bak from the uv install side.
        assert (plugins_dir / "hybrid.0.1.0.bak").exists()


# ---------------------------------------------------------------------------
# Bak hygiene under upgrade failure
# ---------------------------------------------------------------------------


class TestBakHygieneOnFailure:
    def test_failed_upgrade_restores_canonical_slot(self, tmp_path):
        """Already covered in test_install_lifecycle.py but pinned again
        here because the post-rollback state was a candidate bug — if
        rollback leaks a .bak (rename failed silently) the operator
        gets a confusing state on next install."""
        plugins_dir = tmp_path / "installed"
        uv = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
        mgr = PluginInstallManager(
            [uv],
            host_info_provider=lambda **_kw: HostInfo(python_version="3.12.0"),
        )

        mgr.install(_build_archive(tmp_path, version="0.1.0"), _runtime())
        # Switch the installer to a failing runner so the new install fails.
        uv._run = _stub_runner(returncode=1)
        result = mgr.upgrade(
            "test-plugin",
            _build_archive(tmp_path, version="0.2.0"),
            _runtime(),
        )

        assert not result.success
        assert (plugins_dir / "test-plugin").is_dir()
        # .bak consumed by rollback rename — no residue.
        baks = [p for p in plugins_dir.iterdir() if p.name.endswith(".bak")]
        assert baks == [], f"failed upgrade should not leak .bak, found: {baks}"
