"""Tests for ``DockerInstaller`` (P5).

Mocks subprocess so we don't actually pull images, build containers,
or shell out to a daemon. What we pin:

  - ``supports()`` rejects non-docker methods + missing both
    image/dockerfile; delegates other failures to predicate eval.
  - ``install()`` image mode: ``docker pull`` then ``docker run`` —
    state recorded with ``image_was_built=False``.
  - ``install()`` dockerfile mode: ``docker build`` then
    ``docker run`` — state recorded with ``image_was_built=True``,
    image tag follows ``magellon-plugin-<id>:<version>`` convention.
  - ``install()`` prefers ``image:`` when both fields are present
    (faster install path).
  - ``docker run`` command shape: container name, network (when
    set), GPFS mount, broker URL + GPFS env, extra env.
  - Rollback on each failure point: pull/build/run failures must
    leave no lingering container, no built image, no install dir.
  - Zip-slip safety.
  - ``uninstall()`` stops + removes container; built images get
    ``docker rmi``; pulled images do NOT (they may be cached/shared).
  - ``uninstall()`` handles missing state file (half-uninstalled
    state) without crashing.
  - ``is_installed()`` requires BOTH the directory AND the state
    marker — half-state isn't reported as installed.
"""
from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path
from typing import Iterable, List
from uuid import uuid4

import pytest

from magellon_sdk.archive.manifest import (
    InstallSpec,
    PluginArchiveManifest,
    dump_manifest_yaml,
    uuid7,
)

from services.plugin_installer.docker_installer import (
    STATE_FILENAME,
    DockerInstaller,
)
from services.plugin_installer.predicates import HostInfo
from services.plugin_installer.protocol import RuntimeConfig


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _runtime() -> RuntimeConfig:
    return RuntimeConfig(
        broker_url="amqp://r:p@host:5672/",
        gpfs_root="/gpfs/test",
        extra_env={"LOG_LEVEL": "INFO"},
    )


def _spec(
    *, image: str | None = None, dockerfile: str | None = None,
    requires: list | None = None,
) -> InstallSpec:
    payload = {"method": "docker", "requires": requires or []}
    if image:
        payload["image"] = image
    if dockerfile:
        payload["dockerfile"] = dockerfile
    return InstallSpec.model_validate(payload)


def _manifest_with_install(install: list[dict]) -> PluginArchiveManifest:
    return PluginArchiveManifest.model_validate({
        "manifest_version": "1",
        "plugin_id": "ctf-plugin",
        "archive_id": str(uuid7()),
        "name": "CTF",
        "version": "1.2.3",
        "requires_sdk": ">=2.0,<3.0",
        "category": "ctf",
        "install": install,
    })


def _build_archive(
    tmp_path: Path,
    install: list[dict],
    *,
    extra_files: dict[str, bytes] | None = None,
) -> tuple[Path, PluginArchiveManifest]:
    manifest = _manifest_with_install(install)
    yaml_bytes = dump_manifest_yaml(manifest).encode()
    archive = tmp_path / "ctf.mpn"
    files = {"Dockerfile": b"FROM python:3.12\n"}
    if extra_files:
        files.update(extra_files)

    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
        for name, content in files.items():
            z.writestr(name, content)
    return archive, manifest


# ---------------------------------------------------------------------------
# Subprocess stubs
# ---------------------------------------------------------------------------

def _stub_runner(returncode: int = 0, stdout: str = "", stderr: str = ""):
    """All-success runner unless a docker subcommand triggers per-call
    overrides via the returned function's mutable state."""
    calls: list[dict] = []

    def _run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=cmd, returncode=returncode, stdout=stdout, stderr=stderr,
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def _failing_subcommand_runner(failing: set[str]):
    """Runner that fails when ``cmd[1]`` (the docker subcommand) is in
    ``failing``. Used to simulate per-step failures (pull fails, build
    fails, run fails)."""
    calls: list[dict] = []

    def _run(cmd, **kwargs):
        calls.append({"cmd": cmd, "kwargs": kwargs})
        rc = 1 if cmd[1] in failing else 0
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=rc,
            stdout="",
            stderr=f"docker {cmd[1]}: simulated failure" if rc else "",
        )

    _run.calls = calls  # type: ignore[attr-defined]
    return _run


def _docker_subcommands(calls: Iterable[dict]) -> List[str]:
    """Helper — extract the ordered list of docker subcommands run."""
    return [c["cmd"][1] for c in calls if len(c["cmd"]) >= 2]


# ---------------------------------------------------------------------------
# supports()
# ---------------------------------------------------------------------------

def test_supports_rejects_non_docker_method(tmp_path):
    inst = DockerInstaller(plugins_dir=tmp_path, subprocess_runner=_stub_runner())
    spec = InstallSpec.model_validate({"method": "uv", "pyproject": "x"})
    failures = inst.supports(spec, HostInfo(docker_daemon=True))
    assert any("method != docker" in f for f in failures)


def test_supports_passes_when_image_set_and_predicates_ok(tmp_path):
    inst = DockerInstaller(plugins_dir=tmp_path, subprocess_runner=_stub_runner())
    failures = inst.supports(
        _spec(image="ghcr.io/x:1", requires=[{"docker_daemon": True}]),
        HostInfo(docker_daemon=True),
    )
    assert failures == []


def test_supports_passes_when_dockerfile_set(tmp_path):
    inst = DockerInstaller(plugins_dir=tmp_path, subprocess_runner=_stub_runner())
    failures = inst.supports(
        _spec(dockerfile="Dockerfile"), HostInfo(docker_daemon=True),
    )
    assert failures == []


def test_supports_returns_predicate_failures(tmp_path):
    """Plugin requires GPU; host has none. The predicate failure
    message must be returned so the manager can explain the
    no-match to the operator."""
    inst = DockerInstaller(plugins_dir=tmp_path, subprocess_runner=_stub_runner())
    failures = inst.supports(
        _spec(image="ghcr.io/x:1", requires=[{"gpu_count_min": 1}]),
        HostInfo(docker_daemon=True, gpu_count=0),
    )
    assert any("gpu_count_min" in f for f in failures)


# ---------------------------------------------------------------------------
# install() — image (pull) mode
# ---------------------------------------------------------------------------

def test_install_image_mode_runs_pull_then_run(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x/y:1.2.3"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert result.success, result.error
    subcommands = _docker_subcommands(runner.calls)
    assert subcommands == ["pull", "run"]


def test_install_image_mode_state_marks_image_was_built_false(tmp_path):
    """Pulled images stay around after uninstall — uninstall must
    NOT rmi them."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x/y:1.2.3"},
    ])
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )

    inst.install(archive, manifest, manifest.install[0], _runtime())

    state = json.loads(
        (tmp_path / "installed" / "ctf-plugin" / STATE_FILENAME).read_text()
    )
    assert state["image_was_built"] is False
    assert state["image_ref"] == "ghcr.io/x/y:1.2.3"


# ---------------------------------------------------------------------------
# install() — dockerfile (build) mode
# ---------------------------------------------------------------------------

def test_install_dockerfile_mode_runs_build_then_run(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert result.success, result.error
    subcommands = _docker_subcommands(runner.calls)
    assert subcommands == ["build", "run"]


def test_install_dockerfile_mode_uses_synthetic_image_tag(tmp_path):
    """Built images get a deterministic local tag namespaced under
    ``magellon-plugin-`` so they can't collide with pulled images
    and uninstall can rmi them confidently."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    build_call = next(c for c in runner.calls if c["cmd"][1] == "build")
    # The -t arg should be magellon-plugin-ctf-plugin:1.2.3
    t_idx = build_call["cmd"].index("-t")
    tag = build_call["cmd"][t_idx + 1]
    assert tag == "magellon-plugin-ctf-plugin:1.2.3"


def test_install_dockerfile_mode_state_marks_image_was_built_true(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )

    inst.install(archive, manifest, manifest.install[0], _runtime())

    state = json.loads(
        (tmp_path / "installed" / "ctf-plugin" / STATE_FILENAME).read_text()
    )
    assert state["image_was_built"] is True


def test_install_prefers_image_over_dockerfile_when_both_set(tmp_path):
    """A plugin author who provides both gets the faster path
    (pull > build). Documented in PLUGIN_ARCHIVE_FORMAT.md §4.1."""
    archive, manifest = _build_archive(tmp_path, [
        {
            "method": "docker",
            "image": "ghcr.io/x/y:1.2.3",
            "dockerfile": "Dockerfile",
        },
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    subcommands = _docker_subcommands(runner.calls)
    assert "build" not in subcommands  # didn't build
    assert subcommands == ["pull", "run"]


# ---------------------------------------------------------------------------
# docker run command shape
# ---------------------------------------------------------------------------

def test_run_includes_container_name(tmp_path):
    """Stable ``magellon-plugin-<plugin_id>`` so ``docker ps --filter
    name=`` always finds it; uninstall doesn't need a separate
    bookkeeping field."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    run_call = next(c for c in runner.calls if c["cmd"][1] == "run")
    name_idx = run_call["cmd"].index("--name")
    assert run_call["cmd"][name_idx + 1] == "magellon-plugin-ctf-plugin"


def test_run_mounts_gpfs_root(tmp_path):
    """``-v <gpfs>:<gpfs>`` so the same absolute path resolves
    inside and outside the container — what makes
    MAGELLON_HOME_DIR portable per DATA_PLANE.md."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    run_call = next(c for c in runner.calls if c["cmd"][1] == "run")
    assert "-v" in run_call["cmd"]
    v_idx = run_call["cmd"].index("-v")
    assert run_call["cmd"][v_idx + 1] == "/gpfs/test:/gpfs/test"


def test_run_passes_broker_url_and_gpfs_env(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    run_call = next(c for c in runner.calls if c["cmd"][1] == "run")
    cmd = run_call["cmd"]
    # Find every '-e VALUE' pair.
    env_args = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-e"]
    assert "MAGELLON_BROKER_URL=amqp://r:p@host:5672/" in env_args
    assert "MAGELLON_HOME_DIR=/gpfs/test" in env_args
    assert "LOG_LEVEL=INFO" in env_args


def test_run_includes_network_when_set(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed",
        network="magellon-net",
        subprocess_runner=runner,
    )

    inst.install(archive, manifest, manifest.install[0], _runtime())

    run_call = next(c for c in runner.calls if c["cmd"][1] == "run")
    assert "--network" in run_call["cmd"]
    n_idx = run_call["cmd"].index("--network")
    assert run_call["cmd"][n_idx + 1] == "magellon-net"


def test_run_omits_network_when_not_set(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)

    inst.install(archive, manifest, manifest.install[0], _runtime())

    run_call = next(c for c in runner.calls if c["cmd"][1] == "run")
    assert "--network" not in run_call["cmd"]


# ---------------------------------------------------------------------------
# install() — error paths and rollback
# ---------------------------------------------------------------------------

def test_install_refuses_already_installed(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    plugins_dir = tmp_path / "installed"
    plugins_dir.mkdir()
    (plugins_dir / "ctf-plugin").mkdir()

    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "already installed" in result.error


def test_install_cleans_up_when_pull_fails(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _failing_subcommand_runner({"pull"})
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=runner,
    )

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "docker pull" in result.error
    # No install dir remaining.
    assert not (tmp_path / "installed" / "ctf-plugin").exists()
    # No `run` was attempted (we stopped after pull failed).
    assert "run" not in _docker_subcommands(runner.calls)


def test_install_cleans_up_when_build_fails(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    runner = _failing_subcommand_runner({"build"})
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=runner,
    )

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "docker build" in result.error
    assert not (tmp_path / "installed" / "ctf-plugin").exists()


def test_install_cleans_up_when_run_fails_after_build(tmp_path):
    """``docker run`` blew up after we built the image — must rmi
    the built image during rollback so a re-attempt isn't blocked
    by a stale image with the same tag, and the disk doesn't bloat."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    runner = _failing_subcommand_runner({"run"})
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=runner,
    )

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    subcommands = _docker_subcommands(runner.calls)
    # Built, ran (failed), tried to clean up the container, then rmi'd
    # the just-built image. ``stop`` + ``rm`` may both fail since the
    # container never started — that's fine, they're swallowed.
    assert subcommands[:2] == ["build", "run"]
    assert "rmi" in subcommands  # built image cleaned up
    assert not (tmp_path / "installed" / "ctf-plugin").exists()


def test_install_cleans_up_when_run_fails_after_pull(tmp_path):
    """Pull mode: if run fails, we do NOT rmi the pulled image (it
    may be cached/shared). Just clean up dir + container attempt."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    runner = _failing_subcommand_runner({"run"})
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=runner,
    )

    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    subcommands = _docker_subcommands(runner.calls)
    assert "rmi" not in subcommands  # pulled image preserved
    assert not (tmp_path / "installed" / "ctf-plugin").exists()


def test_install_refuses_zip_slip(tmp_path):
    manifest = _manifest_with_install([
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    yaml_bytes = dump_manifest_yaml(manifest).encode()
    archive = tmp_path / "evil.mpn"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.yaml", yaml_bytes)
        z.writestr("plugin.yaml", yaml_bytes)
        z.writestr("../escape.txt", b"escaped")

    runner = _stub_runner()
    inst = DockerInstaller(plugins_dir=tmp_path / "installed", subprocess_runner=runner)
    result = inst.install(archive, manifest, manifest.install[0], _runtime())

    assert not result.success
    assert "unsafe archive entry" in result.error
    # Never even attempted docker — bailed at extraction.
    assert _docker_subcommands(runner.calls) == []


# ---------------------------------------------------------------------------
# uninstall()
# ---------------------------------------------------------------------------

def test_uninstall_stops_and_removes_container(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    plugins_dir = tmp_path / "installed"
    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    runner = _stub_runner()
    inst._run = runner
    result = inst.uninstall("ctf-plugin")

    assert result.success
    subcommands = _docker_subcommands(runner.calls)
    assert "stop" in subcommands
    assert "rm" in subcommands
    # Pulled image — no rmi.
    assert "rmi" not in subcommands


def test_uninstall_removes_built_images(tmp_path):
    """Built images are per-plugin and not shared; rmi them to free
    disk. Pulled images are kept (shared/cached use cases)."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    plugins_dir = tmp_path / "installed"
    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    runner = _stub_runner()
    inst._run = runner
    inst.uninstall("ctf-plugin")

    subcommands = _docker_subcommands(runner.calls)
    assert "rmi" in subcommands


def test_uninstall_removes_install_dir(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    plugins_dir = tmp_path / "installed"
    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())
    assert (plugins_dir / "ctf-plugin").exists()

    inst.uninstall("ctf-plugin")

    assert not (plugins_dir / "ctf-plugin").exists()


def test_uninstall_refuses_when_not_installed(tmp_path):
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    result = inst.uninstall("nope")
    assert not result.success
    assert "not installed" in result.error


def test_uninstall_handles_missing_state_file(tmp_path):
    """Half-uninstalled state: directory exists but state file gone
    (operator manually deleted it, or earlier uninstall crashed
    after rm-ing files but before rm-ing the dir). Best-effort:
    remove the directory, report what wasn't cleaned up."""
    plugins_dir = tmp_path / "installed"
    plugins_dir.mkdir()
    (plugins_dir / "ctf-plugin").mkdir()  # dir but no state file

    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    result = inst.uninstall("ctf-plugin")

    assert not result.success
    assert "install_state.json missing" in result.error
    # Directory should still be removed (best-effort cleanup).
    assert not (plugins_dir / "ctf-plugin").exists()


# ---------------------------------------------------------------------------
# is_installed()
# ---------------------------------------------------------------------------

def test_is_installed_true_when_dir_and_state_exist(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    plugins_dir = tmp_path / "installed"
    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    assert inst.is_installed("ctf-plugin")


def test_is_installed_false_when_dir_but_no_state(tmp_path):
    """Directory present but state marker absent → don't pretend
    we own it. Otherwise an operator's hand-created plugins/ subdir
    would block install."""
    plugins_dir = tmp_path / "installed"
    plugins_dir.mkdir()
    (plugins_dir / "ctf-plugin").mkdir()

    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    assert not inst.is_installed("ctf-plugin")


def test_is_installed_false_when_dir_absent(tmp_path):
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    assert not inst.is_installed("anything")


# ---------------------------------------------------------------------------
# uninstall(preserve_as_backup=True) — P6 upgrade rollback surface
# ---------------------------------------------------------------------------

def test_preserve_as_backup_renames_to_versioned_dir(tmp_path):
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    plugins_dir = tmp_path / "installed"
    inst = DockerInstaller(plugins_dir=plugins_dir, subprocess_runner=_stub_runner())
    inst.install(archive, manifest, manifest.install[0], _runtime())

    inst._run = _stub_runner()
    result = inst.uninstall("ctf-plugin", preserve_as_backup=True)

    assert result.success
    assert not (plugins_dir / "ctf-plugin").exists()
    assert (plugins_dir / "ctf-plugin.1.2.3.bak").is_dir()


def test_preserve_as_backup_stops_and_removes_container(tmp_path):
    """Container must still be torn down — backup mode preserves
    on-disk state, NOT a running container. Otherwise the new
    version's container can't be created (name collision)."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    inst.install(archive, manifest, manifest.install[0], _runtime())

    runner = _stub_runner()
    inst._run = runner
    inst.uninstall("ctf-plugin", preserve_as_backup=True)

    subcommands = _docker_subcommands(runner.calls)
    assert "stop" in subcommands
    assert "rm" in subcommands


def test_preserve_as_backup_keeps_built_image(tmp_path):
    """Built images must be preserved during backup so a rollback
    can re-run the same one. Regular uninstall would rmi them; backup
    mode must NOT."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "dockerfile": "Dockerfile"},
    ])
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    inst.install(archive, manifest, manifest.install[0], _runtime())

    runner = _stub_runner()
    inst._run = runner
    inst.uninstall("ctf-plugin", preserve_as_backup=True)

    subcommands = _docker_subcommands(runner.calls)
    assert "rmi" not in subcommands  # built image preserved


def test_preserve_as_backup_keeps_pulled_image(tmp_path):
    """Pulled images aren't rmi'd by regular uninstall either, but
    confirm explicitly that backup mode doesn't accidentally start
    rmi'ing them."""
    archive, manifest = _build_archive(tmp_path, [
        {"method": "docker", "image": "ghcr.io/x:1"},
    ])
    inst = DockerInstaller(
        plugins_dir=tmp_path / "installed", subprocess_runner=_stub_runner(),
    )
    inst.install(archive, manifest, manifest.install[0], _runtime())

    runner = _stub_runner()
    inst._run = runner
    inst.uninstall("ctf-plugin", preserve_as_backup=True)

    subcommands = _docker_subcommands(runner.calls)
    assert "rmi" not in subcommands
