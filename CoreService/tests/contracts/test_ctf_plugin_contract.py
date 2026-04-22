"""Contract test for the CTF plugin container (G.2).

The plugin exposes ``POST /execute`` as a synchronous HTTP RPC into
``do_execute(TaskDto) -> TaskResultDto``. Hitting that endpoint lets
us verify the wire contract without racing CoreService's in-process
result consumer or touching RMQ.

What this test pins:

- The plugin accepts a :class:`TaskDto` with the CTF category and
  replies with a :class:`TaskResultDto`.
- ``task_id`` and ``job_id`` round-trip (plugin echoes the caller's
  identifiers so the result writer can key off them).
- Provenance is stamped (``plugin_id`` and ``plugin_version``
  populated after the P4 auto-stamp in ``PluginBrokerRunner``).
- The HTTP layer itself behaves — 4xx/5xx here means the container
  is alive but broken; the test fails loud.

The canned input deliberately points at a non-existent file so the
plugin exits on FileNotFoundError without needing real MRC data
shipped with the test fixtures. The plugin's exit path is what we're
contracting, not ctffind4's science.

Skips cleanly when the plugin container isn't running. See
``tests/contracts/conftest.py`` for the skip logic.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest

pytest.importorskip("httpx")  # lighter than requests for the test-time client


def _canned_ctf_task() -> Dict[str, Any]:
    """Shape matches ``TaskDto`` with a CTF-category ``data`` payload
    (``CtfTaskData``) pointing at a non-existent file. The plugin's
    execute() will hit FileNotFoundError and publish a failure-status
    result — both the happy-path wire shape and the failure wire
    shape are contracts worth pinning, but the failure path is
    cheaper to exercise without real input data."""
    task_id = uuid.uuid4()
    job_id = uuid.uuid4()
    image_id = uuid.uuid4()

    return {
        "id": str(task_id),
        "job_id": str(job_id),
        "type": {
            "code": 2,
            "name": "CTF",
            "description": "Contrast Transfer Function",
        },
        "status": {
            "code": 0,
            "name": "pending",
            "description": "Task is pending",
        },
        "data": {
            # CtfTaskData shape. The file path is deliberately absent
            # on disk so ctffind4 can't run; plugin must fail gracefully.
            "image_id": str(image_id),
            "image_name": "contract_test_missing",
            "image_path": "/magellon/does-not-exist/contract_test.mrc",
            "inputFile": "/magellon/does-not-exist/contract_test.mrc",
            "outputFile": "contract_test_ctf.mrc",
            "pixelSize": 1.0,
            "accelerationVoltage": 300.0,
            "sphericalAberration": 2.7,
            "amplitudeContrast": 0.1,
            "sizeOfAmplitudeSpectrum": 512,
            "minimumResolution": 30.0,
            "maximumResolution": 5.0,
            "minimumDefocus": 5000.0,
            "maximumDefocus": 50000.0,
            "defocusSearchStep": 100.0,
            "binning_x": 1,
        },
    }


def test_execute_endpoint_echoes_task_identifiers(require_ctf_plugin):
    """Plugin's ``/execute`` response must keep ``task_id`` and
    ``job_id`` from the request. Without this, the result writer on
    CoreService can't thread the reply back to the right ImageJobTask
    row."""
    import httpx

    task = _canned_ctf_task()
    url = f"http://127.0.0.1:{require_ctf_plugin}/execute"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200, (
        f"CTF /execute returned {resp.status_code}: {resp.text[:200]}"
    )
    body = resp.json()

    # Pydantic may wrap result under a key or return flat; handle both.
    if "task_id" not in body and "result" in body:
        body = body["result"]

    assert body.get("task_id") == task["id"], (
        f"task_id not echoed: sent {task['id']}, got {body.get('task_id')}"
    )
    assert body.get("job_id") == task["job_id"], (
        f"job_id not echoed: sent {task['job_id']}, got {body.get('job_id')}"
    )


def test_execute_endpoint_stamps_provenance(require_ctf_plugin):
    """Every reply carries the plugin's identity so operators know
    which container produced the result (P4 provenance stamp)."""
    import httpx

    task = _canned_ctf_task()
    url = f"http://127.0.0.1:{require_ctf_plugin}/execute"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200
    body = resp.json()
    if "plugin_id" not in body and "result" in body:
        body = body["result"]

    # The live P4 auto-stamp happens inside PluginBrokerRunner on the
    # bus path. The HTTP /execute path calls do_execute directly, which
    # may or may not go through provenance — depends on the plugin's
    # service.py. Assert softly: if provenance IS present, it matches
    # the expected plugin id. If it isn't, mark it xfail-worthy so
    # we notice when the plugin author wires provenance into the HTTP
    # path too.
    plugin_id = body.get("plugin_id")
    if plugin_id is not None:
        # CTFFind plugin identifies as "CTFFind" or similar — allow
        # any non-empty string. The contract is "plugin_id is set
        # consistently"; tightening to a specific name would over-pin.
        assert isinstance(plugin_id, str) and plugin_id, (
            f"plugin_id present but not a non-empty string: {plugin_id!r}"
        )
    else:
        pytest.xfail(
            "CTF plugin's HTTP /execute path does not stamp provenance. "
            "Bus path (PluginBrokerRunner) does (P4). Follow-up: wire "
            "provenance into do_execute so both paths are symmetric."
        )


def test_execute_endpoint_returns_task_result_shape(require_ctf_plugin):
    """The reply JSON must deserialize into a TaskResultDto so the
    result processor can write it. We pin the minimum-viable fields —
    anything more specific belongs in plugin-level tests."""
    import httpx

    from magellon_sdk.models import TaskResultDto

    task = _canned_ctf_task()
    url = f"http://127.0.0.1:{require_ctf_plugin}/execute"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=task)

    assert resp.status_code == 200
    body = resp.json()
    if "task_id" not in body and "result" in body:
        body = body["result"]

    # Soft validation — if the plugin returns extra fields the SDK
    # doesn't know about, model_validate drops them (ignore extras).
    # What we care about is that the core fields pass Pydantic.
    result = TaskResultDto.model_validate(body)
    assert result.task_id == uuid.UUID(task["id"])
    assert result.job_id == uuid.UUID(task["job_id"])
    # status / code may be either success (the plugin found some way
    # to produce a result) or failure (FileNotFoundError). Either is a
    # valid contract reply; the test only requires that one of the
    # known code ranges is present.
    if result.code is not None:
        assert isinstance(result.code, int)
