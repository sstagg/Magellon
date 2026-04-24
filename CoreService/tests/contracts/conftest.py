"""Shared fixtures for plugin-container contract tests (G.2).

Contract tests verify the wire contract each plugin container
exposes: "send this TaskDto shape, get this TaskResultDto shape
back, with provenance stamped". They talk to the live plugin's
HTTP ``/execute`` endpoint rather than going through RMQ — that
avoids racing with CoreService's in-process result consumer and
keeps the test about the plugin's contract, not the bus topology.

Every contract test skips cleanly when the target plugin isn't
running, so running locally (with only a subset of plugins up)
or in CI (with no docker at all) doesn't break the suite.

Closes the "no contract test between CoreService and external
plugin containers" gap called out in ``CURRENT_ARCHITECTURE.md``
§9.
"""
from __future__ import annotations

import os
import socket
from typing import Optional

import pytest


def _plugin_host() -> str:
    """Contract tests target the docker-compose port forward on
    127.0.0.1. Overridable for tests against a remote plugin host."""
    return os.environ.get("MAGELLON_CONTRACT_TEST_HOST", "127.0.0.1")


def _port_from_env(env_key: str, default: int) -> int:
    raw = os.environ.get(env_key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _plugin_reachable(port: int, path: str = "/health", timeout: float = 2.0) -> bool:
    """Quick TCP + HTTP probe of the plugin's health endpoint.

    TCP alone isn't enough: the port could be listening but the
    app not ready. We do a fast HTTP GET and treat any 2xx as live.
    """
    host = _plugin_host()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except Exception:
        return False

    # Optional: if ``httpx`` or ``requests`` is available, validate
    # the HTTP layer. Fall back to "TCP open is good enough" when
    # neither is present — test harness may be minimal.
    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            resp = client.get(f"http://{host}:{port}{path}")
            return 200 <= resp.status_code < 300
    except ImportError:
        pass
    try:
        import requests

        resp = requests.get(f"http://{host}:{port}{path}", timeout=timeout)
        return 200 <= resp.status_code < 300
    except Exception:
        return True  # TCP was enough; let the real call surface HTTP-level errors.


@pytest.fixture(scope="module")
def ctf_plugin_port() -> int:
    """CTF plugin host port. Defaults to the docker-compose .env
    value (8035). Overridable via ``MAGELLON_CTF_PLUGIN_PORT``."""
    return _port_from_env("MAGELLON_CTF_PLUGIN_PORT", 8035)


@pytest.fixture(scope="module")
def motioncor_plugin_port() -> int:
    return _port_from_env("MAGELLON_MOTIONCOR_PLUGIN_PORT", 8036)


@pytest.fixture(scope="module")
def fft_plugin_port() -> int:
    return _port_from_env("MAGELLON_FFT_PLUGIN_PORT", 8037)


@pytest.fixture(scope="module")
def ptolemy_plugin_port() -> int:
    return _port_from_env("MAGELLON_PTOLEMY_PLUGIN_PORT", 8038)


@pytest.fixture(scope="module", autouse=False)
def require_ctf_plugin(ctf_plugin_port: int) -> int:
    """Skip unless the CTF plugin container is reachable on its
    expected port. Returns the port for use by the test body."""
    if not _plugin_reachable(ctf_plugin_port):
        pytest.skip(
            f"CTF plugin not reachable on {_plugin_host()}:{ctf_plugin_port} "
            f"— `docker compose up magellon_ctf_plugin` to run this test, "
            f"or set MAGELLON_CTF_PLUGIN_PORT."
        )
    return ctf_plugin_port


@pytest.fixture(scope="module", autouse=False)
def require_motioncor_plugin(motioncor_plugin_port: int) -> int:
    if not _plugin_reachable(motioncor_plugin_port):
        pytest.skip(
            f"MotionCor plugin not reachable on "
            f"{_plugin_host()}:{motioncor_plugin_port}"
        )
    return motioncor_plugin_port


@pytest.fixture(scope="module", autouse=False)
def require_fft_plugin(fft_plugin_port: int) -> int:
    if not _plugin_reachable(fft_plugin_port):
        pytest.skip(
            f"FFT plugin not reachable on {_plugin_host()}:{fft_plugin_port}"
        )
    return fft_plugin_port


@pytest.fixture(scope="module", autouse=False)
def require_ptolemy_plugin(ptolemy_plugin_port: int) -> int:
    if not _plugin_reachable(ptolemy_plugin_port):
        pytest.skip(
            f"Ptolemy plugin not reachable on {_plugin_host()}:{ptolemy_plugin_port}"
            f" — `docker compose up magellon_ptolemy_plugin` to run this test, "
            f"or set MAGELLON_PTOLEMY_PLUGIN_PORT."
        )
    return ptolemy_plugin_port


__all__ = [
    "require_ctf_plugin",
    "require_fft_plugin",
    "require_motioncor_plugin",
    "require_ptolemy_plugin",
]
