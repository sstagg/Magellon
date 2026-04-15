"""HTTP-layer tests for the P9 cancellation controller.

The service module is exercised separately in
``test_cancellation_service``. Here we pin the controller's job:

  - Routes plug into the router with the right verbs/paths.
  - Service exceptions are mapped to sensible HTTP status codes
    (broker hiccup → 502, missing container → 404).
  - The request/response shapes match what the operator UI assumes.

We mount the router on a throwaway FastAPI app rather than importing
``main`` so the test doesn't drag in DB / RMQ startup hooks.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers import cancellation_controller as ctl
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_role


@pytest.fixture
def client():
    """Minimal app with auth + RBAC overridden — these dependencies
    aren't what we're testing here, and standing them up would require
    a real DB session."""
    app = FastAPI()
    app.include_router(ctl.cancellation_router, prefix="/cancellation")
    fake_user = uuid4()
    app.dependency_overrides[get_current_user_id] = lambda: fake_user
    app.dependency_overrides[require_role("Administrator")] = lambda: None
    # require_role returns a *new* dep callable each call, so override
    # by name as well — FastAPI keys overrides by the resolved callable.
    for route in app.routes:
        for dep in getattr(route, "dependant", None).dependencies if getattr(route, "dependant", None) else []:
            if dep.call is not None and dep.call.__qualname__.startswith("require_role"):
                app.dependency_overrides[dep.call] = lambda: None
    return TestClient(app)


# ---------------------------------------------------------------------------
# /queues/purge
# ---------------------------------------------------------------------------

def test_purge_queues_returns_per_queue_counts(client):
    """Happy path: the controller hands the queue list to the service
    and surfaces its dict verbatim."""
    with patch.object(ctl.cancellation_service, "purge_queues",
                      return_value={"ctf_tasks_queue": 4, "fft_tasks_queue": 0}):
        resp = client.post(
            "/cancellation/queues/purge",
            json={"queue_names": ["ctf_tasks_queue", "fft_tasks_queue"]},
        )

    assert resp.status_code == 200
    assert resp.json() == {"purged": {"ctf_tasks_queue": 4, "fft_tasks_queue": 0}}


def test_purge_queues_rejects_empty_list(client):
    """min_length=1 on the request model — an empty purge has no meaning
    and is more likely a frontend bug than intent."""
    resp = client.post("/cancellation/queues/purge", json={"queue_names": []})
    assert resp.status_code == 422


def test_purge_queues_maps_broker_failure_to_502(client):
    """A connection-level pika failure is upstream — 502 reflects that
    accurately, where 500 would imply a CoreService bug."""
    with patch.object(ctl.cancellation_service, "purge_queues",
                      side_effect=RuntimeError("broker unreachable")):
        resp = client.post(
            "/cancellation/queues/purge",
            json={"queue_names": ["ctf_tasks_queue"]},
        )

    assert resp.status_code == 502
    assert "broker unreachable" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /containers/{name}/kill
# ---------------------------------------------------------------------------

def test_kill_container_returns_service_payload(client):
    """The service result is echoed straight back; the controller adds
    no fields of its own (audit goes to the log, not the response)."""
    payload = {
        "container_name": "ctf-plugin-1",
        "id": "abc123",
        "signal": "SIGKILL",
        "status": "killed",
    }
    with patch.object(ctl.cancellation_service, "kill_plugin_container",
                      return_value=payload) as mock:
        resp = client.post("/cancellation/containers/ctf-plugin-1/kill")

    assert resp.status_code == 200
    assert resp.json() == payload
    mock.assert_called_once_with("ctf-plugin-1", signal="SIGKILL")


def test_kill_container_signal_query_param_is_forwarded(client):
    """``?signal=SIGTERM`` must reach the service unmodified — the
    operator's intent (graceful kill) hinges on this."""
    payload = {
        "container_name": "ctf-plugin-1",
        "id": "abc123",
        "signal": "SIGTERM",
        "status": "killed",
    }
    with patch.object(ctl.cancellation_service, "kill_plugin_container",
                      return_value=payload) as mock:
        resp = client.post("/cancellation/containers/ctf-plugin-1/kill?signal=SIGTERM")

    assert resp.status_code == 200
    mock.assert_called_once_with("ctf-plugin-1", signal="SIGTERM")


def test_kill_container_missing_container_maps_to_404(client):
    """docker SDK's NotFound text triggers a 404 — operators should
    see 'doesn't exist' not 'broker error'."""
    with patch.object(ctl.cancellation_service, "kill_plugin_container",
                      side_effect=RuntimeError("404 Client Error: Not Found for "
                                              'container: ghost')):
        resp = client.post("/cancellation/containers/ghost/kill")

    assert resp.status_code == 404


def test_kill_container_other_failure_maps_to_502(client):
    """Anything that doesn't read like 'not found' is treated as an
    upstream issue with the docker daemon → 502."""
    with patch.object(ctl.cancellation_service, "kill_plugin_container",
                      side_effect=RuntimeError("daemon connection refused")):
        resp = client.post("/cancellation/containers/ctf-plugin-1/kill")

    assert resp.status_code == 502
