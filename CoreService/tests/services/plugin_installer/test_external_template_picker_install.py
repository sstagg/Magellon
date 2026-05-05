"""PI-1: end-to-end install of the real external template-picker plugin.

Packs ``../plugins/magellon_template_picker_plugin`` on the fly with
the SDK CLI and runs it through the install pipeline with subprocess
mocked. Catches the class of bug where the manifest format drifts
between what ``magellon-sdk plugin pack`` writes and what
``UvInstaller`` / ``DockerInstaller`` accept — without it, drift
shows up only on a real production install.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from magellon_sdk.archive.manifest import load_manifest_bytes

from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import RuntimeConfig
from services.plugin_installer.uv_installer import UvInstaller


REPO_ROOT = Path(__file__).resolve().parents[3].parent
EXTERNAL_PICKER_SRC = REPO_ROOT / "plugins" / "magellon_template_picker_plugin"


def _pack_external_picker(out_dir: Path) -> Path:
    """Invoke ``magellon-sdk plugin pack`` against the real plugin
    source. Returns the path to the produced ``.mpn``."""
    if not EXTERNAL_PICKER_SRC.is_dir():
        pytest.skip(
            f"external picker source not present at {EXTERNAL_PICKER_SRC} — "
            f"skipping PI-1 install test",
        )
    out_path = out_dir / "template-picker-0.1.0.mpn"
    from magellon_sdk.cli.main import main as cli_main
    import sys
    saved_argv = sys.argv[:]
    sys.argv = [
        "magellon-sdk", "plugin", "pack",
        str(EXTERNAL_PICKER_SRC),
        "--out", str(out_path),
    ]
    try:
        cli_main()
    finally:
        sys.argv = saved_argv
    assert out_path.exists(), f"pack did not produce {out_path}"
    return out_path


def _stub_runner():
    """All-success subprocess runner so the test doesn't shell out
    to uv (which would build a real venv)."""
    calls: list[dict] = []

    def _run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout="", stderr="",
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def test_external_template_picker_packs_with_well_formed_manifest(tmp_path):
    """The external plugin's manifest must round-trip through pack →
    load_manifest_bytes without error. Pinned because manifest schema
    drift would surface here first."""
    archive_path = _pack_external_picker(tmp_path)
    import zipfile

    with zipfile.ZipFile(archive_path) as z:
        with z.open("manifest.yaml") as f:
            manifest = load_manifest_bytes(f.read())
    assert manifest.plugin_id == "template-picker"
    assert manifest.category == "particle_picking"
    methods = {spec.method for spec in manifest.install}
    assert {"uv", "docker"}.issubset(methods)


def test_uv_installer_supports_external_picker(tmp_path):
    """``UvInstaller.supports()`` should accept the external plugin's
    uv install spec on a host that has a uv binary. Pinned so a future
    predicate change can't accidentally reject the canonical example."""
    archive_path = _pack_external_picker(tmp_path)
    import zipfile

    with zipfile.ZipFile(archive_path) as z:
        with z.open("manifest.yaml") as f:
            manifest = load_manifest_bytes(f.read())

    uv_spec = next(s for s in manifest.install if s.method == "uv")
    installer = UvInstaller(plugins_dir=tmp_path / "installed")
    host = HostInfo(
        docker_daemon=True,
        python_version="3.12.0",
        os="linux",
        arch="x86_64",
    )

    rejection_reasons = installer.supports(uv_spec, host)
    assert rejection_reasons == [], f"supports() rejected: {rejection_reasons}"


def test_external_template_picker_uv_install_lays_out_directory(tmp_path):
    """End-to-end install of the real packed external picker through
    ``UvInstaller`` with subprocess stubbed. Verifies:
      - directory layout matches expectations
      - manifest.yaml lands inside the install dir
      - main.py + plugin/ + pyproject.toml are extracted
      - runtime.env is written with deployment values
    """
    archive_path = _pack_external_picker(tmp_path)
    plugins_dir = tmp_path / "installed"

    runner = _stub_runner()
    installer = UvInstaller(
        plugins_dir=plugins_dir,
        subprocess_runner=runner,
        verify_checksums=True,
    )
    manager = PluginInstallManager([installer])

    runtime = RuntimeConfig(
        broker_url="amqp://test:test@localhost:5672/",
        gpfs_root="/gpfs",
    )
    result = manager.install(archive_path, runtime)

    assert result.success, f"install failed: {result.error}\n{result.logs}"
    assert result.plugin_id == "template-picker"
    assert result.install_method == "uv"

    install_dir = plugins_dir / "template-picker"
    assert install_dir.is_dir()
    assert (install_dir / "manifest.yaml").is_file()
    assert (install_dir / "main.py").is_file()
    assert (install_dir / "plugin" / "plugin.py").is_file()
    assert (install_dir / "pyproject.toml").is_file()

    runtime_env = (install_dir / "runtime.env").read_text(encoding="utf-8")
    assert "MAGELLON_BROKER_URL=amqp://test:test@localhost:5672/" in runtime_env
    assert "MAGELLON_GPFS_PATH=/gpfs" in runtime_env
    assert "HOST_GPFS_PATH=/gpfs" in runtime_env
    assert "MAGELLON_HOME_DIR=/gpfs" in runtime_env

    # Subprocess runner saw uv venv + uv sync.
    cmds = [c["cmd"] for c in runner.calls]
    assert any("venv" in cmd for cmd in cmds)
    assert any("sync" in cmd and "--project" in cmd for cmd in cmds)


def test_uninstall_external_template_picker_removes_directory(tmp_path):
    """After install + uninstall, the install dir should be gone — the
    operator-visible round trip works on the real plugin."""
    archive_path = _pack_external_picker(tmp_path)
    plugins_dir = tmp_path / "installed"

    installer = UvInstaller(
        plugins_dir=plugins_dir,
        subprocess_runner=_stub_runner(),
        verify_checksums=True,
    )
    manager = PluginInstallManager([installer])
    runtime = RuntimeConfig(
        broker_url="amqp://test:test@localhost:5672/", gpfs_root="/gpfs",
    )

    install_result = manager.install(archive_path, runtime)
    assert install_result.success
    install_dir = plugins_dir / "template-picker"
    assert install_dir.is_dir()

    uninstall_result = manager.uninstall("template-picker")
    assert uninstall_result.success
    assert not install_dir.exists()
