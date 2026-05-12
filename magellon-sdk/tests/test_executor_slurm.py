"""Tests for :class:`SlurmExecutor`.

Slurm is not assumed to be installed. The ``process_runner`` seam is
replaced with a fake that records argv per invocation and returns
canned ``(rc, stdout, stderr)`` tuples — that's how we pin the sbatch
script content, the submit / poll / cancel argv shapes, and the
mapping from Slurm states to success / failure.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

import pytest

from magellon_sdk.executor import ExecutorSpec
from magellon_sdk.executor.impls import ExecutionFailed, SlurmExecutor
from magellon_sdk.progress import NullReporter


class FakeRunner:
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
            raise AssertionError(f"runner exhausted at call {argv!r}")
        return self._responses.pop(0)


def _spec(**config: Any) -> ExecutorSpec:
    return ExecutorSpec(kind="slurm", config=config)


@pytest.mark.asyncio
async def test_submit_writes_sbatch_script_and_returns_jobid(tmp_path: Path):
    runner = FakeRunner([(0, b"50231\n", b"")])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="motioncor/motioncor2",
        input_payload={"image_path": "/gpfs/x.tif"},
        spec=_spec(
            command=["python", "-m", "mc_runner", "--in", "{payload}", "--out", "{result}"],
            partition="cryosparc4",
            cpus=8,
            gpus=2,
            memory="24G",
            time="36:00:00",
            account="lab-grant",
            pre_script=["module load cuda/11.8", "source activate mc"],
            extra_sbatch=["--exclusive"],
        ),
        reporter=NullReporter(),
    )

    assert handle.executor_kind == "slurm"
    assert handle.model_dump()["slurm_job_id"] == "50231"

    # sbatch invocation argv
    argv = runner.calls[0]
    assert argv[0] == "sbatch"
    assert argv[1] == "--parsable"
    script_path = Path(argv[2])
    assert script_path.exists()

    script = script_path.read_text()
    # Shebang + identity
    assert script.startswith("#!/bin/bash")
    assert "--job-name=magellon-motioncor-motioncor2" in script
    # Resource directives
    assert "#SBATCH --partition=cryosparc4" in script
    assert "#SBATCH --cpus-per-task=8" in script
    assert "#SBATCH --mem=24G" in script
    assert "#SBATCH --time=36:00:00" in script
    assert "#SBATCH --account=lab-grant" in script
    assert "#SBATCH --gres=gpu:2" in script
    assert "#SBATCH --exclusive" in script
    # Pre-script lines
    assert "module load cuda/11.8" in script
    assert "source activate mc" in script
    # Body — placeholders resolved, command shell-quoted
    payload_path = Path(handle.model_dump()["run_dir"]) / "input.json"
    result_path = Path(handle.model_dump()["result_path"])
    assert str(payload_path) in script
    assert str(result_path) in script

    # Input payload was materialized.
    assert json.loads(payload_path.read_text()) == {"image_path": "/gpfs/x.tif"}


@pytest.mark.asyncio
async def test_await_result_polls_squeue_then_sacct_and_succeeds(tmp_path: Path):
    runner = FakeRunner([
        (0, b"50000\n", b""),                # sbatch
        (0, b"RUNNING\n", b""),                # squeue
        (0, b"", b""),                          # squeue empty (job gone)
        (0, b"COMPLETED\n", b""),              # sacct
    ])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner, poll_interval_s=0.01)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(command=["true"]),
        reporter=NullReporter(),
    )

    # Container/job would have written this; tests stand in for the
    # shared FS by writing it directly.
    Path(handle.model_dump()["result_path"]).write_text(json.dumps({"done": True}))

    out = await ex.await_result(handle)
    assert out == {"done": True}

    # We expect: sbatch, then at least one squeue poll, then sacct.
    cmds = [c[0] for c in runner.calls]
    assert cmds[0] == "sbatch"
    assert "squeue" in cmds
    assert cmds[-1] == "sacct"


@pytest.mark.asyncio
async def test_await_result_terminal_failure_state(tmp_path: Path):
    runner = FakeRunner([
        (0, b"50001\n", b""),                # sbatch
        (0, b"", b""),                          # squeue empty
        (0, b"FAILED\n", b""),                  # sacct
    ])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner, poll_interval_s=0.01)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(command=["true"]),
        reporter=NullReporter(),
    )
    # Drop a log so the failure tail is non-empty.
    Path(handle.model_dump()["log_path"]).write_text("segfault\n")

    with pytest.raises(ExecutionFailed) as exc:
        await ex.await_result(handle)
    assert exc.value.reason == "FAILED"
    assert "segfault" in exc.value.log_tail


@pytest.mark.asyncio
async def test_sacct_state_with_trailing_text(tmp_path: Path):
    # sacct frequently emits "CANCELLED by 1001" — the impl should
    # take the first token only.
    runner = FakeRunner([
        (0, b"50002\n", b""),                # sbatch
        (0, b"", b""),                          # squeue empty
        (0, b"CANCELLED by 1001\n", b""),       # sacct
    ])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner, poll_interval_s=0.01)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(command=["true"]),
        reporter=NullReporter(),
    )
    with pytest.raises(ExecutionFailed) as exc:
        await ex.await_result(handle)
    assert exc.value.reason == "CANCELLED"


@pytest.mark.asyncio
async def test_sbatch_failure_raises(tmp_path: Path):
    runner = FakeRunner([
        (1, b"", b"sbatch: error: invalid partition specified: nope\n"),
    ])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner)

    with pytest.raises(ExecutionFailed) as exc:
        await ex.submit(
            plugin_id="x",
            input_payload={},
            spec=_spec(command=["true"], partition="nope"),
            reporter=NullReporter(),
        )
    assert exc.value.reason == "sbatch-1"
    assert "invalid partition" in exc.value.log_tail


@pytest.mark.asyncio
async def test_cancel_calls_scancel(tmp_path: Path):
    runner = FakeRunner([
        (0, b"50003\n", b""),                # sbatch
        (0, b"", b""),                          # scancel
    ])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(command=["true"]),
        reporter=NullReporter(),
    )

    await ex.cancel(handle)
    assert runner.calls[-1] == ["scancel", "50003"]


@pytest.mark.asyncio
async def test_parsable_jobid_with_cluster_suffix(tmp_path: Path):
    # `sbatch --parsable` returns "JOBID" or "JOBID;CLUSTER" on
    # multi-cluster sites. The impl must take the first segment.
    runner = FakeRunner([
        (0, b"99887;curie\n", b""),
    ])
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(command=["true"]),
        reporter=NullReporter(),
    )
    assert handle.model_dump()["slurm_job_id"] == "99887"


@pytest.mark.asyncio
async def test_timeout_in_poll_raises(tmp_path: Path):
    # squeue keeps saying RUNNING forever; we should time out.
    forever_running = [(0, b"RUNNING\n", b"")] * 50
    runner = FakeRunner([(0, b"50004\n", b"")] + forever_running)
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=runner, poll_interval_s=0.01)

    handle = await ex.submit(
        plugin_id="x",
        input_payload={},
        spec=_spec(command=["true"]),
        reporter=NullReporter(),
    )
    with pytest.raises(asyncio.TimeoutError):
        await ex.await_result(handle, timeout_s=0.05)


@pytest.mark.asyncio
async def test_missing_command_raises(tmp_path: Path):
    ex = SlurmExecutor(work_dir=tmp_path, process_runner=FakeRunner([]))
    with pytest.raises(ValueError, match="command"):
        await ex.submit(
            plugin_id="x",
            input_payload={},
            spec=ExecutorSpec(kind="slurm"),
            reporter=NullReporter(),
        )
