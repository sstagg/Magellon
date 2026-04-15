"""Tests for the unified PluginBrokerRunner harness (P5).

The harness is the only place plugin-loop boilerplate lives now, so
these tests pin the contract every plugin inherits:

  - A valid task is decoded, validated, executed, and a result is
    published with provenance auto-stamped from the manifest.
  - A bad payload is classified via P2's classifier (DLQ for poison,
    REQUEUE for transient).
  - A plugin that fills in its own provenance is *not* overwritten —
    engine wrappers (one PluginBase running gctf vs ctffind) need to
    report different identities than their host class name.
"""
from __future__ import annotations

from typing import Type
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from magellon_sdk.base import PluginBase
from magellon_sdk.errors import PermanentError, RetryableError
from magellon_sdk.models import (
    CTF_TASK,
    PluginInfo,
    TaskDto,
    TaskResultDto,
)
from magellon_sdk.runner import PluginBrokerRunner


# ---------------------------------------------------------------------------
# Test plugin
# ---------------------------------------------------------------------------

class _StubInput(BaseModel):
    image_path: str = ""


class _StubOutput(BaseModel):
    answer: int


class _StubPlugin(PluginBase[_StubInput, _StubOutput]):
    task_category = CTF_TASK

    def __init__(self, *, raise_on_run: Exception | None = None) -> None:
        super().__init__()
        self._raise = raise_on_run

    def get_info(self) -> PluginInfo:
        return PluginInfo(name="stub-plugin", version="0.42.0", developer="test")

    @classmethod
    def input_schema(cls) -> Type[_StubInput]:
        return _StubInput

    @classmethod
    def output_schema(cls) -> Type[_StubOutput]:
        return _StubOutput

    def execute(self, input_data: _StubInput, *, reporter=None) -> _StubOutput:
        if self._raise is not None:
            raise self._raise
        return _StubOutput(answer=42)


def _result_factory(task: TaskDto, output: _StubOutput) -> TaskResultDto:
    return TaskResultDto(
        task_id=task.id,
        job_id=task.job_id,
        code=200,
        message="ok",
        type=task.type,
        output_data={"answer": output.answer},
    )


def _make_task() -> TaskDto:
    return TaskDto(
        id=uuid4(),
        job_id=uuid4(),
        type=CTF_TASK,
        data={"image_path": "/gpfs/x.mrc"},
    )


def _make_runner(plugin: _StubPlugin) -> PluginBrokerRunner:
    return PluginBrokerRunner(
        plugin=plugin,
        settings=MagicMock(),  # never connects in unit tests
        in_queue="ctf_in",
        out_queue="ctf_out",
        result_factory=_result_factory,
    )


# ---------------------------------------------------------------------------
# Process pipeline
# ---------------------------------------------------------------------------

def test_process_returns_result_with_provenance_stamped():
    """A clean run produces a TaskResultDto whose plugin_id /
    plugin_version come from the plugin's own get_info() — that's the
    audit-trail guarantee P4 leans on."""
    runner = _make_runner(_StubPlugin())
    body = _make_task().model_dump_json().encode()

    out_bytes = runner._process(body)

    out = TaskResultDto.model_validate_json(out_bytes)
    assert out.plugin_id == "stub-plugin"
    assert out.plugin_version == "0.42.0"
    assert out.output_data == {"answer": 42}


def test_process_preserves_explicit_provenance_set_by_factory():
    """If the result_factory already filled provenance (engine
    wrapper case), the harness must not clobber it."""
    runner = _make_runner(_StubPlugin())
    runner.result_factory = lambda t, o: TaskResultDto(
        task_id=t.id,
        plugin_id="gctf-2.1",
        plugin_version="2.1.0",
    )
    body = _make_task().model_dump_json().encode()

    out_bytes = runner._process(body)

    out = TaskResultDto.model_validate_json(out_bytes)
    assert out.plugin_id == "gctf-2.1"
    assert out.plugin_version == "2.1.0"


def test_process_validates_input_against_plugin_schema():
    """A task whose data doesn't match the plugin's input_schema must
    raise — preferably *before* the plugin's bespoke logic runs.
    Without this gate every plugin would have to repeat the validation."""

    class _StrictInput(BaseModel):
        required_field: int

    class _StrictPlugin(_StubPlugin):
        @classmethod
        def input_schema(cls):
            return _StrictInput

    runner = _make_runner(_StrictPlugin())
    body = _make_task().model_dump_json().encode()  # data has image_path, no required_field

    with pytest.raises(Exception):  # pydantic ValidationError
        runner._process(body)


# ---------------------------------------------------------------------------
# Broker callback (ack / requeue / DLQ)
# ---------------------------------------------------------------------------

def _ch_method():
    ch = MagicMock()
    method = MagicMock()
    method.delivery_tag = 7
    method.redelivered = False
    return ch, method


def test_callback_acks_and_publishes_on_success():
    runner = _make_runner(_StubPlugin())
    client = MagicMock()
    cb = runner._build_callback(client)
    ch, method = _ch_method()

    cb(ch, method, properties=None, body=_make_task().model_dump_json().encode())

    client.publish_message.assert_called_once()
    published_body = client.publish_message.call_args[0][0]
    assert b'"plugin_id":"stub-plugin"' in published_body
    ch.basic_ack.assert_called_once_with(delivery_tag=7)
    ch.basic_nack.assert_not_called()


def test_callback_dlqs_on_permanent_error():
    """PermanentError → DLQ on first attempt. Plugin signals 'never
    going to work'; the harness must not retry."""
    runner = _make_runner(_StubPlugin(raise_on_run=PermanentError("bad shape")))
    cb = runner._build_callback(MagicMock())
    ch, method = _ch_method()

    cb(ch, method, properties=None, body=_make_task().model_dump_json().encode())

    ch.basic_ack.assert_not_called()
    ch.basic_nack.assert_called_once_with(delivery_tag=7, requeue=False)


def test_callback_requeues_on_retryable_error():
    """RetryableError → REQUEUE regardless of redelivery count, per
    the P2 contract."""
    runner = _make_runner(_StubPlugin(raise_on_run=RetryableError("nfs blip")))
    cb = runner._build_callback(MagicMock())
    ch, method = _ch_method()

    cb(ch, method, properties=None, body=_make_task().model_dump_json().encode())

    ch.basic_ack.assert_not_called()
    ch.basic_nack.assert_called_once_with(delivery_tag=7, requeue=True)


def test_callback_does_not_publish_when_plugin_raises():
    """A failed run must not produce a result on the out-queue —
    publishing a half-baked TaskResultDto would fool the writer."""
    runner = _make_runner(_StubPlugin(raise_on_run=RuntimeError("boom")))
    client = MagicMock()
    cb = runner._build_callback(client)
    ch, method = _ch_method()

    cb(ch, method, properties=None, body=_make_task().model_dump_json().encode())

    client.publish_message.assert_not_called()
