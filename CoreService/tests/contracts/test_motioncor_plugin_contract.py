"""Contract test for the MotionCor plugin container (G.2).

Mirror of ``test_ctf_plugin_contract.py`` against the MotionCor
plugin's ``POST /execute`` endpoint. Same contract: plugin accepts
TaskDto, returns TaskResultDto, echoes task_id / job_id, and
populates provenance where available.

MotionCor is GPU-bound in real execution; the canned task here
points at a missing frame file so the plugin exits early without
needing a GPU or real frames. What we're pinning is the wire
shape, not the science.

Skips cleanly when the plugin container isn't running. See
``tests/contracts/conftest.py``.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest

pytest.importorskip("httpx")


def _canned_motioncor_task() -> Dict[str, Any]:
    task_id = uuid.uuid4()
    job_id = uuid.uuid4()
    image_id = uuid.uuid4()

    return {
        "id": str(task_id),
        "job_id": str(job_id),
        "type": {
            "code": 5,
            "name": "MOTIONCOR",
            "description": "Motion correction",
        },
        "status": {
            "code": 0,
            "name": "pending",
            "description": "Task is pending",
        },
        "data": {
            # CryoEmMotionCorTaskData shape. Missing input → clean fail.
            "image_id": str(image_id),
            "image_name": "contract_test_missing",
            "image_path": "/magellon/does-not-exist/contract_test_frames.eer",
            "inputFile": "/magellon/does-not-exist/contract_test_frames.eer",
            "OutMrc": "contract_test_mc.mrc",
            "Gain": "/magellon/does-not-exist/gain.gain.eer",
            "PatchesX": 5,
            "PatchesY": 5,
            "SumRangeMinDose": 0.0,
            "SumRangeMaxDose": 0.0,
            "FmDose": 0.75,
            "PixSize": 0.705,
            "Group": 3,
        },
    }


def test_execute_endpoint_echoes_task_identifiers(require_motioncor_plugin):
    import httpx

    task = _canned_motioncor_task()
    url = f"http://127.0.0.1:{require_motioncor_plugin}/execute"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200, (
        f"MotionCor /execute returned {resp.status_code}: {resp.text[:200]}"
    )
    body = resp.json()
    if "task_id" not in body and "result" in body:
        body = body["result"]

    assert body.get("task_id") == task["id"]
    assert body.get("job_id") == task["job_id"]


def test_execute_endpoint_returns_task_result_shape(require_motioncor_plugin):
    import httpx

    from magellon_sdk.models import TaskResultDto

    task = _canned_motioncor_task()
    url = f"http://127.0.0.1:{require_motioncor_plugin}/execute"

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200
    body = resp.json()
    if "task_id" not in body and "result" in body:
        body = body["result"]

    result = TaskResultDto.model_validate(body)
    assert result.task_id == uuid.UUID(task["id"])
    assert result.job_id == uuid.UUID(task["job_id"])
