"""The per-movie run log: the exact command, then everything it printed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

motioncor_service = pytest.importorskip("service.motioncor_service")


def test_log_has_the_command_and_both_output_streams_in_order(tmp_path):
    log = tmp_path / "movie_motioncor.log"
    command = "bash -c 'echo first; echo second >&2; echo third'"

    code, output = motioncor_service.run_and_log(command, str(log))

    text = log.read_text()
    assert code == 0
    assert output.splitlines() == ["first", "second", "third"]
    assert f"Command:\n{command}\n" in text
    assert text.index("first") < text.index("second") < text.index("third")
    assert "Exit code: 0" in text


def test_failed_command_keeps_its_output_and_exit_code(tmp_path):
    log = tmp_path / "movie_motioncor.log"

    code, _ = motioncor_service.run_and_log("bash -c 'echo Error: bad gain; exit 3'", str(log))

    assert code == 3
    assert "Error: bad gain" in log.read_text()
    assert "Exit code: 3" in log.read_text()


def test_output_reaches_the_log_while_the_command_is_still_running(tmp_path):
    log = tmp_path / "movie_motioncor.log"
    # The command reads the log itself, so it sees only what was already written.
    command = f"bash -c 'echo early; sleep 1; grep -cx early {log}'"

    _, output = motioncor_service.run_and_log(command, str(log))

    assert output.splitlines() == ["early", "1"]


def test_an_unwritable_log_is_not_an_error(tmp_path):
    motioncor_service.add_to_run_log(str(tmp_path / "missing" / "x.log"), "text")
    motioncor_service.add_to_run_log(None, "text")
