"""Tests for :class:`LocalDockerExecutor`.

Docker is not assumed to be available in the test environment. The
executor's ``process_runner`` seam is replaced with a fake that records
argv and returns canned ``(rc, stdout, stderr)`` tuples — that's what
lets us pin the docker CLI argv shape and the success / failure paths
without any actual containerization.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pytest

from magellon_sdk.executor import ExecutorSpec
from magellon_sdk.executor.impls import ExecutionFailed, LocalDockerExecutor
from magellon_sdk.progress import NullReporter


class FakeRunner:
    """Records argv per invocation; returns the next queued response."""

    def __init__(self, responses: List[Tuple[int, bytes, bytes]]):
        self._responses = list(responses)
        self.calls: List[List[str]] = []

    async def __call__(
        self,
        argv: List[str],
        *,
        env: Optional[Mapping[str, str]] = None,
    ) -> Tuple[int, bytes, bytes]:
        self.calls.append(list(argv))
        if not self._responses:
            raise AssertionError(f"fake runner exhausted at call {argv!r}")
        return self._responses.pop(0)


def _spec(**config: Any) -> ExecutorSpec:
    return ExecutorSpec(kind="localdocker", config=config)


@pytest.mark.asyncio
async def test_submit_emits_expected_docker_run_argv(tmp_path: Path):
    runner = FakeRunner([(0, b"deadbeefcafe\n", b"")])
    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="ctf/ctffind",
        input_payload={"image_path": "/data/x.mrc"},
        spec=_spec(
            image="magellon/ctf:latest",
            command=["python", "-m", "ctf_runner", "--in", "{payload}", "--out", "{result}"],
            gpus="all",
            mounts=["/scratch:/scratch:ro"],
            env={"DEBUG": "1"},
        ),
        reporter=NullReporter(),
    )

    assert handle.executor_kind == "localdocker"
    assert handle.model_dump()["container_id"] == "deadbeefcafe"

    argv = runner.calls[0]
    assert argv[:3] == ["docker", "run", "-d"]
    assert "--gpus" in argv and "all" in argv
    assert "--name" in argv
    container_name = argv[argv.index("--name") + 1]
    assert container_name.startswith("magellon-")

    # Bind-mount of run_dir at /work plus the explicit extra.
    assert any(":/work" in tok for tok in argv)
    assert "/scratch:/scratch:ro" in argv

    # Env var passed through.
    assert "DEBUG=1" in argv

    # Image precedes the in-container command, and placeholders are
    # rewritten to /work paths.
    image_idx = argv.index("magellon/ctf:latest")
    tail = argv[image_idx + 1:]
    assert tail == [
        "python", "-m", "ctf_runner",
        "--in", "/work/input.json",
        "--out", "/work/result.json",
    ]

    # Input payload was materialized in the run dir.
    run_dir = Path(handle.model_dump()["run_dir"])
    assert json.loads((run_dir / "input.json").read_text()) == {"image_path": "/data/x.mrc"}


@pytest.mark.asyncio
async def test_await_result_reads_result_json_on_success(tmp_path: Path):
    runner = FakeRunner([
        (0, b"cid123\n", b""),         # docker run -d
        (0, b"0\n", b""),                # docker wait → exit 0
        (0, b"", b""),                   # docker rm -f
    ])
    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(image="img"),
        reporter=NullReporter(),
    )

    # The container would have written this; we fake it on the host since
    # run_dir is bind-mounted in real deployments.
    Path(handle.model_dump()["result_path"]).write_text(json.dumps({"ok": True}))

    out = await ex.await_result(handle)
    assert out == {"ok": True}

    # docker wait + docker rm -f were called.
    assert runner.calls[1][:2] == ["docker", "wait"]
    assert runner.calls[2][:3] == ["docker", "rm", "-f"]


@pytest.mark.asyncio
async def test_await_result_failure_collects_log_tail(tmp_path: Path):
    runner = FakeRunner([
        (0, b"cid456\n", b""),                # run
        (0, b"137\n", b""),                    # wait — non-zero exit
        (0, b"OOM killed\nexit\n", b""),       # logs
        (0, b"", b""),                         # rm
    ])
    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(image="img"),
        reporter=NullReporter(),
    )

    with pytest.raises(ExecutionFailed) as exc:
        await ex.await_result(handle)
    assert exc.value.reason == "container-exit-137"
    assert "OOM killed" in exc.value.log_tail


@pytest.mark.asyncio
async def test_docker_run_failure_surfaces_stderr(tmp_path: Path):
    runner = FakeRunner([
        (125, b"", b"Error response from daemon: No such image: nope:latest\n"),
    ])
    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=runner)

    with pytest.raises(ExecutionFailed) as exc:
        await ex.submit(
            plugin_id="x",
            input_payload={},
            spec=_spec(image="nope:latest"),
            reporter=NullReporter(),
        )
    assert exc.value.reason == "docker-run-125"
    assert "No such image" in exc.value.log_tail


@pytest.mark.asyncio
async def test_cancel_hits_docker_kill_then_rm(tmp_path: Path):
    runner = FakeRunner([
        (0, b"cid789\n", b""),    # run
        (0, b"", b""),              # kill
        (0, b"", b""),              # rm
    ])
    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(image="img"),
        reporter=NullReporter(),
    )

    await ex.cancel(handle)
    assert runner.calls[1][:2] == ["docker", "kill"]
    assert runner.calls[1][2] == "cid789"
    assert runner.calls[2][:3] == ["docker", "rm", "-f"]


@pytest.mark.asyncio
async def test_missing_image_raises(tmp_path: Path):
    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=FakeRunner([]))
    with pytest.raises(ValueError, match="image"):
        await ex.submit(
            plugin_id="x",
            input_payload={},
            spec=ExecutorSpec(kind="localdocker"),
            reporter=NullReporter(),
        )


@pytest.mark.asyncio
async def test_handle_without_container_id_raises(tmp_path: Path):
    from magellon_sdk.executor import ExecutionHandle
    from magellon_sdk.executor.impls import ExecutionNotFound

    ex = LocalDockerExecutor(work_dir=tmp_path, process_runner=FakeRunner([]))
    stray = ExecutionHandle(executor_kind="localdocker", execution_id="zzz")

    with pytest.raises(ExecutionNotFound):
        await ex.await_result(stray)
