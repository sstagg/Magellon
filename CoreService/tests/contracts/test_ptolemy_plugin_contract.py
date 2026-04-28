"""Contract test for the Ptolemy plugin container.

Mirror of ``test_fft_plugin_contract.py``. The Ptolemy plugin is unusual
in that one container serves two categories (`SquareDetection`, code 6;
`HoleDetection`, code 7). We pin both by posting a canned TaskMessage shape
to the plugin's ``POST /execute`` endpoint and asserting the
``TaskResultMessage`` round-trip.

Uses a missing input_file so the pin is about the wire shape — we
expect a 200 with an error result envelope, or a plugin-raised error
propagated via the FastAPI exception handler. Real compute correctness
lives in the plugin's own ``tests/test_smoke.py``.

Skips cleanly when the plugin container isn't running.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest

pytest.importorskip("httpx")


def _canned_task(category_code: int, category_name: str) -> Dict[str, Any]:
    task_id = uuid.uuid4()
    job_id = uuid.uuid4()
    image_id = uuid.uuid4()

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
        "data": {
            "image_id": str(image_id),
            "image_name": "contract_test_missing",
            "image_path": "/magellon/does-not-exist/contract_test.mrc",
            "input_file": "/magellon/does-not-exist/contract_test.mrc",
        },
    }


def _post(port: int, task: Dict[str, Any]):
    import httpx

    url = f"http://127.0.0.1:{port}/execute"
    with httpx.Client(timeout=30.0) as client:
        return client.post(url, json=task)


# --- SquareDetection (code 6) -----------------------------------------------


def test_square_execute_rejects_unknown_type(require_ptolemy_plugin):
    """Ensure the /execute router guards against unknown type codes."""
    task = _canned_task(category_code=999, category_name="BogusCategory")
    resp = _post(require_ptolemy_plugin, task)
    # Unknown type → plugin's own 400, not FastAPI's generic handler.
    assert resp.status_code == 400
    body = resp.json()
    assert "Unsupported" in body.get("message", "")


def test_square_execute_returns_task_result_shape(require_ptolemy_plugin):
    import httpx

    task = _canned_task(category_code=6, category_name="SquareDetection")
    resp = _post(require_ptolemy_plugin, task)

    # Missing MRC -> plugin's compute raises; FastAPI's exception handler
    # wraps it in a 400 envelope. That's the wire contract we pin.
    assert resp.status_code in (200, 400)
    body = resp.json()

    if resp.status_code == 200:
        from magellon_sdk.models import TaskResultMessage

        result = TaskResultMessage.model_validate(body)
        assert result.task_id == uuid.UUID(task["id"])
        assert result.job_id == uuid.UUID(task["job_id"])
    else:
        assert "message" in body


# --- HoleDetection (code 7) -------------------------------------------------


def test_hole_execute_returns_task_result_shape(require_ptolemy_plugin):
    task = _canned_task(category_code=7, category_name="HoleDetection")
    resp = _post(require_ptolemy_plugin, task)

    assert resp.status_code in (200, 400)
    body = resp.json()

    if resp.status_code == 200:
        from magellon_sdk.models import TaskResultMessage

        result = TaskResultMessage.model_validate(body)
        assert result.task_id == uuid.UUID(task["id"])
        assert result.job_id == uuid.UUID(task["job_id"])
    else:
        assert "message" in body
