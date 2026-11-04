"""The nightly clean-up removes Jobs tab test logs, and nothing else."""
from __future__ import annotations

import os
import time

import pytest

import config
from services import jobs_cleanup


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MAGELLON_HOME_DIR", str(tmp_path))
    monkeypatch.setattr(jobs_cleanup, "_testing_is_a_session", lambda: False)
    return tmp_path


def _file(home, *parts, age_hours=3):
    path = home.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    old = time.time() - age_hours * 3600
    os.utime(path, (old, old))
    os.utime(path.parent, (old, old))
    return path


def test_old_logs_and_their_empty_folders_go(home):
    mc = _file(home, "testing", "fao", "a", "a_motioncor.log")
    ctf = _file(home, "testing", "ctf", "b", "b_ctffind.log")

    assert jobs_cleanup.clean_test_logs()["removed"] == 2

    assert not mc.parent.exists() and not ctf.parent.exists()


def test_a_log_from_the_last_two_hours_stays(home):
    log = _file(home, "testing", "fao", "a", "a_motioncor.log", age_hours=1)

    assert jobs_cleanup.clean_test_logs() == {"removed": 0, "kept_recent": 1}
    assert log.exists()


def test_other_files_and_other_sessions_are_never_touched(home):
    other = _file(home, "testing", "fao", "a", "a_DW.mrc")
    log = _file(home, "testing", "fao", "a", "a_motioncor.log")
    real = _file(home, "26oct27a", "fao", "c", "c_motioncor.log")

    jobs_cleanup.clean_test_logs()

    assert other.exists() and not log.exists() and real.exists()


def test_a_real_session_named_testing_is_left_alone(home, monkeypatch):
    monkeypatch.setattr(jobs_cleanup, "_testing_is_a_session", lambda: True)
    log = _file(home, "testing", "fao", "a", "a_motioncor.log")

    assert jobs_cleanup.clean_test_logs()["removed"] == 0
    assert log.exists()


def test_a_database_failure_deletes_nothing(home, monkeypatch):
    def down():
        raise RuntimeError("database down")
    monkeypatch.setattr(jobs_cleanup, "_testing_is_a_session", down)
    log = _file(home, "testing", "fao", "a", "a_motioncor.log")

    with pytest.raises(RuntimeError):
        jobs_cleanup.clean_test_logs()
    assert log.exists()


def test_no_testing_folder_is_fine(home):
    assert jobs_cleanup.clean_test_logs() == {"removed": 0, "kept_recent": 0}
