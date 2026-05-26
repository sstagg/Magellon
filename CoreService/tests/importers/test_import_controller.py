from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException

from controllers.import_controller import import_directory, validate_directory
from models.pydantic_models import MagellonImportJobDto


def test_validate_magellon_directory_requires_gains_folder(monkeypatch):
    source_dir = r"C:\data\24dec03a"

    def fake_exists(path):
        normalized = str(path).replace("\\", "/")
        existing = {
            "C:/data/24dec03a",
            "C:/data/24dec03a/session.json",
            "C:/data/24dec03a/home/original",
            "C:/data/24dec03a/home/frames",
        }
        return normalized in existing

    monkeypatch.setattr("controllers.import_controller._resolve_gpfs_path", lambda p: p)
    monkeypatch.setattr("controllers.import_controller.os.path.exists", fake_exists)

    with pytest.raises(HTTPException) as exc:
        validate_directory(source_dir=source_dir, user_id=uuid.uuid4())

    assert exc.value.status_code == 400
    assert "gains" in exc.value.detail.lower()


def test_magellon_import_endpoint_schedules_background_task(monkeypatch):
    monkeypatch.setattr("controllers.import_controller._resolve_gpfs_path", lambda p: p)
    monkeypatch.setattr("controllers.import_controller.os.path.exists", lambda _p: True)

    background_tasks = BackgroundTasks()
    request = MagellonImportJobDto(source_dir=r"C:\data\24dec03a")

    response = import_directory(
        request=request,
        background_tasks=background_tasks,
        _=None,
        user_id=uuid.uuid4(),
    )

    assert response["status"] == "scheduled"
    assert uuid.UUID(response["job_id"])
    assert len(background_tasks.tasks) == 1
