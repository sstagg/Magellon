"""Tests for the Slurm executor scaffolding (Wave 6 Phase 26).

The point of these tests isn't to validate behaviour — none is
implemented yet — it's to pin the *abstraction* extension: a third
install method fits the existing Protocol shape without changing the
manager's dispatch logic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from services.plugin_installer.lifecycle import (
    LifecycleStatus,
    NotSupportedError,
    SlurmLifecycle,
)
from services.plugin_installer.slurm_installer import SlurmInstaller
from services.plugin_installer.protocol import Installer


def test_slurm_installer_satisfies_installer_protocol(tmp_path):
    """Structural check: SlurmInstaller has the right method signatures
    so the manager can use it interchangeably with UvInstaller /
    DockerInstaller. The implementations raise NotImplementedError but
    the *shape* of the Protocol is honored."""
    inst = SlurmInstaller(plugins_dir=tmp_path)
    assert isinstance(inst, Installer)
    assert inst.method == "slurm"


def test_slurm_installer_supports_returns_method_mismatch(tmp_path):
    """supports() must reject non-slurm specs without raising."""
    from magellon_sdk.archive.manifest import InstallSpec
    from services.plugin_installer.predicates import HostInfo

    spec = InstallSpec.model_validate({"method": "docker", "image": "img:1"})
    host = HostInfo(
        docker_daemon=True, binaries_on_path=[],
        python_version="3.12.0", os="linux", arch="x86_64",
    )
    inst = SlurmInstaller(plugins_dir=tmp_path)
    failures = inst.supports(spec, host)
    assert failures == ["method != slurm (got 'docker')"]


def test_slurm_installer_install_is_not_implemented(tmp_path):
    """The scaffolding fence — calling install() with the intent of
    using Slurm should fail loudly with a message pointing at the
    design choice the implementor needs to make."""
    from magellon_sdk.archive.manifest import InstallSpec
    from services.plugin_installer.protocol import RuntimeConfig

    inst = SlurmInstaller(plugins_dir=tmp_path)
    spec = InstallSpec.model_validate({"method": "slurm"})
    with pytest.raises(NotImplementedError, match="scaffolding"):
        inst.install(tmp_path / "fake.mpn", None, spec, RuntimeConfig(
            broker_url="x", gpfs_root="/g",
        ))


def test_slurm_installer_is_installed_returns_false(tmp_path):
    """Until install is wired, is_installed must return False so the
    manager's duplicate-check doesn't 500 when probed."""
    inst = SlurmInstaller(plugins_dir=tmp_path)
    assert inst.is_installed("any-plugin-id") is False


# ---------------------------------------------------------------------------
# SlurmLifecycle
# ---------------------------------------------------------------------------


def test_slurm_lifecycle_method_and_pause_capability(tmp_path):
    """Slurm has no freezing primitive, so supports_pause must be
    False. The React UI greys out the Pause button on the strength of
    this flag alone."""
    lc = SlurmLifecycle(plugins_dir=tmp_path)
    assert lc.method == "slurm"
    assert lc.supports_pause is False


def test_slurm_lifecycle_pause_raises_not_supported(tmp_path):
    """Pause MUST raise NotSupportedError (not NotImplementedError) so
    the admin controller maps it to 409 with the actionable message,
    matching the uv path."""
    lc = SlurmLifecycle(plugins_dir=tmp_path)
    with pytest.raises(NotSupportedError, match="Slurm"):
        lc.pause("any-plugin")


def test_slurm_lifecycle_unpause_raises_not_supported(tmp_path):
    lc = SlurmLifecycle(plugins_dir=tmp_path)
    with pytest.raises(NotSupportedError):
        lc.unpause("any-plugin")


def test_slurm_lifecycle_start_stop_restart_are_not_implemented(tmp_path):
    lc = SlurmLifecycle(plugins_dir=tmp_path)
    for verb in ("start", "stop", "restart"):
        with pytest.raises(NotImplementedError, match="scaffolding"):
            getattr(lc, verb)("any-plugin")


def test_slurm_lifecycle_status_unknown_until_wired(tmp_path):
    """status() returns UNKNOWN as the scaffolding default — same
    fall-back the NoOp supervisor uses."""
    lc = SlurmLifecycle(plugins_dir=tmp_path)
    assert lc.status("any-plugin") == LifecycleStatus.UNKNOWN


def test_slurm_lifecycle_logs_empty_until_wired(tmp_path):
    lc = SlurmLifecycle(plugins_dir=tmp_path)
    assert lc.logs("any-plugin", tail=100) == ""


# ---------------------------------------------------------------------------
# Manifest schema accepts ``method: slurm``
# ---------------------------------------------------------------------------


def test_manifest_accepts_slurm_install_method():
    """v1.1 (Wave 6 Phase 26) adds 'slurm' to the known install
    methods. A manifest declaring it must validate without error."""
    from magellon_sdk.archive.manifest import PluginArchiveManifest

    m = PluginArchiveManifest.model_validate({
        "manifest_version": "1.1",
        "plugin_id": "p",
        "name": "P",
        "version": "1.0.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": [{"method": "slurm"}],
    })
    assert m.install[0].method == "slurm"
