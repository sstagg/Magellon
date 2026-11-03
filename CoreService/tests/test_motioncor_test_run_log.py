"""A Jobs tab test's MotionCor run log is kept in the home folder."""
from __future__ import annotations

import core.motioncor_test_result_processor as processor


def _files(tmp_path, monkeypatch):
    monkeypatch.setattr(processor, "MAGELLON_HOME_DIR", str(tmp_path / "home"))
    job = tmp_path / "jobs" / "task-id"
    job.mkdir(parents=True)
    log = job / "movie_a_motioncor.log"
    log.write_text("Command: x\n")
    result = job / "movie_a_DW.mrc"
    result.write_text("mrc")
    return log, result


def test_run_log_moves_to_home_and_other_outputs_stay(tmp_path, monkeypatch):
    log, result = _files(tmp_path, monkeypatch)
    output_files = [{"name": "motioncorRunLog", "path": str(log)},
                    {"name": "outputDWMrc", "path": str(result)}]

    processor._keep_run_logs(output_files)

    kept = tmp_path / "home" / "testing" / "fao" / "movie_a" / "movie_a_motioncor.log"
    assert kept.read_text() == "Command: x\n"
    assert not log.exists()
    assert output_files[0]["path"] == str(kept)
    assert result.exists() and output_files[1]["path"] == str(result)


def test_a_redelivered_result_is_not_an_error(tmp_path, monkeypatch):
    log, _ = _files(tmp_path, monkeypatch)
    output_files = [{"name": "motioncorRunLog", "path": str(log)}]
    processor._keep_run_logs(output_files)

    again = [{"name": "motioncorRunLog", "path": str(log)}]
    processor._keep_run_logs(again)

    assert again[0]["path"] == output_files[0]["path"]


def test_a_log_that_cannot_be_moved_keeps_its_path(tmp_path, monkeypatch):
    monkeypatch.setattr(processor, "MAGELLON_HOME_DIR", str(tmp_path / "home"))
    missing = str(tmp_path / "jobs" / "gone_motioncor.log")
    output_files = [{"name": "motioncorRunLog", "path": missing}]

    processor._keep_run_logs(output_files)

    assert output_files[0]["path"] == missing
