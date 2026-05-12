"""Shared fixtures for the integration test wave (Phases 0–4 e2e).

All fixtures here are opt-in by name — adding them to this file doesn't
affect the pre-existing ``test_fft_full_stack_e2e.py`` /
``test_e2e_seam.py`` / ``test_nats_pubsub.py`` tests, which use their
own setup paths.

The new tests (test_install_lifecycle_dispatch_e2e.py,
test_sync_path_canonicalization_e2e.py, test_install_from_hub_e2e.py,
test_pause_during_task_e2e.py) declare the fixtures they need and skip
cleanly when the stack isn't up.
"""
from __future__ import annotations

import os
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import pytest


# ---------------------------------------------------------------------------
# Stack readiness
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E2eStack:
    """Connection info for the docker-compose stack.

    All URLs / paths come from env so an operator can repoint at a
    remote stack or a different scratch root without editing tests.
    """

    backend_url: str
    db_url: str
    rmq_url: str
    nats_url: str
    gpfs_host_root: Path
    magellon_home_root: Path
    super_user: str
    super_pass: str


@pytest.fixture(scope="session")
def e2e_stack() -> E2eStack:
    """Gate fixture: skips the test unless ``MAGELLON_E2E_STACK=up``.

    Set this in your shell after ``cd Docker && docker compose up -d``
    finishes. Other env vars default to the dev-stack values from
    Docker/.env, so most tests need only the gate.
    """
    if os.environ.get("MAGELLON_E2E_STACK") != "up":
        pytest.skip(
            "MAGELLON_E2E_STACK is not 'up' — bring up the docker-compose "
            "stack and set the env var before running e2e tests.",
        )
    return E2eStack(
        backend_url=os.environ.get(
            "MAGELLON_BACKEND_URL", "http://127.0.0.1:8000",
        ),
        db_url=os.environ.get(
            "MAGELLON_E2E_DB_URL",
            "mysql+pymysql://root:behd1d2@127.0.0.1:3306/magellon01",
        ),
        rmq_url=os.environ.get(
            "MAGELLON_RMQ_URL", "amqp://guest:guest@127.0.0.1:5672/",
        ),
        nats_url=os.environ.get(
            "MAGELLON_NATS_URL", "nats://127.0.0.1:4222",
        ),
        gpfs_host_root=Path(
            os.environ.get(
                "MAGELLON_GPFS_HOST_PATH", r"C:\temp\magellon\gpfs",
            ),
        ),
        magellon_home_root=Path(
            os.environ.get("MAGELLON_HOME_DIR", r"C:\magellon\home"),
        ),
        super_user=os.environ.get("MAGELLON_E2E_USER", "super"),
        super_pass=os.environ.get("MAGELLON_E2E_PASS", "behd1d2"),
    )


# ---------------------------------------------------------------------------
# httpx clients
# ---------------------------------------------------------------------------


def _login_for_token(stack: E2eStack) -> str:
    """POST /auth/login → bearer token. Lifted from the existing
    test_fft_full_stack_e2e helper so the new tests don't drift."""
    import httpx

    resp = httpx.post(
        f"{stack.backend_url}/auth/login",
        json={"username": stack.super_user, "password": stack.super_pass},
        timeout=10.0,
    )
    assert resp.status_code == 200, (
        f"login failed: {resp.status_code} {resp.text[:300]}"
    )
    token = resp.json().get("access_token")
    assert token, "no access_token in login response"
    return token


@pytest.fixture(scope="session")
def admin_client(e2e_stack: E2eStack):
    """httpx.Client pre-authenticated as the Administrator role.

    All Phase 0–4 endpoints are Administrator-gated (Casbin RBAC), so
    every fixture that drives an admin endpoint needs this. Session-
    scoped so we don't relogin per test.
    """
    import httpx

    token = _login_for_token(e2e_stack)
    with httpx.Client(
        base_url=e2e_stack.backend_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=60.0),
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Mock hub for Test 3
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Reserve and release a free TCP port. There's a tiny race window
    between release and bind, but for a single test process it's a
    non-issue."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class MockHub:
    """Handle returned from the ``mock_hub`` fixture. Tests configure
    what the hub returns by setting ``plugin_json`` and ``archive_bytes``
    before invoking the install-from-hub endpoint."""

    base_url: str
    set_plugin_json: callable  # (plugin_id, payload) -> None
    set_archive: callable      # (filename, bytes) -> None
    set_archive_status: callable  # (code) -> None
    set_plugin_status: callable   # (plugin_id, code) -> None


@pytest.fixture
def mock_hub() -> Iterator[MockHub]:
    """In-process FastAPI mock of the Magellon hub.

    Exposes the two routes the install-from-hub endpoint reads:

      GET  /v1/plugins/{plugin_id}.json
      GET  /assets/plugins/{filename}

    Tests set responses via the ``set_*`` callables on the returned
    handle. Fixture tears down the server cleanly after the test.
    """
    from fastapi import FastAPI, HTTPException, Response
    import uvicorn

    app = FastAPI()
    plugin_payloads: dict[str, dict] = {}
    plugin_statuses: dict[str, int] = {}
    archives: dict[str, bytes] = {}
    archive_status = {"code": 200}

    @app.get("/v1/plugins/{plugin_id}.json")
    def get_plugin(plugin_id: str):
        status = plugin_statuses.get(plugin_id, 200)
        if status != 200:
            raise HTTPException(status_code=status, detail="mock-hub error")
        payload = plugin_payloads.get(plugin_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="not found")
        return payload

    @app.get("/assets/plugins/{filename}")
    def get_archive(filename: str):
        if archive_status["code"] != 200:
            raise HTTPException(
                status_code=archive_status["code"], detail="mock-hub error",
            )
        body = archives.get(filename)
        if body is None:
            raise HTTPException(status_code=404, detail="archive not found")
        return Response(content=body, media_type="application/octet-stream")

    port = _free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the server to start accepting connections.
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.05)
    else:
        server.should_exit = True
        raise RuntimeError("mock hub server did not start within 5s")

    handle = MockHub(
        base_url=f"http://127.0.0.1:{port}",
        set_plugin_json=lambda pid, payload: plugin_payloads.update({pid: payload}),
        set_archive=lambda name, body: archives.update({name: body}),
        set_archive_status=lambda code: archive_status.update({"code": code}),
        set_plugin_status=lambda pid, code: plugin_statuses.update({pid: code}),
    )
    try:
        yield handle
    finally:
        server.should_exit = True
        thread.join(timeout=5.0)


# ---------------------------------------------------------------------------
# Socket.IO step-event collector
# ---------------------------------------------------------------------------


@contextmanager
def collect_step_events(backend_url: str, job_id, *, until_completed: int,
                       timeout: float):
    """Context manager that joins the job's Socket.IO room and records
    every ``step_event`` payload until ``until_completed`` completed
    events arrive (or ``timeout`` elapses).

    Yields a list reference; the test reads it after the context exits.
    The collector runs in a background thread so the test body can
    dispatch tasks without blocking the event loop.

    The asyncio + Socket.IO plumbing mirrors test_fft_full_stack_e2e's
    ``_subscribe_dispatch_drain`` but reshaped as a context manager so
    callers control when to publish.
    """
    import asyncio
    import socketio

    events: list[dict] = []
    completed_count = {"n": 0}
    done = threading.Event()
    started = threading.Event()
    loop_holder: dict = {}

    async def _runner():
        sio = socketio.AsyncClient(reconnection=False)

        @sio.on("step_event")
        async def _on_step(payload):
            events.append(payload)
            if payload.get("type") == "magellon.step.completed":
                completed_count["n"] += 1
                if completed_count["n"] >= until_completed:
                    done.set()

        await sio.connect(backend_url, transports=["websocket"])
        ack = await sio.call("join_job_room", {"job_id": str(job_id)}, timeout=5)
        assert ack and ack.get("ok"), f"join_job_room rejected: {ack}"
        started.set()

        # Park here until the test body signals completion (via done) or
        # the timeout elapses.
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline and not done.is_set():
                await asyncio.sleep(0.1)
        finally:
            try:
                await sio.disconnect()
            except Exception:
                pass

    def _thread_target():
        loop = asyncio.new_event_loop()
        loop_holder["loop"] = loop
        try:
            loop.run_until_complete(_runner())
        finally:
            loop.close()

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()

    # Wait until the subscriber has joined the room before yielding —
    # the test body's first task publish could otherwise race the join.
    assert started.wait(timeout=10.0), (
        "Socket.IO subscriber did not join the job room within 10s"
    )

    try:
        yield events
    finally:
        # Give the collector its full timeout to drain remaining events,
        # then signal done and join the thread.
        done.wait(timeout=timeout)
        thread.join(timeout=5.0)


@pytest.fixture
def step_event_collector(e2e_stack: E2eStack):
    """Returns the ``collect_step_events`` context-manager factory bound
    to the stack's backend URL. Use as::

        with step_event_collector(job_id, until_completed=1, timeout=60) as events:
            ... publish task ...
        # events list is populated
    """
    def factory(job_id, *, until_completed: int, timeout: float):
        return collect_step_events(
            e2e_stack.backend_url, job_id,
            until_completed=until_completed, timeout=timeout,
        )
    return factory


# ---------------------------------------------------------------------------
# .mpn fixture for the centerpiece + pause tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fft_mpn_archive() -> Path:
    """Locate (or build) the FFT plugin .mpn archive.

    Resolution order:
      1. ``MAGELLON_FFT_MPN`` env var — explicit override.
      2. tests/integration/fixtures/fft-<version>.mpn — built locally.
      3. Skip the test with an actionable message.

    We don't auto-build here because pack invokes the SDK CLI which may
    not be on PATH in every dev env; the actionable message tells the
    operator exactly which command to run.
    """
    override = os.environ.get("MAGELLON_FFT_MPN")
    if override:
        path = Path(override)
        if not path.is_file():
            pytest.skip(f"MAGELLON_FFT_MPN={override} does not exist")
        return path

    fixtures_dir = Path(__file__).parent / "fixtures"
    candidates = sorted(fixtures_dir.glob("fft-*.mpn"))
    if candidates:
        # Take the lexicographically last one — for SemVer versions
        # that approximates "newest" well enough for a test fixture.
        return candidates[-1]

    pytest.skip(
        "FFT .mpn fixture not found. Build it with:\n"
        "    scripts/build_fft_mpn.sh\n"
        "or set MAGELLON_FFT_MPN to an existing .mpn path."
    )


@pytest.fixture(scope="session")
def template_picker_mpn_archive() -> Path:
    """Locate (or build) the template-picker plugin .mpn archive.

    Same resolution shape as ``fft_mpn_archive``:
      1. ``MAGELLON_TEMPLATE_PICKER_MPN`` env var — explicit override.
      2. tests/integration/fixtures/template-picker-<version>.mpn —
         built locally.
      3. Skip the test with an actionable message.
    """
    override = os.environ.get("MAGELLON_TEMPLATE_PICKER_MPN")
    if override:
        path = Path(override)
        if not path.is_file():
            pytest.skip(f"MAGELLON_TEMPLATE_PICKER_MPN={override} does not exist")
        return path

    fixtures_dir = Path(__file__).parent / "fixtures"
    candidates = sorted(fixtures_dir.glob("template-picker-*.mpn"))
    if candidates:
        return candidates[-1]

    pytest.skip(
        "template-picker .mpn fixture not found. Build it with:\n"
        "    scripts/build_template_picker_mpn.sh\n"
        "or set MAGELLON_TEMPLATE_PICKER_MPN to an existing .mpn path."
    )


@pytest.fixture(scope="session")
def template_paths(e2e_stack) -> list[str]:
    """The three reference templates the picker uses by default.

    Pre-seeded under ``<gpfs_host_root>/templates/`` per the deploy
    runbook. The picker's manifest defaults to these paths, and the
    e2e test consumes them as the canonical multi-template input.
    Skips if they aren't present so the test isn't silently a no-op.
    """
    seeded = [
        e2e_stack.gpfs_host_root / "templates" / f"origTemplate{i}.mrc"
        for i in (1, 2, 3)
    ]
    missing = [str(p) for p in seeded if not p.is_file()]
    if missing:
        pytest.skip(
            f"Template MRC fixtures missing under {e2e_stack.gpfs_host_root}/"
            f"templates/: {missing}. Stage the three origTemplate*.mrc "
            f"files there before running the template-picker e2e."
        )
    return [str(p).replace("\\", "/") for p in seeded]
