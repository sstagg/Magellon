"""Unit tests for TaskOutputProcessor state advancement.

Focus: the ``ImageJobTask.status_id`` / ``stage`` write that used to be
missing. File-copy + metadata paths are out of scope — they touch
config and the filesystem and are better exercised end-to-end.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from services.task_output_processor import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    TaskOutputProcessor,
)


class _StubTaskType:
    def __init__(self, code: int, name: str):
        self.code = code
        self.name = name


class _StubStatus:
    def __init__(self, code: int):
        self.code = code


class _StubTaskResult:
    def __init__(self, *, task_id, type_code, status_code=None):
        self.task_id = task_id
        self.type = _StubTaskType(type_code, f"type-{type_code}")
        self.status = _StubStatus(status_code) if status_code is not None else None
        self.image_id = uuid4()
        self.image_path = "/tmp/img.mrc"
        self.session_name = "sess1"
        self.output_files = []
        self.output_data = None
        self.meta_data = None


def _make_processor_with_stub(db_task):
    """Build a TaskOutputProcessor whose `.db` is a stub session that
    returns ``db_task`` for any ImageJobTask lookup. Bypasses
    AppSettingsSingleton so these tests don't need live settings."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = db_task

    # Instantiate without triggering settings lookup.
    proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
    proc.db = db
    proc._queue_type_output_config = {}
    return proc, db


def test_advance_task_state_motioncor_completed():
    task_id = uuid4()
    db_task = MagicMock(status_id=0, stage=0)

    proc, _ = _make_processor_with_stub(db_task)
    result = _StubTaskResult(task_id=task_id, type_code=5)  # MotionCor

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    assert db_task.status_id == STATUS_COMPLETED
    assert db_task.stage == 1  # MotionCor = stage 1


def test_advance_task_state_ctf_failed():
    task_id = uuid4()
    db_task = MagicMock(status_id=0, stage=0)

    proc, _ = _make_processor_with_stub(db_task)
    result = _StubTaskResult(task_id=task_id, type_code=2)  # CTF

    proc._advance_task_state(result, status_id=STATUS_FAILED)

    assert db_task.status_id == STATUS_FAILED
    assert db_task.stage == 2  # CTF = stage 2


def test_advance_task_state_unknown_type_goes_to_default_stage():
    task_id = uuid4()
    db_task = MagicMock(status_id=0, stage=0)

    proc, _ = _make_processor_with_stub(db_task)
    result = _StubTaskResult(task_id=task_id, type_code=99)

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    assert db_task.stage == 99  # _DEFAULT_STAGE — visible-in-UI sentinel


def test_advance_task_state_no_task_id_is_safe():
    """result.task_id=None must not raise — the helper just logs & skips."""
    proc, db = _make_processor_with_stub(db_task=None)
    result = _StubTaskResult(task_id=None, type_code=5)

    proc._advance_task_state(result, status_id=STATUS_COMPLETED)

    db.query.assert_not_called()


def test_advance_task_state_missing_row_is_safe():
    proc, _ = _make_processor_with_stub(db_task=None)
    result = _StubTaskResult(task_id=uuid4(), type_code=5)

    # Should not raise — just log and move on.
    proc._advance_task_state(result, status_id=STATUS_COMPLETED)
