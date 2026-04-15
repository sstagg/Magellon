"""Tests for the P9 cancellation primitives.

The service is two unrelated functions that happen to share a file
because operators reach for them together. We test them apart and
mock the boundary in each case (pika for purge, the docker SDK for
kill) — neither external dependency is available in CI.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from services import cancellation_service


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

class _FakeRmqSettings:
    """Minimum duck-type the service needs from rabbitmq_settings."""
    HOST_NAME = "localhost"
    USER_NAME = "rabbit"
    PASSWORD = "behd1d2"


@pytest.fixture
def rmq_settings():
    return _FakeRmqSettings()


def _make_pika_connection(message_count: int):
    """Build a fake pika BlockingConnection whose passive declare
    returns ``message_count``. Returns (connection, channel) so the
    test can assert on either."""
    method_frame = MagicMock()
    method_frame.method.message_count = message_count

    channel = MagicMock()
    channel.queue_declare.return_value = method_frame

    connection = MagicMock()
    connection.channel.return_value = channel
    connection.is_closed = False
    return connection, channel


# ---------------------------------------------------------------------------
# purge_queue
# ---------------------------------------------------------------------------

def test_purge_queue_returns_message_count_and_purges(rmq_settings):
    """Happy path: passive declare reports N pending, purge runs, and
    the function returns N. The count is what the operator audit log
    records as 'cancelled N tasks', so it must be the pre-purge value
    not a post-purge re-read."""
    connection, channel = _make_pika_connection(message_count=7)
    with patch.object(cancellation_service.pika, "BlockingConnection",
                      return_value=connection) as mock_conn:
        result = cancellation_service.purge_queue(rmq_settings, "ctf_tasks_queue")

    assert result == 7
    channel.queue_declare.assert_called_once_with(
        queue="ctf_tasks_queue", passive=True
    )
    channel.queue_purge.assert_called_once_with(queue="ctf_tasks_queue")
    mock_conn.assert_called_once()
    connection.close.assert_called_once()


def test_purge_queue_raises_when_queue_missing(rmq_settings):
    """passive=True is the contract — declaring a non-existent queue
    must surface as an error so a typo'd cancel doesn't silently
    pretend success."""
    connection, channel = _make_pika_connection(message_count=0)
    channel.queue_declare.side_effect = RuntimeError("NOT_FOUND - no queue 'ghost'")

    with patch.object(cancellation_service.pika, "BlockingConnection",
                      return_value=connection):
        with pytest.raises(RuntimeError, match="NOT_FOUND"):
            cancellation_service.purge_queue(rmq_settings, "ghost")

    # Connection should still be closed (finally block).
    connection.close.assert_called_once()


def test_purge_queue_closes_connection_on_purge_failure(rmq_settings):
    """If queue_purge itself raises, the finally must still run —
    leaking pika connections in an admin path would eventually starve
    the broker."""
    connection, channel = _make_pika_connection(message_count=3)
    channel.queue_purge.side_effect = RuntimeError("broker hiccup")

    with patch.object(cancellation_service.pika, "BlockingConnection",
                      return_value=connection):
        with pytest.raises(RuntimeError, match="broker hiccup"):
            cancellation_service.purge_queue(rmq_settings, "ctf_tasks_queue")

    connection.close.assert_called_once()


# ---------------------------------------------------------------------------
# purge_queues
# ---------------------------------------------------------------------------

def test_purge_queues_returns_per_queue_counts(rmq_settings):
    """Operator action over N queues returns N counts so the UI can
    show 'cancelled X / Y / Z' rather than one opaque total."""
    with patch.object(cancellation_service, "purge_queue",
                      side_effect=[4, 0, 11]) as mock:
        out = cancellation_service.purge_queues(
            rmq_settings, ["ctf_tasks_queue", "fft_tasks_queue", "motioncor_tasks_queue"]
        )

    assert out == {
        "ctf_tasks_queue": 4,
        "fft_tasks_queue": 0,
        "motioncor_tasks_queue": 11,
    }
    assert mock.call_count == 3


def test_purge_queues_records_individual_failures_as_minus_one(rmq_settings):
    """Partial success matters: one bad queue can't block the others
    in a 'cancel everything' sweep. -1 sentinel keeps the response
    shape uniform without losing the information that something broke."""
    def fake(_settings, q):
        if q == "broken":
            raise RuntimeError("missing queue")
        return 5

    with patch.object(cancellation_service, "purge_queue", side_effect=fake):
        out = cancellation_service.purge_queues(
            rmq_settings, ["ctf_tasks_queue", "broken", "fft_tasks_queue"]
        )

    assert out == {
        "ctf_tasks_queue": 5,
        "broken": -1,
        "fft_tasks_queue": 5,
    }


def test_purge_queues_empty_list_returns_empty_dict(rmq_settings):
    """Edge case — no queues to purge is a no-op, not a 4xx. The
    HTTP layer enforces non-empty input."""
    with patch.object(cancellation_service, "purge_queue") as mock:
        out = cancellation_service.purge_queues(rmq_settings, [])
    assert out == {}
    mock.assert_not_called()


# ---------------------------------------------------------------------------
# kill_plugin_container
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_docker_module(monkeypatch):
    """Inject a fake ``docker`` module so the lazy import inside the
    service resolves to our mock without requiring the real package."""
    fake = types.ModuleType("docker")
    fake.from_env = MagicMock()
    fake.DockerClient = MagicMock()
    monkeypatch.setitem(sys.modules, "docker", fake)
    return fake


def test_kill_plugin_container_kills_by_name(fake_docker_module):
    """Container is looked up by name (operator-supplied) and killed
    with SIGKILL by default. The returned dict is what the controller
    echoes back to the caller."""
    container = MagicMock()
    container.id = "abc123"
    client = MagicMock()
    client.containers.get.return_value = container
    fake_docker_module.from_env.return_value = client

    result = cancellation_service.kill_plugin_container("ctf-plugin-1")

    client.containers.get.assert_called_once_with("ctf-plugin-1")
    container.kill.assert_called_once_with(signal="SIGKILL")
    assert result == {
        "container_name": "ctf-plugin-1",
        "id": "abc123",
        "signal": "SIGKILL",
        "status": "killed",
    }
    client.close.assert_called_once()


def test_kill_plugin_container_honours_signal_override(fake_docker_module):
    """SIGTERM is for the rare 'let it clean up' kill — we don't want
    the default to silently win when the operator asks for something
    else."""
    container = MagicMock()
    container.id = "xyz"
    client = MagicMock()
    client.containers.get.return_value = container
    fake_docker_module.from_env.return_value = client

    result = cancellation_service.kill_plugin_container(
        "motioncor-plugin-2", signal="SIGTERM"
    )

    container.kill.assert_called_once_with(signal="SIGTERM")
    assert result["signal"] == "SIGTERM"


def test_kill_plugin_container_uses_docker_url_when_provided(fake_docker_module):
    """``docker_url`` overrides ``from_env`` — needed for a remote
    docker host (operator's box → plugin host over TCP)."""
    container = MagicMock()
    container.id = "xyz"
    client = MagicMock()
    client.containers.get.return_value = container
    fake_docker_module.DockerClient.return_value = client

    cancellation_service.kill_plugin_container(
        "ctf-plugin-1", docker_url="tcp://10.0.0.5:2375"
    )

    fake_docker_module.DockerClient.assert_called_once_with(base_url="tcp://10.0.0.5:2375")
    fake_docker_module.from_env.assert_not_called()


def test_kill_plugin_container_propagates_lookup_failure(fake_docker_module):
    """Container-not-found must bubble up — silently succeeding here
    would be the worst outcome for an operator hitting cancel."""
    client = MagicMock()
    client.containers.get.side_effect = RuntimeError("No such container: ghost")
    fake_docker_module.from_env.return_value = client

    with pytest.raises(RuntimeError, match="No such container"):
        cancellation_service.kill_plugin_container("ghost")

    client.close.assert_called_once()
