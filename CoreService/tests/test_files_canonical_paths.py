"""End-to-end tests for the canonical /gpfs path contract on
``/web/files/browse`` and ``/web/files/upload``.

These endpoints must:
  * accept ONLY canonical ``/gpfs/...`` paths from the wire
  * return canonical ``/gpfs/...`` paths in their responses

That keeps the path safe to flow through plugin task DTOs without
needing every caller to know about the host's GPFS root layout.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import webapp_motioncor_controller as ctl
from dependencies.auth import get_current_user_id


@pytest.fixture
def gpfs_root(tmp_path: Path) -> Path:
    root = tmp_path / "gpfs"
    root.mkdir()
    (root / "sessions").mkdir()
    (root / "sessions" / "demo.mrc").write_bytes(b"\x00" * 16)
    return root


@pytest.fixture
def client(gpfs_root: Path):
    app = FastAPI()
    app.include_router(ctl.motioncor_router, prefix="/web")
    user_id = uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    with patch.object(
        ctl.app_settings.directory_settings,
        "MAGELLON_GPFS_PATH",
        str(gpfs_root),
    ):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# /files/browse
# ---------------------------------------------------------------------------


def test_browse_returns_canonical_paths(client, gpfs_root: Path):
    """Items must come back as ``/gpfs/sessions/demo.mrc`` — never the
    host-absolute form. Otherwise a Linux plugin can't open the path."""
    resp = client.get("/web/files/browse", params={"path": "/gpfs/sessions"})
    assert resp.status_code == 200
    items = resp.json()
    paths = [it["path"] for it in items]
    assert "/gpfs/sessions/demo.mrc" in paths
    # Negative: no host-form leakage.
    assert not any(str(gpfs_root) in p for p in paths)
    assert not any(p.startswith(("C:", "/tmp")) for p in paths)


def test_browse_root_returns_canonical_paths(client):
    resp = client.get("/web/files/browse", params={"path": "/gpfs"})
    assert resp.status_code == 200
    items = resp.json()
    sessions = next(it for it in items if it["name"] == "sessions")
    assert sessions["path"] == "/gpfs/sessions"


def test_browse_rejects_non_canonical_path(client, tmp_path: Path):
    """Refuse to browse anything that isn't under the canonical root.
    This is the boundary; without it, the picker can roam C:\\."""
    elsewhere = tmp_path / "outside"
    elsewhere.mkdir()
    resp = client.get("/web/files/browse", params={"path": str(elsewhere)})
    assert resp.status_code == 400
    assert "outside" in resp.json()["detail"].lower() or "canonical" in resp.json()["detail"].lower()


def test_browse_rejects_windows_drive_root(client):
    """Even on Windows direct-run the picker must not show ``C:\\``."""
    resp = client.get("/web/files/browse", params={"path": "C:/"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /files/upload
# ---------------------------------------------------------------------------


def test_upload_response_uses_canonical_path(client, gpfs_root: Path):
    resp = client.post(
        "/web/files/upload",
        data={"path": "/gpfs/sessions"},
        files=[("files", ("uploaded.txt", io.BytesIO(b"x"), "text/plain"))],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["path"] == "/gpfs/sessions/uploaded.txt"
    # Same negatives as browse: no host-absolute leakage.
    assert str(gpfs_root) not in body[0]["path"]
