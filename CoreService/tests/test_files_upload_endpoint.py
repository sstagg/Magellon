"""Smoke tests for POST /web/files/upload.

Pins the security boundary (refuse writes outside the configured GPFS
root, refuse traversal, refuse pre-existing files unless overwrite is
asked for) plus the happy path.
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
    (root / "uploads").mkdir()
    return root


@pytest.fixture
def client(gpfs_root: Path):
    app = FastAPI()
    app.include_router(ctl.motioncor_router, prefix="/web")
    user_id = uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: user_id

    # Point the controller's settings at our temp GPFS so upload paths
    # resolve under it.
    with patch.object(
        ctl.app_settings.directory_settings,
        "MAGELLON_GPFS_PATH",
        str(gpfs_root),
    ):
        yield TestClient(app)


def test_upload_writes_one_file_under_gpfs(client, gpfs_root: Path):
    target = "/gpfs/uploads"
    payload = b"hello world\n"
    resp = client.post(
        "/web/files/upload",
        data={"path": target},
        files=[("files", ("greeting.txt", io.BytesIO(payload), "text/plain"))],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "greeting.txt"
    assert body[0]["size"] == len(payload)
    assert body[0]["overwritten"] is False
    on_disk = gpfs_root / "uploads" / "greeting.txt"
    assert on_disk.read_bytes() == payload


def test_upload_writes_multiple_files(client, gpfs_root: Path):
    resp = client.post(
        "/web/files/upload",
        data={"path": "/gpfs/uploads"},
        files=[
            ("files", ("a.txt", io.BytesIO(b"AAA"), "text/plain")),
            ("files", ("b.txt", io.BytesIO(b"BBB"), "text/plain")),
        ],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2
    assert (gpfs_root / "uploads" / "a.txt").read_bytes() == b"AAA"
    assert (gpfs_root / "uploads" / "b.txt").read_bytes() == b"BBB"


def test_upload_rejects_path_outside_gpfs(client, tmp_path: Path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    resp = client.post(
        "/web/files/upload",
        data={"path": str(outside)},
        files=[("files", ("oops.txt", io.BytesIO(b"x"), "text/plain"))],
    )
    assert resp.status_code == 400
    assert "outside" in resp.json()["detail"].lower()


def test_upload_rejects_traversal_in_filename(client, gpfs_root: Path):
    """Multi-file drops on Windows can include ``subdir\\name.mrc``;
    we strip that to the leaf name. A ``../foo`` filename must not
    escape — confirm by uploading a name with ``..`` and checking the
    leaf landed in the target dir, not the parent."""
    resp = client.post(
        "/web/files/upload",
        data={"path": "/gpfs/uploads"},
        files=[("files", ("../escaped.txt", io.BytesIO(b"x"), "text/plain"))],
    )
    assert resp.status_code == 200
    # ../escaped.txt → Path(...).name = "escaped.txt", lands inside target
    assert (gpfs_root / "uploads" / "escaped.txt").exists()
    assert not (gpfs_root / "escaped.txt").exists()


def test_upload_409_on_existing_file_without_overwrite(client, gpfs_root: Path):
    (gpfs_root / "uploads" / "exists.txt").write_text("old")
    resp = client.post(
        "/web/files/upload",
        data={"path": "/gpfs/uploads"},
        files=[("files", ("exists.txt", io.BytesIO(b"new"), "text/plain"))],
    )
    assert resp.status_code == 409
    assert (gpfs_root / "uploads" / "exists.txt").read_text() == "old"


def test_upload_overwrites_when_explicitly_requested(client, gpfs_root: Path):
    (gpfs_root / "uploads" / "exists.txt").write_text("old")
    resp = client.post(
        "/web/files/upload",
        data={"path": "/gpfs/uploads", "overwrite": "true"},
        files=[("files", ("exists.txt", io.BytesIO(b"new"), "text/plain"))],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["overwritten"] is True
    assert (gpfs_root / "uploads" / "exists.txt").read_text() == "new"


def test_upload_404_for_missing_directory(client):
    resp = client.post(
        "/web/files/upload",
        data={"path": "/gpfs/does-not-exist"},
        files=[("files", ("a.txt", io.BytesIO(b"x"), "text/plain"))],
    )
    assert resp.status_code == 404
