"""Contract test for the Topaz plugin container.

Mirror of ``test_ptolemy_plugin_contract.py``. The Topaz plugin serves
two categories from one container (TopazParticlePicking code 8,
MicrographDenoising code 9). We pin both by posting a canned TaskDto to
``POST /execute`` and asserting the round-trip shape.

Uses missing input_file paths so the contract is about the wire shape,
not compute correctness — we expect either a 200 with an error result
envelope or a 400 propagated through the FastAPI exception handler.

Skips cleanly when the plugin container isn't running.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest

pytest.importorskip("httpx")


def _canned_task(category_code: int, category_name: str, *, denoise: bool = False) -> Dict[str, Any]:
    task_id = uuid.uuid4()
    job_id = uuid.uuid4()
    image_id = uuid.uuid4()

    data: Dict[str, Any] = {
        "image_id": str(image_id),
        "image_name": "contract_test_missing",
        "image_path": "/magellon/does-not-exist/contract_test.mrc",
        "input_file": "/magellon/does-not-exist/contract_test.mrc",
    }
    if denoise:
        data["output_file"] = "/magellon/does-not-exist/contract_test_denoised.mrc"

    return {
        "id": str(task_id),
        "job_id": str(job_id),
        "type": {
            "code": category_code,
            "name": category_name,
            "description": f"{category_name} contract test",
        },
        "status": {
            "code": 0,
            "name": "pending",
            "description": "Task is pending",
        },
        "data": data,
    }


def _post(port: int, task: Dict[str, Any]):
    import httpx

    url = f"http://127.0.0.1:{port}/execute"
    with httpx.Client(timeout=30.0) as client:
        return client.post(url, json=task)


def test_pick_execute_rejects_unknown_type(require_topaz_plugin):
    task = _canned_task(category_code=999, category_name="BogusCategory")
    resp = _post(require_topaz_plugin, task)
    assert resp.status_code == 400
    body = resp.json()
    assert "Unsupported" in body.get("message", "")


def test_pick_execute_returns_task_result_shape(require_topaz_plugin):
    task = _canned_task(category_code=8, category_name="TopazParticlePicking")
    resp = _post(require_topaz_plugin, task)
    assert resp.status_code in (200, 400)

    body = resp.json()
    if resp.status_code == 200:
        from magellon_sdk.models import TaskResultDto

        result = TaskResultDto.model_validate(body)
        assert result.task_id == uuid.UUID(task["id"])
        assert result.job_id == uuid.UUID(task["job_id"])
    else:
        assert "message" in body


def test_denoise_execute_returns_task_result_shape(require_topaz_plugin):
    task = _canned_task(
        category_code=9, category_name="MicrographDenoising", denoise=True,
    )
    resp = _post(require_topaz_plugin, task)
    assert resp.status_code in (200, 400)

    body = resp.json()
    if resp.status_code == 200:
        from magellon_sdk.models import TaskResultDto

        result = TaskResultDto.model_validate(body)
        assert result.task_id == uuid.UUID(task["id"])
        assert result.job_id == uuid.UUID(task["job_id"])
    else:
        assert "message" in body
