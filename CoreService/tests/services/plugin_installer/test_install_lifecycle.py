"""Lifecycle tests for the install pipeline (P6).

End-to-end-ish: real ``UvInstaller`` (subprocess mocked, but
filesystem operations are real against ``tmp_path``) backing a real
``PluginInstallManager``, exercising upgrade flows from start to
finish.

What we pin:

  - ``upgrade()`` happy path: old → ``.bak``, new at ``<plugin_id>/``.
  - Version-monotonicity check: refuses downgrade by default;
    ``force_downgrade=True`` overrides.
  - ``upgrade()`` refuses when the new archive's plugin_id doesn't
    match the installed one.
  - ``upgrade()`` refuses when no plugin is installed.
  - On a failed new install, the manager rolls back: ``.bak`` is
    renamed back to ``<plugin_id>/``, no half-state remains.
  - Stale ``.bak`` directories from prior upgrades are GC'd at the
    start of the next upgrade.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from magellon_sdk.archive.manifest import (
    PluginArchiveManifest,
    dump_manifest_yaml,
    uuid7,
)

from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import RuntimeConfig
from services.plugin_installer.uv_installer import UvInstaller


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _stub_runner(returncode: int = 0):
    """All-success subprocess runner unless overridden."""
    calls: list[dict] = []

    def _run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout="", stderr="",
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(broker_url="amqp://x", gpfs_root="/g")


def _build_archive(
    tmp_path: Path,
    *,
    plugin_id: str = "test-plugin",
    version: str = "0.1.0",
    archive_name: Optional[str] = None,
) -> Path:
    """Build a minimal but real .mpn archive at the given version."""
    src = tmp_path / f"src-{plugin_id}-{version}-{archive_name or 'default'}"
    src.mkdir(exist_ok=True)
    files = {
        "pyproject.toml": b'[project]\nname = "x"\nversion = "0.0.1"\n',
        "main.py": b"# noop\n",
    }
    for name, content in files.items():
        (src / name).write_text(content.decode())

    manifest = PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": plugin_id,
        "archive_id": str(uuid7()),
        "name": "T",
        "version": version,
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": [{"method": "uv", "pyproject": "pyproject.toml"}],
        "file_checksums": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        },
    })
    yaml_bytes = dump_manifest_yaml(manifest).encode()

    archive = tmp_path / (archive_name or f"{plugin_id}-{version}.mpn")
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
        for name, content in files.items():
            z.writestr(name, content)
    return archive


def _make_manager(plugins_dir: Path):
    """Real UvInstaller with stubbed subprocess + minimal manager."""
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    return PluginInstallManager(
        [inst],
        host_info_provider=lambda _: HostInfo(python_version="3.12.0"),
    ), inst


# ---------------------------------------------------------------------------
# Happy-path upgrade
# ---------------------------------------------------------------------------

def test_upgrade_replaces_old_with_new_and_creates_bak(tmp_path):
    """Standard upgrade: old version becomes ``.bak``, new version
    occupies the canonical slot, both filesystem states match what
    the operator expects."""
    plugins_dir = tmp_path / "installed"
    mgr, _inst = _make_manager(plugins_dir)

    old = _build_archive(tmp_path, version="0.1.0")
    new = _build_archive(tmp_path, version="0.2.0")

    mgr.install(old, _runtime())
    assert mgr.is_installed("test-plugin")

    result = mgr.upgrade("test-plugin", new, _runtime())

    assert result.success, result.error
    # New version at the canonical slot, .bak preserves the old.
    assert (plugins_dir / "test-plugin").is_dir()
    assert (plugins_dir / "test-plugin.0.1.0.bak").is_dir()


def test_upgrade_new_install_carries_correct_version(tmp_path):
    """The slot must contain the NEW manifest, not a stale copy."""
    plugins_dir = tmp_path / "installed"
    mgr, _inst = _make_manager(plugins_dir)

    mgr.install(_build_archive(tmp_path, version="0.1.0"), _runtime())
    mgr.upgrade(
        "test-plugin",
        _build_archive(tmp_path, version="0.2.0"),
        _runtime(),
    )

    from magellon_sdk.archive.manifest import load_manifest_bytes
    installed = load_manifest_bytes(
        (plugins_dir / "test-plugin" / "manifest.yaml").read_bytes()
    )
    assert installed.version == "0.2.0"


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------

def test_upgrade_refuses_when_plugin_not_installed(tmp_path):
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)

    new = _build_archive(tmp_path, version="0.2.0")
    result = mgr.upgrade("test-plugin", new, _runtime())

    assert not result.success
    assert "not installed" in result.error


def test_upgrade_refuses_plugin_id_mismatch(tmp_path):
    """Operator uploaded the wrong archive — its plugin_id is for a
    different plugin. Must refuse loudly rather than overwrite."""
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)

    mgr.install(_build_archive(tmp_path, plugin_id="alpha", version="0.1.0"), _runtime())

    other = _build_archive(tmp_path, plugin_id="beta", version="0.2.0")
    result = mgr.upgrade("alpha", other, _runtime())

    assert not result.success
    assert "plugin_id" in result.error
    assert (plugins_dir / "alpha").exists()  # untouched


def test_upgrade_refuses_downgrade_by_default(tmp_path):
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)

    mgr.install(_build_archive(tmp_path, version="0.2.0"), _runtime())
    older = _build_archive(tmp_path, version="0.1.0")

    result = mgr.upgrade("test-plugin", older, _runtime())

    assert not result.success
    assert "not newer" in result.error
    assert "force_downgrade" in result.error


def test_upgrade_force_downgrade_allows_older_version(tmp_path):
    """Operators sometimes need to roll back across plugin
    boundaries (e.g. revert a buggy ctffind release). The flag
    exists for exactly that case."""
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)

    mgr.install(_build_archive(tmp_path, version="0.2.0"), _runtime())
    older = _build_archive(tmp_path, version="0.1.0")

    result = mgr.upgrade("test-plugin", older, _runtime(), force_downgrade=True)

    assert result.success, result.error


def test_upgrade_refuses_same_version(tmp_path):
    """0.2.0 → 0.2.0 isn't strictly newer. Refuse so operators
    don't accidentally re-install the same artifact thinking
    something changed."""
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)

    mgr.install(_build_archive(tmp_path, version="0.2.0", archive_name="a.mpn"), _runtime())
    same = _build_archive(tmp_path, version="0.2.0", archive_name="b.mpn")

    result = mgr.upgrade("test-plugin", same, _runtime())

    assert not result.success
    assert "not newer" in result.error


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def test_upgrade_rolls_back_on_new_install_failure(tmp_path):
    """The new version's install fails (uv blew up). The manager
    must restore the old install from .bak so the operator isn't
    left with no plugin at all."""
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    mgr = PluginInstallManager(
        [inst],
        host_info_provider=lambda _: HostInfo(python_version="3.12.0"),
    )

    mgr.install(_build_archive(tmp_path, version="0.1.0"), _runtime())

    # Now make uv fail for the next call.
    inst._run = _stub_runner(returncode=1)
    result = mgr.upgrade(
        "test-plugin",
        _build_archive(tmp_path, version="0.2.0"),
        _runtime(),
    )

    assert not result.success
    assert "rollback" in result.error
    # Old install restored at the canonical slot.
    assert (plugins_dir / "test-plugin").is_dir()
    # No leftover .bak — rollback consumed it by renaming back.
    assert not (plugins_dir / "test-plugin.0.1.0.bak").exists()


# ---------------------------------------------------------------------------
# Backup GC across multiple upgrade cycles
# ---------------------------------------------------------------------------

def test_upgrade_gcs_stale_backups_from_prior_cycles(tmp_path):
    """Two consecutive upgrades — only the most recent .bak should
    remain. Otherwise stale .bak's accumulate (potentially gigabytes
    on disk for plugins with bundled binaries)."""
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)

    mgr.install(_build_archive(tmp_path, version="0.1.0", archive_name="v1.mpn"), _runtime())
    mgr.upgrade("test-plugin",
                _build_archive(tmp_path, version="0.2.0", archive_name="v2.mpn"),
                _runtime())
    mgr.upgrade("test-plugin",
                _build_archive(tmp_path, version="0.3.0", archive_name="v3.mpn"),
                _runtime())

    # Most-recent .bak (the one made during the 0.2.0 → 0.3.0 swap)
    # is preserved; the older one (from 0.1.0 → 0.2.0) was GC'd.
    assert (plugins_dir / "test-plugin.0.2.0.bak").exists()
    assert not (plugins_dir / "test-plugin.0.1.0.bak").exists()


# ---------------------------------------------------------------------------
# Uninstall semantics — sanity checks the upgrade depends on
# ---------------------------------------------------------------------------

def test_uninstall_removes_install_dir_after_install(tmp_path):
    """If upgrade's preserve_as_backup invariant breaks, regular
    uninstall might also break — keep this in the lifecycle suite
    as a top-level sanity."""
    plugins_dir = tmp_path / "installed"
    mgr, _ = _make_manager(plugins_dir)
    mgr.install(_build_archive(tmp_path, version="0.1.0"), _runtime())

    result = mgr.uninstall("test-plugin")

    assert result.success
    assert not (plugins_dir / "test-plugin").exists()
