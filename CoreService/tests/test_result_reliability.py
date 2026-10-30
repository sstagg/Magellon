"""Result processing must apply each plugin result exactly once and never
drop one: duplicates are skipped, the result and its effect on the job
commit together, failures roll back and raise for a retry (transient
database errors with a delay), results that keep failing are dead-lettered
and fail their step, file moves survive a retry, and large values go to
files instead of the database.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import OperationalError

import core.result_consumer as rc
from magellon_sdk.errors import RetryableError
from models.sqlalchemy_models import TaskResultDeadLetter, TaskResultReceipt
from services import task_output_processor as top
from services.task_output_processor import OFFLOAD_BYTES, TaskOutputProcessor


def _result(*, type_name="CTF", type_code=2, failed=False, meta=None, output=None):
    return SimpleNamespace(
        task_id=uuid4(), job_id=uuid4(), image_id=uuid4(),
        type=SimpleNamespace(code=type_code, name=type_name),
        status=SimpleNamespace(code=3 if failed else 2),
        image_path="/data/img_0001.mrc", session_name="sess1",
        output_files=[], output_data=output, meta_data=meta,
        plugin_id=None, plugin_version=None, subject_kind=None, subject_id=None,
        description="", message="",
    )


def _processor(tmp_path, *, receipt=None):
    db = MagicMock()
    db.get.return_value = receipt
    db.query.return_value.filter.return_value.first.return_value = None
    proc = TaskOutputProcessor.__new__(TaskOutputProcessor)
    proc.db = db
    proc.magellon_home_dir = str(tmp_path)
    proc._queue_type_output_config = TaskOutputProcessor._build_queue_type_output_config([])
    return proc, db


def test_duplicate_result_is_skipped(tmp_path):
    proc, db = _processor(tmp_path, receipt=object())
    out = proc.process(_result())
    assert "already processed" in out["message"]
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_result_receipt_and_job_update_commit_together(tmp_path):
    proc, db = _processor(tmp_path)
    result = _result()
    with patch("services.job_manager.job_manager.record_task_finished") as record:
        proc.process(result)
    receipts = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], TaskResultReceipt)]
    assert len(receipts) == 1 and receipts[0].step == "ctf" and receipts[0].task_id == str(result.task_id)
    record.assert_called_once()
    assert record.call_args.kwargs["db"] is db          # same transaction
    assert db.commit.call_count == 1


def test_transient_database_error_rolls_back_and_asks_for_retry(tmp_path):
    proc, db = _processor(tmp_path)
    db.commit.side_effect = OperationalError("COMMIT", {}, Exception("server has gone away"))
    with patch("services.job_manager.job_manager.record_task_finished"):
        with pytest.raises(RetryableError):
            proc.process(_result())
    db.rollback.assert_called()


def test_other_errors_propagate_after_rollback(tmp_path):
    proc, db = _processor(tmp_path)
    with patch("services.job_manager.job_manager.record_task_finished", side_effect=ValueError("bad")):
        with pytest.raises(ValueError):
            proc.process(_result())
    db.rollback.assert_called()
    db.commit.assert_not_called()


def test_large_values_are_written_to_files(tmp_path):
    big = "x" * (OFFLOAD_BYTES + 1)
    meta = [SimpleNamespace(key="patchAlignment_Image_data", value=big, dict=None),
            SimpleNamespace(key="small", value="1", dict=None)]
    result = _result(type_name="MotionCor", type_code=5, meta=meta, output={"output_avrot": big, "n": 3})
    proc, _ = _processor(tmp_path)
    proc._offload_large_values(result, str(tmp_path / "dest"))

    ref = json.loads(meta[0].value)
    assert ref["bytes"] == len(big) and open(ref["file"]).read() == big
    assert meta[1].value == "1"
    assert result.output_data["output_avrot"]["file"].endswith("img_0001_output_avrot.txt")
    assert result.output_data["n"] == 3


def test_file_move_already_done_by_an_earlier_delivery(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "out.mrc").write_text("done")
    assert top._move_file_to_directory(str(tmp_path / "out.mrc"), str(dest)) is True


def test_dead_lettered_result_is_kept_and_fails_its_step():
    db = MagicMock()
    hook = rc._dead_letter_hook("ctf_out_tasks_queue", lambda: db)
    task_id, job_id = uuid4(), uuid4()
    envelope = SimpleNamespace(data={"task_id": str(task_id), "job_id": str(job_id),
                                     "image_id": str(uuid4()), "code": 200, "message": "ok",
                                     "type": {"code": 2, "name": "CTF", "description": "ctf"}})
    with patch("services.job_manager.job_manager.record_task_finished") as record:
        hook(envelope, RuntimeError("keeps failing"))
    kept = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], TaskResultDeadLetter)]
    assert len(kept) == 1 and kept[0].task_id == str(task_id) and "keeps failing" in kept[0].error
    assert record.call_args.kwargs["failed"] is True and record.call_args.kwargs["db"] is db
    db.commit.assert_called_once()


def test_record_task_finished_in_caller_transaction_does_not_commit():
    from services.job_manager import JobManager
    db = MagicMock()
    jm = JobManager()
    with patch.object(JobManager, "_record_task_finished", return_value={"settled": None}) as inner:
        jm.record_task_finished("j", "t", step="CTF", db=db)
    inner.assert_called_once()
    db.commit.assert_not_called()
