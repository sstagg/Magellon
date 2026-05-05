"""Tests for ``UvInstaller`` (P4).

We DO NOT invoke uv for real here — these are unit tests that mock
``subprocess.run`` and verify the uv command shape. Real-uv
integration tests live in ``tests/integration/`` and skip when uv
isn't on PATH.

What we pin:

  - ``supports()`` rejects non-uv method specs and missing pyproject;
    delegates other failures to predicate evaluation.
  - ``install()`` happy path: extract → checksum-verify → venv → deps
    → runtime.env. Each step's command shape and outputs are
    asserted.
  - ``install()`` refuses if already installed (idempotency).
  - ``install()`` cleans up the install dir on failure (no
    half-installed plugins blocking the next attempt).
  - Zip-slip safety: an archive with ``../`` entries is refused.
  - Checksum mismatch refuses install.
  - ``uninstall()`` removes the install dir; refuses gracefully if
    not installed.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from magellon_sdk.archive.manifest import (
    PluginArchiveManifest,
    dump_manifest_yaml,
    uuid7,
)

from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import RuntimeConfig
from services.plugin_installer.uv_installer import UvInstaller


# ---------------------------------------------------------------------------
# Fixture helpers — build a tiny .mpn in tmp_path
# ---------------------------------------------------------------------------

def _make_manifest(plugin_id: str = "test-plugin") -> PluginArchiveManifest:
    return PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": plugin_id,
        "archive_id": str(uuid7()),
        "name": "Test Plugin",
        "version": "0.1.0",
        "requires_sdk": ">=2.0,<3.0",
        "category": "fft",
        "install": [
            {
                "method": "uv",
                "pyproject": "pyproject.toml",
                "requires": [{"python": ">=3.11"}],
            },
        ],
    })


def _build_archive(
    tmp_path: Path,
    plugin_id: str = "test-plugin",
    extra_files: dict[str, bytes] | None = None,
    skip_pyproject: bool = False,
) -> tuple[Path, PluginArchiveManifest]:
    """Build a tiny .mpn under tmp_path and return (archive_path, manifest)."""
    files: dict[str, bytes] = {
        "pyproject.toml": b'[project]\nname = "test-plugin"\nversion = "0.1.0"\n',
        "main.py": b"# noop\n",
    }
    if skip_pyproject:
        del files["pyproject.toml"]
    if extra_files:
        files.update(extra_files)

    manifest = _make_manifest(plugin_id)
    # Compute checksums for the model.
    file_checksums = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in files.items()
    }
    payload = manifest.model_dump(mode="python")
    payload["file_checksums"] = file_checksums
    manifest = PluginArchiveManifest.model_validate(payload)
    manifest_yaml = dump_manifest_yaml(manifest).encode("utf-8")

    archive = tmp_path / f"{plugin_id}.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", manifest_yaml)
        z.writestr("plugin.yaml", manifest_yaml)
        for name, content in files.items():
            z.writestr(name, content)
    return archive, manifest


def _stub_runner(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Return a callable that mimics subprocess.run + records calls."""
    calls: list[dict] = []

    def _run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode,
            stdout=stdout, stderr=stderr,
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(
        broker_url="amqp://test:test@broker:5672/",
        gpfs_root="/gpfs/test",
        extra_env={"LOG_LEVEL": "DEBUG"},
    )


# ---------------------------------------------------------------------------
# supports()
# ---------------------------------------------------------------------------

def test_supports_rejects_non_uv_method():
    inst = UvInstaller(plugins_dir=Path("/tmp/x"))
    spec = _make_manifest().install[0]
    spec_docker = type(spec).model_validate({
        "method": "docker",
        "image": "x:1",
    })
    failures = inst.supports(spec_docker, HostInfo(python_version="3.12.0"))
    assert any("method != uv" in f for f in failures)


def test_supports_passes_when_predicates_satisfied():
    inst = UvInstaller(plugins_dir=Path("/tmp/x"))
    spec = _make_manifest().install[0]
    failures = inst.supports(spec, HostInfo(python_version="3.12.0"))
    assert failures == []


def test_supports_returns_predicate_failures():
    inst = UvInstaller(plugins_dir=Path("/tmp/x"))
    spec = _make_manifest().install[0]
    failures = inst.supports(spec, HostInfo(python_version="3.10.0"))
    assert len(failures) == 1
    assert "3.10" in failures[0]


# ---------------------------------------------------------------------------
# install() — happy path
# ---------------------------------------------------------------------------

def test_install_extracts_archive_to_plugin_dir(tmp_path):
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(
        plugins_dir=plugins_dir,
        subprocess_runner=_stub_runner(),
    )

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert result.success, result.error
    assert (plugins_dir / "test-plugin" / "pyproject.toml").exists()
    assert (plugins_dir / "test-plugin" / "main.py").exists()


def test_install_runs_uv_venv_command(tmp_path):
    archive, manifest = _build_archive(tmp_path)
    runner = _stub_runner()
    inst = UvInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    venv_calls = [c for c in runner.calls if "venv" in c["cmd"]]
    assert len(venv_calls) == 1
    cmd = venv_calls[0]["cmd"]
    assert cmd[0] == "uv"
    assert cmd[1] == "venv"
    assert "test-plugin" in cmd[2]
    assert ".venv" in cmd[2]


def test_install_runs_uv_sync_for_pyproject(tmp_path):
    """Plugin has pyproject.toml, so uv sync resolves it into the venv."""
    archive, manifest = _build_archive(tmp_path)
    runner = _stub_runner()
    inst = UvInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    install_calls = [c for c in runner.calls if "sync" in c["cmd"]]
    assert len(install_calls) == 1
    cmd = install_calls[0]["cmd"]
    assert cmd[:3] == ["uv", "sync", "--project"]
    assert cmd[-1] == "--no-dev"


def test_install_sets_project_environment_for_uv_sync(tmp_path):
    """``UV_PROJECT_ENVIRONMENT`` must point uv sync at the plugin venv."""
    archive, manifest = _build_archive(tmp_path)
    runner = _stub_runner()
    inst = UvInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    install_calls = [c for c in runner.calls if "sync" in c["cmd"]]
    env = install_calls[0]["kwargs"]["env"]
    assert "VIRTUAL_ENV" in env
    assert "UV_PROJECT_ENVIRONMENT" in env
    assert "test-plugin" in env["VIRTUAL_ENV"]
    assert ".venv" in env["VIRTUAL_ENV"]
    assert "test-plugin" in env["UV_PROJECT_ENVIRONMENT"]
    assert ".venv" in env["UV_PROJECT_ENVIRONMENT"]


def test_ensure_sdk_path_helpers_copies_missing_module(tmp_path):
    """Older bundled SDK wheels may miss magellon_sdk.paths."""
    venv_dir = tmp_path / ".venv"
    sdk_dir = venv_dir / "Lib" / "site-packages" / "magellon_sdk"
    sdk_dir.mkdir(parents=True)
    (sdk_dir / "__init__.py").write_text("# installed sdk\n", encoding="utf-8")
    logs: list[str] = []
    inst = UvInstaller(plugins_dir=tmp_path / "installed")

    inst._ensure_sdk_path_helpers(venv_dir, logs)

    patched = sdk_dir / "paths.py"
    assert patched.exists()
    assert "from_canonical_gpfs_path" in patched.read_text(encoding="utf-8")
    assert "patched magellon_sdk.paths compatibility helper" in logs


def test_patch_legacy_fft_output_resolution(tmp_path):
    compute_py = tmp_path / "fft" / "plugin" / "compute.py"
    compute_py.parent.mkdir(parents=True)
    compute_py.write_text(
        dedent(
            """
            def compute_file_fft(image_path, abs_out_file_name, height=1024):
                mic = _load_image_array(image_path).astype(float)
                return abs_out_file_name
            """
        ).lstrip(),
        encoding="utf-8",
    )
    logs: list[str] = []
    inst = UvInstaller(plugins_dir=tmp_path / "installed")

    inst._patch_legacy_fft_output_resolution(tmp_path / "fft", logs)

    patched = compute_py.read_text(encoding="utf-8")
    assert "abs_out_file_name = _resolve_local_path(abs_out_file_name)" in patched
    assert "patched legacy FFT output path resolution" in logs


def test_install_writes_runtime_env_with_deployment_values(tmp_path, monkeypatch):
    archive, manifest = _build_archive(tmp_path)
    # Bypass real port-bind probe so the test runs without a network.
    monkeypatch.setattr(
        "services.plugin_installer.port_allocator._is_port_free",
        lambda port: True,
    )
    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )

    inst.install(archive, manifest, manifest.install[0], _runtime())

    runtime_env = (tmp_path / "installed" / "test-plugin" / "runtime.env").read_text()
    assert "MAGELLON_BROKER_URL=amqp://test:test@broker:5672/" in runtime_env
    assert "MAGELLON_GPFS_PATH=/gpfs/test" in runtime_env
    assert "HOST_GPFS_PATH=/gpfs/test" in runtime_env
    assert "MAGELLON_HOME_DIR=/gpfs/test" in runtime_env
    assert "LOG_LEVEL=DEBUG" in runtime_env
    # R2 #4: runtime.env carries the allocated http endpoint so the
    # plugin process announces a reachable URL.
    assert "MAGELLON_PLUGIN_HTTP_ENDPOINT=http://127.0.0.1:" in runtime_env
    assert "MAGELLON_PLUGIN_HOST=127.0.0.1" in runtime_env
    assert "MAGELLON_PLUGIN_PORT=" in runtime_env


def test_install_falls_back_to_requirements_txt_when_no_pyproject(tmp_path):
    """Pre-v1 plugins (and very minimal plugins) only have
    requirements.txt. uv install should still work."""
    archive, manifest = _build_archive(
        tmp_path,
        skip_pyproject=True,
        extra_files={"requirements.txt": b"# none\n"},
    )
    runner = _stub_runner()
    inst = UvInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert result.success, result.error
    install_calls = [
        c for c in runner.calls if "pip" in c["cmd"] and "install" in c["cmd"]
    ]
    cmd = install_calls[0]["cmd"]
    assert "-r" in cmd
    assert any("requirements.txt" in arg for arg in cmd)


# ---------------------------------------------------------------------------
# install() — error paths
# ---------------------------------------------------------------------------

def test_install_refuses_already_installed(tmp_path):
    """Idempotency. The upgrade flow (P6) is the only legal way to
    replace a live install — install must NOT silently overwrite."""
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    plugins_dir.mkdir()
    (plugins_dir / "test-plugin").mkdir()

    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "already installed" in result.error


def test_install_cleans_up_on_uv_venv_failure(tmp_path):
    """A failed install must NOT leave a half-extracted directory
    behind — the next install attempt would refuse with "already
    installed" and the operator would have no path forward."""
    archive, manifest = _build_archive(tmp_path)
    runner = _stub_runner(returncode=1, stderr="uv venv blew up")
    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=runner,
    )

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "uv venv" in result.error
    assert not (tmp_path / "installed" / "test-plugin").exists()


def test_install_cleans_up_on_uv_pip_install_failure(tmp_path):
    """uv venv succeeds, uv pip install fails — same cleanup."""
    archive, manifest = _build_archive(tmp_path)

    call_count = [0]
    def _runner(cmd, **kwargs):
        call_count[0] += 1
        rc = 0 if call_count[0] == 1 else 1  # second call fails
        return subprocess.CompletedProcess(
            args=cmd, returncode=rc, stdout="", stderr="dep resolution failed",
        )

    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_runner,
    )
    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "uv pip install" in result.error
    assert not (tmp_path / "installed" / "test-plugin").exists()


def test_install_refuses_zip_slip(tmp_path):
    """An archive with a ``../`` entry could escape the plugins
    directory and clobber arbitrary files. The installer must
    refuse before extracting."""
    archive_path = tmp_path / "evil.mpn"
    manifest = _make_manifest()
    manifest_yaml = dump_manifest_yaml(manifest).encode()

    with zipfile.ZipFile(archive_path, "w") as z:
        z.writestr("manifest.yaml", manifest_yaml)
        z.writestr("plugin.yaml", manifest_yaml)
        z.writestr("../escape.txt", b"escaped")

    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    result = inst.install(archive_path, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "unsafe archive entry" in result.error
    assert not (tmp_path / "escape.txt").exists()
    assert not (tmp_path / "installed" / "test-plugin").exists()


def test_install_refuses_checksum_mismatch(tmp_path):
    """A tampered file inside the archive — the manifest's
    file_checksums claims one hash but the actual content has
    another. The installer must refuse before letting uv touch it."""
    archive, _manifest = _build_archive(tmp_path)

    # Re-pack the archive replacing main.py's bytes with junk while
    # leaving the manifest's claimed checksum untouched.
    tampered = tmp_path / "tampered.mpn"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "main.py":
                data = b"# tampered\n"
            dst.writestr(item, data)

    # Re-load the manifest from the (now-stale-checksum) archive.
    with zipfile.ZipFile(tampered) as z:
        from magellon_sdk.archive.manifest import load_manifest_bytes
        manifest = load_manifest_bytes(z.read("manifest.yaml"))

    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    result = inst.install(tampered, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "checksum mismatch" in result.error
    assert not (tmp_path / "installed" / "test-plugin").exists()


def test_install_skips_checksum_verification_when_disabled(tmp_path):
    """Operators may legitimately disable verification (debugging a
    pack regression). The install completes; the integrity guarantee
    is opt-out, not silently bypassed."""
    archive, _manifest = _build_archive(tmp_path)

    # Tamper main.py.
    tampered = tmp_path / "tampered.mpn"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "main.py":
                data = b"# tampered\n"
            dst.writestr(item, data)
    with zipfile.ZipFile(tampered) as z:
        from magellon_sdk.archive.manifest import load_manifest_bytes
        manifest = load_manifest_bytes(z.read("manifest.yaml"))

    inst = UvInstaller(
        plugins_dir=tmp_path / "installed",
        subprocess_runner=_stub_runner(),
        verify_checksums=False,
    )
    result = inst.install(tampered, manifest, manifest.install[0], _runtime())

    assert result.success


# ---------------------------------------------------------------------------
# uninstall() / is_installed() / venv_python()
# ---------------------------------------------------------------------------

def test_uninstall_removes_plugin_dir(tmp_path):
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())
    assert inst.is_installed("test-plugin")

    result = inst.uninstall("test-plugin")

    assert result.success
    assert not inst.is_installed("test-plugin")
    assert not (plugins_dir / "test-plugin").exists()


def test_uninstall_refuses_when_not_installed(tmp_path):
    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    result = inst.uninstall("nope")
    assert not result.success
    assert "not installed" in result.error


def test_is_installed_false_when_dir_absent(tmp_path):
    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    assert not inst.is_installed("anything")


def test_venv_python_returns_path_after_install(tmp_path):
    """The manager / launcher will spawn the plugin via this Python
    binary. Returning ``None`` for un-installed plugins keeps the
    spawn path from accidentally using the host interpreter."""
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    venv_python = inst.venv_python("test-plugin")
    assert venv_python is not None
    assert "test-plugin" in str(venv_python)
    assert ".venv" in str(venv_python)
    if sys.platform == "win32":
        assert venv_python.name == "python.exe"
    else:
        assert venv_python.name == "python"


def test_venv_python_returns_none_when_not_installed(tmp_path):
    inst = UvInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    assert inst.venv_python("nothing") is None


# ---------------------------------------------------------------------------
# uninstall(preserve_as_backup=True) — P6 upgrade rollback surface
# ---------------------------------------------------------------------------

def test_preserve_as_backup_renames_to_versioned_dir(tmp_path):
    """The upgrade flow needs the old install preserved so a failed
    new-version install can be rolled back. Backup mode renames the
    install dir to ``<plugin_id>.<version>.bak/`` instead of deleting."""
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    result = inst.uninstall("test-plugin", preserve_as_backup=True)

    assert result.success
    # Original gone, .bak in its place.
    assert not (plugins_dir / "test-plugin").exists()
    assert (plugins_dir / "test-plugin.0.1.0.bak").is_dir()


def test_preserve_as_backup_reads_version_from_installed_manifest(tmp_path):
    """The .bak name carries the version so multiple upgrade cycles
    don't collide. We get that version by reading the installed
    plugin's manifest.yaml — NOT from in-memory state, because state
    might be stale."""
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    inst.uninstall("test-plugin", preserve_as_backup=True)

    # The .bak content matches what was installed.
    saved_manifest = (plugins_dir / "test-plugin.0.1.0.bak" / "manifest.yaml").read_text()
    assert "test-plugin" in saved_manifest


def test_preserve_as_backup_overwrites_pre_existing_backup(tmp_path):
    """Two upgrades back-to-back of the same version (rare, but
    possible if upgrade is retried). The new .bak must replace the
    old one — accumulating duplicates would be operator-confusing."""
    archive, manifest = _build_archive(tmp_path)
    plugins_dir = tmp_path / "installed"
    inst = UvInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())
    # Pre-existing stale .bak that this uninstall must replace.
    stale_bak = plugins_dir / "test-plugin.0.1.0.bak"
    stale_bak.mkdir()
    (stale_bak / "stale.txt").write_text("old leftover")

    inst.uninstall("test-plugin", preserve_as_backup=True)

    bak = plugins_dir / "test-plugin.0.1.0.bak"
    assert bak.is_dir()
    assert not (bak / "stale.txt").exists()  # old contents replaced
