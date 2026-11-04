"""The per-image run log: the exact command, then everything it printed."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ctf_service = pytest.importorskip("service.ctf_service")


def test_log_has_the_multi_line_command_and_its_output(tmp_path):
    log = tmp_path / "image_ctffind.log"
    command = 'echo -e "a\nb" | cat; echo problem >&2'

    code, output = ctf_service.run_and_log(command, str(log))

    text = log.read_text()
    assert code == 0
    assert output.splitlines() == ["a", "b", "problem"]
    assert f"Command:\n{command}\n\nOutput:\n" in text
    assert "Exit code: 0" in text


def test_failed_command_keeps_its_output_and_exit_code(tmp_path):
    log = tmp_path / "image_ctffind.log"

    code, _ = ctf_service.run_and_log("bash -c 'echo bad input; exit 3'", str(log))

    assert code == 3
    assert "bad input" in log.read_text()
    assert "Exit code: 3" in log.read_text()


def test_an_unwritable_log_is_not_an_error(tmp_path):
    ctf_service.add_to_run_log(str(tmp_path / "missing" / "x.log"), "text")
    ctf_service.add_to_run_log(None, "text")


def test_ctffind_values_are_converted_to_the_evaluation_units():
    values = ctf_service.ctffind_values(["1.0", "33893.0", "33854.0", "90.0", "0.0"])

    assert values["defocus1"] == pytest.approx(3.3893e-6)
    assert values["defocus2"] == pytest.approx(3.3854e-6)
    assert values["angle_astigmatism"] == pytest.approx(1.570796, abs=1e-5)
