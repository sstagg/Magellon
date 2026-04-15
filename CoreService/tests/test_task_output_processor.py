"""Unit tests for the in-process result-processor (P3).

Pin the contracts the projection layer must hold, regardless of which
queue or category sent the message:

  - ImageJobTask.status_id and stage advance to the right values for the
    completed/failed × motioncor/ctf matrix.
  - A missing task_id or row is handled silently — the consumer must
    not crash on a stray result whose row has been GC'd.
  - The OutQueueConfig list maps queue_type → category/dir_name.
  - The OUT_QUEUES default ([]) leaves the consumer dormant — the
    safety valve that lets deployments adopt the in-process processor
    without forcing a config change.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from models.pydantic_models_settings import OutQueueConfig, OutQueueType
from services.task_output_processor import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    TaskOutputProcessor,
)


class _StubType:
    def __init__(self, code: int, name: str) -> None:
        self.code = code
        self.name = name


class _StubStatus:
    def __init__(self, code: int) -> None:
        self.code = code


class _StubResult:
    def __init__(self, *, task_id, type_code, type_name="t", status_code=None):
        self.task_id = task_id
        self.type = _StubType(type_code, type_name)
        self.status = _StubStatus(status_code) if status_code is not None else None
        self.image_id = uuid4()
        self.image_path = "/tmp/img.mrc"
        self.session_name = "sess1"
        self.output_files = []
        self.output_data = None
        self.meta_data = None


def _make_processor(db_task=None, out_queues=None):
    """Build a TaskOutputProcessor with a stub DB session.

    Bypasses ``__init__``'s settings lookup so the tests don't need
    a populated AppSettingsSingleton.
    """
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = db_task
    proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
    proc.db = db
    proc.magellon_home_dir = "/tmp/magellon"
    proc._queue_type_output_config = (
        TaskOutputProcessor._build_queue_type_output_config(out_queues or [])
    )
    return proc, db


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

def test_advance_motioncor_completed_sets_stage_1():
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=5), status_id=STATUS_COMPLETED)
    assert db_task.status_id == STATUS_COMPLETED
    assert db_task.stage == 1


def test_advance_ctf_failed_sets_stage_2():
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=2), status_id=STATUS_FAILED)
    assert db_task.status_id == STATUS_FAILED
    assert db_task.stage == 2


def test_unknown_type_lands_at_default_stage_99():
    """Operators look for stage=99 to find rows from an unrecognised
    task type — that's the failure-mode signal we lose if we pick a
    real stage as the default."""
    db_task = MagicMock(status_id=0, stage=0)
    proc, _ = _make_processor(db_task)
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=99), status_id=STATUS_COMPLETED)
    assert db_task.stage == 99


def test_advance_skips_when_task_id_is_none():
    """A result with no task_id must not crash the consumer — log + skip."""
    proc, db = _make_processor(db_task=None)
    proc._advance_task_state(_StubResult(task_id=None, type_code=5), status_id=STATUS_COMPLETED)
    db.query.assert_not_called()


def test_advance_skips_when_row_missing():
    """The row may have been deleted between dispatch and result. Don't
    raise — log and move on so the broker can ack the message."""
    proc, _ = _make_processor(db_task=None)
    # Should not raise.
    proc._advance_task_state(_StubResult(task_id=uuid4(), type_code=5), status_id=STATUS_COMPLETED)


# ---------------------------------------------------------------------------
# Queue-config lookup
# ---------------------------------------------------------------------------

def test_queue_config_maps_type_to_category_and_dir():
    """The OUT_QUEUES list is the single source of truth for which
    on-disk subfolder + DB category each result lands under."""
    cfg = [
        OutQueueConfig(name="ctf_out", queue_type=OutQueueType.CTF, dir_name="ctf", category=2),
        OutQueueConfig(name="mc_out", queue_type=OutQueueType.MOTIONCOR, dir_name="fao", category=3),
    ]
    proc, _ = _make_processor(out_queues=cfg)
    assert proc._get_queue_type_output_dir("ctf") == "ctf"
    assert proc._get_queue_type_category("ctf") == 2
    assert proc._get_queue_type_output_dir("motioncor") == "fao"
    assert proc._get_queue_type_category("motioncor") == 3


def test_queue_config_returns_none_for_unknown_type():
    proc, _ = _make_processor(out_queues=[])
    assert proc._get_queue_type_output_dir("ctf") is None
    assert proc._get_queue_type_category("ctf") is None


def test_destination_dir_falls_back_to_type_name_when_no_config():
    """If the deployer didn't list this queue_type, we still get a
    sensible folder named after the task type — keeps results visible
    instead of routing them to ``/None/``."""
    proc, _ = _make_processor(out_queues=[])
    result = _StubResult(task_id=uuid4(), type_code=5, type_name="MotionCor")
    dest = proc._get_destination_dir(result)
    # OS-agnostic: assert the segments are present, not the slash.
    parts = dest.replace("\\", "/").split("/")
    assert parts[-1] == "img"
    assert parts[-2] == "motioncor"
