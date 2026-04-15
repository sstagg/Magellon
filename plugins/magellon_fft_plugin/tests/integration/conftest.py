"""Session-scoped broker fixtures for FFT plugin integration tests.

Spins up RabbitMQ and NATS (with JetStream) via testcontainers so the
test owns its infra — no reliance on a pre-running ``docker compose``.
Skips the whole integration module if Docker isn't reachable so the
test suite stays runnable on machines without Docker Desktop.

Settings for the FFT plugin are injected once at session start via
:func:`AppSettingsSingleton.update_settings_from_yaml`. That has to
happen *before* ``core.rabbitmq_consumer_engine`` is imported because
that module captures ``rabbitmq_settings`` at module-load time.
"""
from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path
from typing import Iterator

import pytest

# Make the FFT plugin importable as ``core.*`` / ``service.*`` —
# matches how the plugin is run in production (cwd == plugin root).
_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.integration_brokers


@pytest.fixture(scope="session")
def _docker_required() -> None:
    if not _docker_available():
        pytest.skip("Docker not reachable — integration brokers unavailable")
    # Ryuk's reaper container fails to expose its port on Windows
    # docker-desktop setups. The fixtures stop containers explicitly
    # in their teardown, so the reaper isn't load-bearing here.
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")


@pytest.fixture(scope="session")
def rmq_container(_docker_required) -> Iterator[dict]:
    """Start RabbitMQ on an ephemeral host port and yield connection info."""
    from testcontainers.rabbitmq import RabbitMqContainer

    container = RabbitMqContainer("rabbitmq:3.13-management-alpine")
    container.start()
    try:
        params = container.get_connection_params()
        yield {
            "host": params.host,
            "port": params.port,
            "username": "guest",
            "password": "guest",
            "vhost": "/",
        }
    finally:
        container.stop()


@pytest.fixture(scope="session")
def nats_container(_docker_required) -> Iterator[dict]:
    """Start NATS with JetStream enabled and yield ``broker_url``."""
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    container = (
        DockerContainer("nats:2.10-alpine")
        .with_command("-js")
        .with_exposed_ports(4222)
    )
    container.start()
    try:
        wait_for_logs(container, "Server is ready", timeout=20)
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(4222))
        yield {"host": host, "port": port, "url": f"nats://{host}:{port}"}
    finally:
        container.stop()


def _wait_for_rmq(host: str, port: int, deadline: float = 30.0) -> None:
    """Poll until the RMQ TCP port accepts connections."""
    end = time.monotonic() + deadline
    last_err: Exception | None = None
    while time.monotonic() < end:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError as exc:
            last_err = exc
            time.sleep(0.5)
    raise RuntimeError(f"RMQ at {host}:{port} not reachable: {last_err}")


@pytest.fixture(scope="session")
def configured_plugin(rmq_container, nats_container) -> Iterator[dict]:
    """Inject broker URLs into the plugin's AppSettings singleton + env.

    Must run before any plugin module that captures settings at
    import time. Yields the same dict the broker fixtures returned,
    plus the queue / stream names the test will use.
    """
    _wait_for_rmq(rmq_container["host"], rmq_container["port"])

    yaml_blob = f"""
ENV_TYPE: development
LOCAL_IP_ADDRESS: 127.0.0.1
PORT_NUMBER: 0

REPLACE_TYPE: none
REPLACE_PATTERN: ''
REPLACE_WITH: ''

JOBS_DIR: ''
HOST_JOBS_DIR: ''

consul_settings:
  CONSUL_HOST: ''
  CONSUL_PORT: 0

database_settings: {{}}

rabbitmq_settings:
  HOST_NAME: {rmq_container['host']}
  PORT: {rmq_container['port']}
  USER_NAME: {rmq_container['username']}
  PASSWORD: {rmq_container['password']}
  VIRTUAL_HOST: '/'
  SSL_ENABLED: false
  CONNECTION_TIMEOUT: 30
  PREFETCH_COUNT: 10
  QUEUE_NAME: fft_tasks_queue
  OUT_QUEUE_NAME: fft_out_tasks_queue
""".strip()

    from core.settings import AppSettingsSingleton

    AppSettingsSingleton.update_settings_from_yaml(yaml_blob)

    os.environ["MAGELLON_STEP_EVENTS_ENABLED"] = "1"
    os.environ["MAGELLON_STEP_EVENTS_RMQ"] = "0"  # NATS-only keeps the assertion model simple
    os.environ["NATS_URL"] = nats_container["url"]
    os.environ["NATS_STEP_EVENTS_STREAM"] = "MAGELLON_STEP_EVENTS"
    os.environ["NATS_STEP_EVENTS_SUBJECTS"] = "magellon.job.*.step.*"

    info = {
        "rmq": rmq_container,
        "nats": nats_container,
        "queue_name": "fft_tasks_queue",
        "stream": "MAGELLON_STEP_EVENTS",
        "subjects": "magellon.job.*.step.*",
    }
    yield info
