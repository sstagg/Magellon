from __future__ import annotations

import subprocess

import pytest

from core.process_runner import run_process_compat


def test_compat_runner_preserves_subprocess_default_check_false(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 17, "", "failed")

    monkeypatch.setattr("core.process_runner.subprocess.run", fake_run)

    result = run_process_compat(["tool", "--probe"])

    assert result.returncode == 17
    assert calls == [(
        ["tool", "--probe"],
        {
            "check": False,
            "capture_output": True,
            "text": True,
            "timeout": 60.0,
            "cwd": None,
            "env": None,
        },
    )]


def test_compat_runner_rejects_shell_execution():
    with pytest.raises(ValueError, match="shell execution is prohibited"):
        run_process_compat(["echo", "unsafe"], shell=True)
