"""Bootstrap requirement-check tests.

These are the shared startup probes every plugin runs. They must return
``RequirementResult`` entries (never raise) so the plugin host can
aggregate outcomes without special-casing exceptions.
"""
from __future__ import annotations

import asyncio
import subprocess

import pytest

from magellon_sdk import bootstrap
from magellon_sdk.models import CheckRequirementsResult, RecuirementResultEnum


def _run(coro):
    return asyncio.run(coro)


def test_python_version_ok_on_current_interpreter():
    # pyproject requires >=3.9 — current interpreter always passes.
    assert _run(bootstrap.check_python_version()) == []


def test_python_version_fails_when_too_old(monkeypatch):
    monkeypatch.setattr("sys.version_info", (3, 7, 0))
    results = _run(bootstrap.check_python_version())

    assert len(results) == 1
    r = results[0]
    assert r.result == RecuirementResultEnum.FAILURE
    assert r.error_type == CheckRequirementsResult.FAILURE_PYTHON_VERSION_ERROR
    assert r.code == 10


def test_operating_system_pass_on_linux(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    assert _run(bootstrap.check_operating_system()) == []


@pytest.mark.parametrize("os_name", ["Windows", "Darwin", "FreeBSD"])
def test_operating_system_fails_off_linux(monkeypatch, os_name):
    monkeypatch.setattr("platform.system", lambda: os_name)
    results = _run(bootstrap.check_operating_system())

    assert len(results) == 1
    r = results[0]
    assert r.result == RecuirementResultEnum.FAILURE
    assert r.error_type == CheckRequirementsResult.FAILURE_OS_ERROR
    assert os_name in r.message
    assert r.code == 20


def test_requirements_txt_pass(monkeypatch):
    def _ok(*_args, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr("subprocess.run", _ok)
    assert _run(bootstrap.check_requirements_txt()) == []


def test_requirements_txt_fail_on_called_process_error(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise subprocess.CalledProcessError(1, ["pip", "check"])

    monkeypatch.setattr("subprocess.run", _raise)
    results = _run(bootstrap.check_requirements_txt())

    assert len(results) == 1
    r = results[0]
    assert r.result == RecuirementResultEnum.FAILURE
    assert r.error_type == CheckRequirementsResult.FAILURE_REQUIREMENTS
    assert r.code == 30
