"""Contract test for the FFT plugin container (G.2).

Mirror of ``test_ctf_plugin_contract.py`` against the FFT plugin's
``POST /execute`` endpoint. FFT is CPU-bound and fast enough to run
on a small synthetic MRC in real time, but this contract test still
uses a missing-file canned task to keep the pin strictly about the
wire shape — the plugin-specific unit tests own the compute
correctness.

Skips cleanly when the plugin container isn't running. See
``tests/contracts/conftest.py``.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest

pytest.importorskip("httpx")


def _canned_fft_task() -> Dict[str, Any]:
    task_id = uuid.uuid4()
    job_id = uuid.uuid4()
    image_id = uuid.uuid4()

    return {
        "id": str(task_id),
        "job_id": str(job_id),
        "type": {
            "code": 1,
            "name": "FFT",
            "description": "Fast Fourier Transform",
        },
        "status": {
            "code": 0,
            "name": "pending",
            "description": "Task is pending",
        },
        "data": {
            # CryoEmFftTaskDetailDto shape. Missing source → clean fail.
            "image_id": str(image_id),
            "image_name": "contract_test_missing",
            "image_path": "/magellon/does-not-exist/contract_test.mrc",
            "target_name": "contract_test_fft",
            "target_path": "/magellon/does-not-exist/contract_test_fft.png",
        },
    }


def test_execute_endpoint_echoes_task_identifiers(require_fft_plugin):
    import httpx

    task = _canned_fft_task()
    url = f"http://127.0.0.1:{require_fft_plugin}/execute"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200, (
        f"FFT /execute returned {resp.status_code}: {resp.text[:200]}"
    )
    body = resp.json()
    if "task_id" not in body and "result" in body:
        body = body["result"]

    assert body.get("task_id") == task["id"]
    assert body.get("job_id") == task["job_id"]


def test_execute_endpoint_returns_task_result_shape(require_fft_plugin):
    import httpx

    from magellon_sdk.models import TaskResultDto

    task = _canned_fft_task()
    url = f"http://127.0.0.1:{require_fft_plugin}/execute"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200
    body = resp.json()
    if "task_id" not in body and "result" in body:
        body = body["result"]

    result = TaskResultDto.model_validate(body)
    assert result.task_id == uuid.UUID(task["id"])
    assert result.job_id == uuid.UUID(task["job_id"])
