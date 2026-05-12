"""Tests for :class:`LocalProcessExecutor`.

Uses a real subprocess (``sys.executable -c '...'``) so the asyncio
process lifecycle gets actually exercised. No mocks for the happy path.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from magellon_sdk.executor import ExecutorSpec
from magellon_sdk.executor.impls import ExecutionFailed, LocalProcessExecutor
from magellon_sdk.progress import NullReporter


# A tiny Python program: read input.json, write {"sum": x + y} to result.json.
HAPPY_SCRIPT = (
    "import json, sys, pathlib; "
    "p = pathlib.Path(sys.argv[1]); "
    "r = pathlib.Path(sys.argv[2]); "
    "data = json.loads(p.read_text()); "
    "r.write_text(json.dumps({'sum': data['x'] + data['y']}))"
)


def _spec(command, **config):
    return ExecutorSpec(kind="localprocess", config={"command": command, **config})


@pytest.mark.asyncio
async def test_happy_path_round_trip(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    spec = _spec([sys.executable, "-c", HAPPY_SCRIPT, "{payload}", "{result}"])

    handle = await ex.submit(
        plugin_id="ctf/ctffind",
        input_payload={"x": 2, "y": 3},
        spec=spec,
        reporter=NullReporter(),
    )

    assert handle.executor_kind == "localprocess"
    # ExecutionHandle allows extra fields; the impl-specific PID is exposed.
    assert handle.model_dump().get("pid")

    result = await ex.await_result(handle)
    assert result == {"sum": 5}

    # Input was materialized in the run dir.
    run_dir = Path(handle.model_dump()["run_dir"])
    assert (run_dir / "input.json").exists()
    assert json.loads((run_dir / "input.json").read_text()) == {"x": 2, "y": 3}


@pytest.mark.asyncio
async def test_nonzero_exit_raises_with_log_tail(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    spec = _spec(
        [sys.executable, "-c", "import sys; sys.stderr.write('boom-line\\n'); sys.exit(7)"]
    )

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=spec,
        reporter=NullReporter(),
    )

    with pytest.raises(ExecutionFailed) as exc:
        await ex.await_result(handle)
    assert "exit-7" in str(exc.value)
    assert "boom-line" in str(exc.value)


@pytest.mark.asyncio
async def test_exit_zero_but_missing_result(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    spec = _spec([sys.executable, "-c", "pass"])

    handle = await ex.submit(plugin_id="x", input_payload={}, spec=spec, reporter=NullReporter())

    with pytest.raises(ExecutionFailed) as exc:
        await ex.await_result(handle)
    assert exc.value.reason == "missing-result"


@pytest.mark.asyncio
async def test_cancel_terminates_running_process(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    # Sleeper that would otherwise sit for 30s.
    spec = _spec([sys.executable, "-c", "import time; time.sleep(30)"])

    handle = await ex.submit(plugin_id="x", input_payload={}, spec=spec, reporter=NullReporter())
    await ex.cancel(handle)

    # await_result should return quickly with non-zero exit
    with pytest.raises(ExecutionFailed):
        await asyncio.wait_for(ex.await_result(handle), timeout=10)


@pytest.mark.asyncio
async def test_cancel_after_completion_is_idempotent(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    spec = _spec([sys.executable, "-c", HAPPY_SCRIPT, "{payload}", "{result}"])

    handle = await ex.submit(
        plugin_id="x",
        input_payload={"x": 1, "y": 1},
        spec=spec,
        reporter=NullReporter(),
    )
    await ex.await_result(handle)
    # Should not raise — process already exited.
    await ex.cancel(handle)


@pytest.mark.asyncio
async def test_missing_command_raises(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    with pytest.raises(ValueError, match="command"):
        await ex.submit(
            plugin_id="x",
            input_payload={},
            spec=ExecutorSpec(kind="localprocess"),
            reporter=NullReporter(),
        )


@pytest.mark.asyncio
async def test_exec_not_found_raises(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    spec = _spec(["this-binary-definitely-does-not-exist-zzz"])

    with pytest.raises(ExecutionFailed) as exc:
        await ex.submit(plugin_id="x", input_payload={}, spec=spec, reporter=NullReporter())
    assert exc.value.reason == "exec-not-found"


@pytest.mark.asyncio
async def test_timeout_propagates(tmp_path: Path):
    ex = LocalProcessExecutor(work_dir=tmp_path)
    spec = _spec([sys.executable, "-c", "import time; time.sleep(30)"])

    handle = await ex.submit(plugin_id="x", input_payload={}, spec=spec, reporter=NullReporter())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await ex.await_result(handle, timeout_s=0.2)
    finally:
        await ex.cancel(handle)
