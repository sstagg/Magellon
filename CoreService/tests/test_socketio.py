"""
Tests for the Socket.IO integration.

Tests handler logic by invoking handlers directly with a mocked sio.emit,
so no running server is needed. Includes chaos/resilience tests that simulate
connection drops, emit failures, and concurrent access.
"""
import asyncio
from unittest.mock import AsyncMock, patch, call

import pytest
import socketio

from core.socketio_server import sio, _run_job_simulation
from main import app


# ---------------------------------------------------------------------------
# Test: socketio-test page is served
# ---------------------------------------------------------------------------

def test_socketio_test_page_served():
    """The /socketio-test HTML page should be reachable via GET."""
    from fastapi.testclient import TestClient
    http = TestClient(app)
    response = http.get("/socketio-test")
    assert response.status_code == 200
    assert "Socket.IO Test" in response.text


# ---------------------------------------------------------------------------
# Test: server module structure
# ---------------------------------------------------------------------------

def test_sio_instance_exists():
    """The sio server object should be an AsyncServer."""
    assert isinstance(sio, socketio.AsyncServer)


def test_sio_has_expected_handlers():
    """All demo event handlers should be registered."""
    handlers = sio.handlers.get("/", {})
    for event_name in ("connect", "disconnect", "ping", "start_job_simulation", "broadcast_message"):
        assert event_name in handlers, f"Handler '{event_name}' not registered on sio"


def test_asgi_app_wraps_fastapi():
    """socket_app should wrap the FastAPI app."""
    from main import socket_app
    assert socket_app is not None
    assert socket_app.other_asgi_app is app


# ---------------------------------------------------------------------------
# Test: connect sends welcome message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_sends_welcome():
    """On connect, server should emit a welcome server_message."""
    handler = sio.handlers["/"]["connect"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("test-sid-123", {})
        mock_emit.assert_called_once_with(
            "server_message",
            {"message": "Welcome! You are connected."},
            room="test-sid-123",
        )


# ---------------------------------------------------------------------------
# Test: ping / pong
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ping_pong():
    """Ping handler should emit pong with echoed data."""
    handler = sio.handlers["/"]["ping"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("sid-abc", "hello-test")
        mock_emit.assert_called_once_with(
            "pong",
            {"echo": "hello-test", "from": "server"},
            room="sid-abc",
        )


@pytest.mark.asyncio
async def test_ping_with_dict_data():
    """Ping handler should echo dict data as well."""
    handler = sio.handlers["/"]["ping"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("sid-xyz", {"key": "value"})
        mock_emit.assert_called_once_with(
            "pong",
            {"echo": {"key": "value"}, "from": "server"},
            room="sid-xyz",
        )


# ---------------------------------------------------------------------------
# Test: broadcast_message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_message():
    """Broadcast handler should emit to all clients (no room filter)."""
    handler = sio.handlers["/"]["broadcast_message"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("sid-sender", {"message": "hi everyone"})
        mock_emit.assert_called_once_with(
            "server_broadcast",
            {"from_sid": "sid-sender", "message": "hi everyone"},
        )


@pytest.mark.asyncio
async def test_broadcast_empty_message():
    """Broadcast with no message key should default to empty string."""
    handler = sio.handlers["/"]["broadcast_message"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("sid-sender", {})
        mock_emit.assert_called_once_with(
            "server_broadcast",
            {"from_sid": "sid-sender", "message": ""},
        )


@pytest.mark.asyncio
async def test_broadcast_none_data():
    """Broadcast with None data should not crash."""
    handler = sio.handlers["/"]["broadcast_message"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("sid-sender", None)
        mock_emit.assert_called_once_with(
            "server_broadcast",
            {"from_sid": "sid-sender", "message": ""},
        )


# ---------------------------------------------------------------------------
# Test: start_job_simulation spawns background task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_job_simulation_spawns_background_task():
    """Handler should call sio.start_background_task and return immediately."""
    handler = sio.handlers["/"]["start_job_simulation"]
    with patch.object(sio, "start_background_task") as mock_bg:
        await handler("sid-bg", {"job_name": "bg-job", "total_steps": 5})
        mock_bg.assert_called_once_with(_run_job_simulation, "sid-bg", "bg-job", 5)


@pytest.mark.asyncio
async def test_start_job_simulation_uses_defaults():
    """Handler should use defaults when data is None."""
    handler = sio.handlers["/"]["start_job_simulation"]
    with patch.object(sio, "start_background_task") as mock_bg:
        await handler("sid-def", None)
        mock_bg.assert_called_once_with(_run_job_simulation, "sid-def", "test-job", 10)


# ---------------------------------------------------------------------------
# Test: _run_job_simulation progress emits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_simulation_emits_progress():
    """
    Job simulation with 3 steps should emit 3 running + 1 completed = 4 events.
    """
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit, \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-job", "ctf-test", 3)

        assert mock_emit.call_count == 4

        # Step 1 — running
        assert mock_emit.call_args_list[0] == call(
            "job_progress",
            {"job_name": "ctf-test", "step": 1, "total_steps": 3, "percent": 33, "status": "running"},
            room="sid-job",
        )

        # Step 2 — running
        assert mock_emit.call_args_list[1] == call(
            "job_progress",
            {"job_name": "ctf-test", "step": 2, "total_steps": 3, "percent": 67, "status": "running"},
            room="sid-job",
        )

        # Step 3 — running (from loop)
        assert mock_emit.call_args_list[2] == call(
            "job_progress",
            {"job_name": "ctf-test", "step": 3, "total_steps": 3, "percent": 100, "status": "running"},
            room="sid-job",
        )

        # Final — completed
        assert mock_emit.call_args_list[3] == call(
            "job_progress",
            {"job_name": "ctf-test", "step": 3, "total_steps": 3, "percent": 100, "status": "completed"},
            room="sid-job",
        )


@pytest.mark.asyncio
async def test_job_simulation_defaults():
    """Job simulation with 10 steps emits 11 events (10 running + 1 completed)."""
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit, \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-default", "test-job", 10)

        assert mock_emit.call_count == 11
        first_data = mock_emit.call_args_list[0][0][1]
        assert first_data["job_name"] == "test-job"
        assert first_data["total_steps"] == 10
        last_data = mock_emit.call_args_list[-1][0][1]
        assert last_data["status"] == "completed"
        assert last_data["percent"] == 100


@pytest.mark.asyncio
async def test_job_simulation_single_step():
    """A 1-step job should emit 1 running + 1 completed = 2 events."""
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit, \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-one", "quick", 1)

        assert mock_emit.call_count == 2
        assert mock_emit.call_args_list[0][0][1]["status"] == "running"
        data = mock_emit.call_args_list[1][0][1]
        assert data["status"] == "completed"
        assert data["percent"] == 100
        assert data["step"] == 1


# ===========================================================================
# CHAOS / RESILIENCE TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# Chaos: client disconnects mid-job (emit raises after N calls)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_survives_client_disconnect_mid_progress():
    """
    Simulate a client disconnecting after step 2 of 5.
    emit raises on the 3rd call; handler catches it — no crash.
    """
    call_count = 0

    async def emit_then_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            raise socketio.exceptions.BadNamespaceError("client disconnected")

    with patch.object(sio, "emit", side_effect=emit_then_fail), \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-dropout", "fragile-job", 5)

    assert call_count == 3  # 2 ok + 1 that raised


@pytest.mark.asyncio
async def test_job_survives_emit_connection_reset():
    """
    TCP ConnectionResetError on first emit — should not crash.
    """
    async def immediate_reset(*args, **kwargs):
        raise ConnectionResetError("Connection reset by peer")

    with patch.object(sio, "emit", side_effect=immediate_reset), \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-reset", "reset-job", 5)


@pytest.mark.asyncio
async def test_job_survives_emit_oserror():
    """
    OSError (broken pipe) on emit — should not crash.
    """
    async def broken_pipe(*args, **kwargs):
        raise OSError("Broken pipe")

    with patch.object(sio, "emit", side_effect=broken_pipe), \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-broken", "pipe-job", 3)


# ---------------------------------------------------------------------------
# Chaos: intermittent emit failures (flaky network)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_aborts_on_flaky_emit():
    """
    Emit works for step 1, fails on step 2.
    Handler aborts cleanly after the first failure.
    """
    emitted = []

    async def flaky_emit(*args, **kwargs):
        emitted.append(args)
        if len(emitted) == 2:
            raise ConnectionError("network blip")

    with patch.object(sio, "emit", side_effect=flaky_emit), \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await _run_job_simulation("sid-flaky", "flaky-job", 5)

    assert len(emitted) == 2


# ---------------------------------------------------------------------------
# Chaos: concurrent jobs for the same client
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_jobs_same_client():
    """
    Two jobs for the same sid run simultaneously — both complete,
    no interference.
    """
    emitted_events = []

    async def track_emit(event, data, **kwargs):
        emitted_events.append((event, data.get("job_name"), data.get("step")))

    with patch.object(sio, "emit", side_effect=track_emit), \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        await asyncio.gather(
            _run_job_simulation("sid-multi", "job-A", 3),
            _run_job_simulation("sid-multi", "job-B", 3),
        )

    job_a_events = [e for e in emitted_events if e[1] == "job-A"]
    job_b_events = [e for e in emitted_events if e[1] == "job-B"]

    # Each job: 3 running + 1 completed = 4
    assert len(job_a_events) == 4
    assert len(job_b_events) == 4

    assert job_a_events[-1] == ("job_progress", "job-A", 3)
    assert job_b_events[-1] == ("job_progress", "job-B", 3)


# ---------------------------------------------------------------------------
# Chaos: many concurrent clients (stress)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_many_concurrent_clients():
    """
    50 clients each running a 3-step job simultaneously.
    All 50 should complete without errors.
    """
    completed_jobs = []

    async def track_completion(event, data, **kwargs):
        if data.get("status") == "completed":
            completed_jobs.append(data["job_name"])

    with patch.object(sio, "emit", side_effect=track_completion), \
         patch("core.socketio_server.asyncio.sleep", new_callable=AsyncMock):

        tasks = [
            _run_job_simulation(f"sid-{i}", f"job-{i}", 3)
            for i in range(50)
        ]
        await asyncio.gather(*tasks)

    assert len(completed_jobs) == 50
    assert set(completed_jobs) == {f"job-{i}" for i in range(50)}


# ---------------------------------------------------------------------------
# Chaos: rapid connect / disconnect cycles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rapid_connect_disconnect_cycles():
    """
    20 rapid connect/disconnect cycles.
    Each should emit a welcome and handle disconnect cleanly.
    """
    connect_handler = sio.handlers["/"]["connect"]
    disconnect_handler = sio.handlers["/"]["disconnect"]
    welcome_count = 0

    async def count_welcomes(*args, **kwargs):
        nonlocal welcome_count
        welcome_count += 1

    with patch.object(sio, "emit", side_effect=count_welcomes):
        for i in range(20):
            await connect_handler(f"sid-rapid-{i}", {})
            await disconnect_handler(f"sid-rapid-{i}")

    assert welcome_count == 20


# ---------------------------------------------------------------------------
# Chaos: disconnect during connect welcome (emit fails on connect)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_emit_fails_gracefully():
    """
    If the welcome emit fails during connect (client already gone),
    the exception propagates — Socket.IO handles it at the transport layer.
    """
    connect_handler = sio.handlers["/"]["connect"]

    async def fail_emit(*args, **kwargs):
        raise ConnectionResetError("gone before welcome")

    with patch.object(sio, "emit", side_effect=fail_emit):
        with pytest.raises(ConnectionResetError):
            await connect_handler("sid-ghost", {})


# ---------------------------------------------------------------------------
# Chaos: broadcast with all clients disconnected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_with_no_clients():
    """
    Broadcast when no clients are connected — should complete without error.
    """
    handler = sio.handlers["/"]["broadcast_message"]
    with patch.object(sio, "emit", new_callable=AsyncMock) as mock_emit:
        await handler("sid-alone", {"message": "anyone there?"})
        mock_emit.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_emit_failure():
    """
    If broadcast emit raises, the error propagates.
    """
    handler = sio.handlers["/"]["broadcast_message"]

    async def fail(*args, **kwargs):
        raise RuntimeError("broadcast failed")

    with patch.object(sio, "emit", side_effect=fail):
        with pytest.raises(RuntimeError, match="broadcast failed"):
            await handler("sid-fail", {"message": "boom"})
