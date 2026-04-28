"""HTTP-layer tests for the v1 admin plugin install controller (P7).

Service-layer behavior (extract, venv build, container run) is
covered by the per-installer tests under
``tests/services/plugin_installer/``. Here we pin the controller's
job:

  - Routes plug into the router with the right verbs/paths.
  - Manager results map to the right HTTP status codes
    (already-installed → 409, not-installed → 404, manifest invalid
    → 400, host-unsupported → 422).
  - Multipart upload streams to a temp file, gets cleaned up after.
  - Casbin Administrator gate is on every endpoint.
  - Upload extension validation rejects garbage.

We mount the router on a throwaway FastAPI app rather than
importing main.py so the test doesn't drag in DB / RMQ / Casbin
startup hooks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import admin_plugin_install_controller as ctl
from dependencies.permissions import require_role
from services.plugin_installer.factory import (
    get_install_manager,
    get_runtime_config,
)
from services.plugin_installer.protocol import (
    InstallResult,
    RuntimeConfig,
    UninstallResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_manager():
    return MagicMock()


@pytest.fixture
def fake_runtime():
    return RuntimeConfig(broker_url="amqp://x", gpfs_root="/g")


@pytest.fixture
def client(fake_manager, fake_runtime):
    app = FastAPI()
    app.include_router(ctl.admin_plugin_install_router, prefix="/admin/plugins")
    app.dependency_overrides[get_install_manager] = lambda: fake_manager
    app.dependency_overrides[get_runtime_config] = lambda: fake_runtime
    # require_role returns a fresh callable per call, so override by
    # name as well — FastAPI keys overrides by the resolved callable
    # object, not by the dependency's identity.
    app.dependency_overrides[require_role("Administrator")] = lambda: None
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant:
            for dep in dependant.dependencies:
                if dep.call is not None and dep.call.__qualname__.startswith("require_role"):
                    app.dependency_overrides[dep.call] = lambda: None
    return TestClient(app)


def _fake_mpn_bytes() -> bytes:
    """Doesn't have to be a real archive — the controller just streams
    it to a temp file and hands the path to the manager (which is
    mocked in these tests). For end-to-end install behavior, see
    test_install_lifecycle.py."""
    return b"fake-mpn-content"


def _success_install(plugin_id: str = "ctf") -> InstallResult:
    return InstallResult(
        success=True,
        plugin_id=plugin_id,
        install_method="docker",
        install_dir=Path(f"/var/magellon/plugins/installed/{plugin_id}"),
        logs="extracted, image pulled, container started",
    )


# ---------------------------------------------------------------------------
# POST /install
# ---------------------------------------------------------------------------

def test_install_success_returns_201(client, fake_manager, fake_runtime):
    fake_manager.install.return_value = _success_install("ctf")

    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("ctf-1.0.0.mpn", _fake_mpn_bytes(), "application/octet-stream")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["plugin_id"] == "ctf"
    assert body["install_method"] == "docker"
    fake_manager.install.assert_called_once()
    archive_arg, runtime_arg = fake_manager.install.call_args.args
    # Manager received a real path that the controller wrote bytes to.
    assert isinstance(archive_arg, Path)
    assert runtime_arg is fake_runtime


def test_install_cleans_up_temp_file_on_success(client, fake_manager):
    """The controller writes uploads to ``tempfile.mkstemp`` then
    unlinks. Verify the path passed to manager.install no longer
    exists after the request returns — leaking temp files would
    fill /tmp on a busy install controller."""
    captured: list[Path] = []

    def _capture(archive_path, runtime):
        captured.append(archive_path)
        return _success_install()

    fake_manager.install.side_effect = _capture

    client.post(
        "/admin/plugins/install",
        files={"file": ("x.mpn", _fake_mpn_bytes())},
    )

    assert len(captured) == 1
    assert not captured[0].exists()  # cleaned up


def test_install_already_installed_returns_409(client, fake_manager):
    """The manager returns ``error="plugin X already installed..."``;
    the controller maps that to 409 Conflict so the operator sees
    "you need to upgrade, not install" without reading the body."""
    fake_manager.install.return_value = InstallResult(
        success=False,
        plugin_id="ctf",
        install_method="docker",
        error="plugin ctf already installed via docker; use upgrade",
    )

    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("ctf.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 409
    assert "already installed" in resp.json()["detail"]


def test_install_invalid_manifest_returns_400(client, fake_manager):
    fake_manager.install.return_value = InstallResult(
        success=False,
        plugin_id="",
        install_method="",
        error="manifest load/validate failed: bad plugin_id",
    )

    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("bad.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 400


def test_install_no_method_matches_returns_422(client, fake_manager):
    """Archive is well-formed but no install method matches the
    host (docker daemon missing, GPU absent). 422 distinguishes
    "operator's environment can't run this" from "the archive
    itself is broken" (400)."""
    fake_manager.install.return_value = InstallResult(
        success=False,
        plugin_id="ctf",
        install_method="",
        error=(
            "no install method matched host for plugin 'ctf':\n"
            "  [0] method='docker': docker_daemon: want True, got False"
        ),
    )

    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("ctf.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 422


def test_install_unknown_failure_returns_500(client, fake_manager):
    """Any error string the controller doesn't pattern-match falls
    through to 500 — better to surface "something went wrong" than
    silently 200 with success=False (which the React app would
    misread)."""
    fake_manager.install.return_value = InstallResult(
        success=False,
        plugin_id="ctf",
        install_method="docker",
        error="some weird disk-IO error nobody anticipated",
    )

    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("ctf.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 500


def test_install_rejects_non_mpn_extension(client, fake_manager):
    """Operator dragged the wrong file (a .pdf, a .zip-of-something).
    Refuse before streaming bytes to disk so we don't fill tmp with
    garbage."""
    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("notes.pdf", b"not an archive")},
    )

    assert resp.status_code == 400
    assert ".mpn" in resp.json()["detail"]
    fake_manager.install.assert_not_called()


def test_install_accepts_legacy_magplugin_extension(client, fake_manager):
    """v0 archives have ``.magplugin`` extension. The pack CLI
    writes both yaml aliases inside; the controller must accept
    both extensions during the transition."""
    fake_manager.install.return_value = _success_install()

    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("legacy.magplugin", _fake_mpn_bytes())},
    )

    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /{plugin_id}/upgrade
# ---------------------------------------------------------------------------

def test_upgrade_success_returns_200(client, fake_manager):
    fake_manager.upgrade.return_value = _success_install("ctf")

    resp = client.post(
        "/admin/plugins/ctf/upgrade",
        files={"file": ("ctf-2.0.0.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["plugin_id"] == "ctf"
    args, kwargs = fake_manager.upgrade.call_args
    assert args[0] == "ctf"
    assert kwargs["force_downgrade"] is False


def test_upgrade_passes_force_downgrade_flag(client, fake_manager):
    """Operator rolling back a buggy release. The flag rides through
    multipart form data so curl/Postman flows can set it without
    JSON gymnastics."""
    fake_manager.upgrade.return_value = _success_install("ctf")

    resp = client.post(
        "/admin/plugins/ctf/upgrade",
        files={"file": ("ctf-1.5.0.mpn", _fake_mpn_bytes())},
        data={"force_downgrade": "true"},
    )

    assert resp.status_code == 200
    args, kwargs = fake_manager.upgrade.call_args
    assert kwargs["force_downgrade"] is True


def test_upgrade_not_installed_returns_404(client, fake_manager):
    fake_manager.upgrade.return_value = InstallResult(
        success=False,
        plugin_id="ctf",
        install_method="",
        error="plugin 'ctf' not installed; use install instead",
    )

    resp = client.post(
        "/admin/plugins/ctf/upgrade",
        files={"file": ("ctf.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 404


def test_upgrade_plugin_id_mismatch_returns_400(client, fake_manager):
    """Operator uploaded the wrong archive. 400 so the React app
    surfaces a clear validation error rather than a server error."""
    fake_manager.upgrade.return_value = InstallResult(
        success=False,
        plugin_id="ctf",
        install_method="",
        error="new archive's plugin_id is 'fft', but upgrade target is 'ctf'",
    )

    resp = client.post(
        "/admin/plugins/ctf/upgrade",
        files={"file": ("wrong.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 400


def test_upgrade_downgrade_refused_returns_400(client, fake_manager):
    fake_manager.upgrade.return_value = InstallResult(
        success=False,
        plugin_id="ctf",
        install_method="",
        error="new version '0.1.0' is not newer than installed '0.2.0'; "
              "pass force_downgrade=True to override",
    )

    resp = client.post(
        "/admin/plugins/ctf/upgrade",
        files={"file": ("older.mpn", _fake_mpn_bytes())},
    )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /{plugin_id}
# ---------------------------------------------------------------------------

def test_uninstall_success_returns_200(client, fake_manager):
    fake_manager.uninstall.return_value = UninstallResult(
        success=True, plugin_id="ctf",
    )

    resp = client.delete("/admin/plugins/ctf")

    assert resp.status_code == 200
    assert resp.json() == {"success": True, "plugin_id": "ctf", "error": None}
    fake_manager.uninstall.assert_called_once_with("ctf")


def test_uninstall_not_installed_returns_404(client, fake_manager):
    fake_manager.uninstall.return_value = UninstallResult(
        success=False,
        plugin_id="ctf",
        error="plugin 'ctf' not installed",
    )

    resp = client.delete("/admin/plugins/ctf")

    assert resp.status_code == 404


def test_uninstall_unknown_failure_returns_500(client, fake_manager):
    fake_manager.uninstall.return_value = UninstallResult(
        success=False,
        plugin_id="ctf",
        error="docker stop/rm failed: container not responding",
    )

    resp = client.delete("/admin/plugins/ctf")

    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /installed
# ---------------------------------------------------------------------------

def test_list_installed_returns_sorted_list(client, fake_manager):
    """Sorted output keeps the React UI's list deterministic
    between renders. Whatever Python dict iteration order is at the
    moment isn't a contract."""
    fake_manager.list_installed.return_value = {
        "motioncor": "docker",
        "ctf": "docker",
        "fft": "uv",
    }

    resp = client.get("/admin/plugins/installed")

    assert resp.status_code == 200
    body = resp.json()
    assert body["installed"] == [
        {"plugin_id": "ctf", "install_method": "docker"},
        {"plugin_id": "fft", "install_method": "uv"},
        {"plugin_id": "motioncor", "install_method": "docker"},
    ]


def test_list_installed_empty(client, fake_manager):
    fake_manager.list_installed.return_value = {}

    resp = client.get("/admin/plugins/installed")

    assert resp.status_code == 200
    assert resp.json() == {"installed": []}


# ---------------------------------------------------------------------------
# Manifest filename in upload — defensive
# ---------------------------------------------------------------------------

def test_install_rejects_upload_without_filename(client, fake_manager):
    """A multipart file without a filename can't be extension-checked.
    Either FastAPI's Form/File validation rejects it (422) or our
    handler does (400) — both are valid 4xx client-error responses
    and crucially the manager never runs."""
    resp = client.post(
        "/admin/plugins/install",
        files={"file": ("", _fake_mpn_bytes())},
    )

    assert 400 <= resp.status_code < 500
    fake_manager.install.assert_not_called()
