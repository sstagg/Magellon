"""Contract tests for the executor protocol stub.

No concrete executor ships at 0.1.0 — these tests just pin that a
faithful implementation satisfies the Protocol at runtime, so later
concrete executors (LocalProcess, LocalDocker, RunPod, Kubernetes) have
a green starting point.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from magellon_sdk.executor import Executor, ExecutionHandle, ExecutorSpec
from magellon_sdk.progress import NullReporter, ProgressReporter


class FakeLocalExecutor:
    """Minimal in-memory executor used only to prove the Protocol binds."""

    kind = "fake"

    def __init__(self) -> None:
        self._results: Dict[str, Dict[str, Any]] = {}

    async def submit(
        self,
        *,
        plugin_id: str,
        input_payload: Dict[str, Any],
        spec: ExecutorSpec,
        reporter: ProgressReporter,
    ) -> ExecutionHandle:
        execution_id = f"exec-{plugin_id}-{len(self._results)}"
        reporter.report(100, "done")
        self._results[execution_id] = {"plugin_id": plugin_id, "input": input_payload}
        return ExecutionHandle(executor_kind=self.kind, execution_id=execution_id)

    async def await_result(
        self,
        handle: ExecutionHandle,
        *,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        return self._results[handle.execution_id]

    async def cancel(self, handle: ExecutionHandle) -> None:
        self._results.pop(handle.execution_id, None)


def test_protocol_runtime_checkable():
    assert isinstance(FakeLocalExecutor(), Executor)


def test_executor_spec_round_trip():
    spec = ExecutorSpec(kind="runpod", config={"endpoint_id": "abc", "gpu_count": 1})
    restored = ExecutorSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec


def test_execution_handle_allows_extra_fields():
    """Concrete executors attach impl-specific ids (container_id, pod
    name, ...) via ``extra`` — the base type must not strip them."""
    h = ExecutionHandle.model_validate(
        {
            "executor_kind": "localdocker",
            "execution_id": "e1",
            "container_id": "deadbeef",
        }
    )
    assert h.model_dump().get("container_id") == "deadbeef"


@pytest.mark.asyncio
async def test_fake_executor_submit_await_cancel():
    ex = FakeLocalExecutor()
    spec = ExecutorSpec(kind="fake")
    h = await ex.submit(
        plugin_id="ctf/ctffind",
        input_payload={"n": 1},
        spec=spec,
        reporter=NullReporter(),
    )
    assert h.executor_kind == "fake"
    out = await ex.await_result(h)
    assert out["plugin_id"] == "ctf/ctffind"
    await ex.cancel(h)  # idempotent no-op after completion
