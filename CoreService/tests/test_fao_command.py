"""Reading the MotionCor command for the Frame Alignment tab from the run log."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

import controllers.webapp_controller as web


def _db(session):
    query = SimpleNamespace(filter=lambda *a: SimpleNamespace(first=lambda: session))
    return SimpleNamespace(query=lambda *a: query)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(web.app_settings.directory_settings, "MAGELLON_HOME_DIR", str(tmp_path))
    monkeypatch.setattr(web, "check_session_access", lambda *a, **k: True)
    return tmp_path


def _write_log(home, name, text):
    folder = home / "s1" / web.FAO_SUB_URL / name
    folder.mkdir(parents=True)
    (folder / f"{name}_motioncor.log").write_text(text)


def _get(name="m1", session=SimpleNamespace(oid=uuid4())):
    return web.get_fao_command_route(name=name, sessionName="S1", db=_db(session), user_id=uuid4())


def test_returns_the_command_from_the_log_header(home):
    _write_log(home, "m1", "Image: m1\nStarted: now\n\nCommand:\n/app/MotionCor -InTiff a.tif\n\nOutput:\nx\n")
    assert _get() == {"command": "/app/MotionCor -InTiff a.tif"}


def test_image_processed_before_logs_has_no_command(home):
    assert _get() == {"command": None}


def test_failure_before_any_command_ran_has_no_command(home):
    _write_log(home, "m1", "Image: m1\n\nFailed: movie not found\n")
    assert _get() == {"command": None}


def test_output_mentioning_command_is_not_mistaken_for_the_header(home):
    _write_log(home, "m1", "\n" * 40 + "Command:\nnot this\n")
    assert _get() == {"command": None}


@pytest.mark.parametrize("name", ["../../etc/passwd", "a/b", "..", "."])
def test_names_cannot_leave_the_fao_folder(home, name):
    with pytest.raises(HTTPException) as e:
        _get(name=name)
    assert e.value.status_code == 400


def test_user_without_access_is_refused(home, monkeypatch):
    monkeypatch.setattr(web, "check_session_access", lambda *a, **k: False)
    _write_log(home, "m1", "Command:\nsecret\n")
    with pytest.raises(HTTPException) as e:
        _get()
    assert e.value.status_code == 403


def test_unknown_session_is_not_found(home):
    with pytest.raises(HTTPException) as e:
        _get(session=None)
    assert e.value.status_code == 404
