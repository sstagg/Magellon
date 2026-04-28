"""Unit tests for the shared messaging helpers.

The rabbitmq-touching helpers are tested with a stub client so the
tests never touch a real broker.
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from magellon_sdk import messaging
from magellon_sdk.models import TaskMessage, TaskResultMessage


class _DummyPayload(BaseModel):
    x: int
    label: str


def test_create_directory_makes_parent(tmp_path):
    target = tmp_path / "a" / "b" / "file.txt"
    messaging.create_directory(str(target))
    assert (tmp_path / "a" / "b").is_dir()


def test_create_directory_no_parent_is_safe(tmp_path):
    # No parent component in the path — must not raise.
    messaging.create_directory("just_a_file.txt")


def test_custom_replace_none_is_passthrough():
    assert messaging.custom_replace("hello", "none", "", "") == "hello"


def test_custom_replace_standard():
    assert messaging.custom_replace("a/b/c", "standard", "/", "-") == "a-b-c"


def test_custom_replace_regex():
    assert messaging.custom_replace("img001.mrc", "regex", r"\d+", "X") == "imgX.mrc"


def test_custom_replace_invalid_type_raises():
    with pytest.raises(ValueError):
        messaging.custom_replace("x", "bogus", "", "")


def test_append_json_to_file_writes_line(tmp_path):
    target = tmp_path / "log.ndjson"
    ok = messaging.append_json_to_file(str(target), json.dumps({"a": 1}))
    ok2 = messaging.append_json_to_file(str(target), json.dumps({"a": 2}))
    assert ok is True and ok2 is True

    lines = target.read_text().strip().splitlines()
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"a": 2}


def test_append_json_to_file_returns_false_on_error(tmp_path):
    # Directory path (not file) — open("a") raises.
    ok = messaging.append_json_to_file(str(tmp_path), "{}")
    assert ok is False


def test_parse_message_to_task_object_round_trip():
    task = TaskMessage(data={"k": "v"})
    parsed = messaging.parse_message_to_task_object(task.model_dump_json())
    assert parsed.data == {"k": "v"}


def test_parse_message_to_task_result_object_round_trip():
    result = TaskResultMessage(code=200, message="ok")
    parsed = messaging.parse_message_to_task_result_object(result.model_dump_json())
    assert parsed.code == 200
    assert parsed.message == "ok"
    assert parsed.task_id is None
    assert parsed.image_id is None


def test_publish_message_to_queue_success():
    """Post-MB6.2: publish_message_to_queue delegates to bus.tasks.send
    on a TaskRoute.named(queue_name) and returns receipt.ok."""
    from unittest.mock import MagicMock

    from magellon_sdk.bus import PublishReceipt
    from magellon_sdk.bus._facade import get_bus as _get_bus

    bus = MagicMock()
    bus.tasks.send.return_value = PublishReceipt(ok=True, message_id="abc")
    _get_bus.override(bus)
    try:
        ok = messaging.publish_message_to_queue(
            _DummyPayload(x=1, label="hi"), "q.test", rabbitmq_settings=object()
        )
    finally:
        _get_bus.override(None)

    assert ok is True
    assert bus.tasks.send.call_count == 1
    route, envelope = bus.tasks.send.call_args.args
    assert route.subject == "q.test"
    assert envelope.data.x == 1
    assert envelope.data.label == "hi"


def test_publish_message_to_queue_returns_false_on_error():
    """Any exception from the bus path becomes ``False`` — plugin
    helpers treat publish as fire-and-forget."""
    from unittest.mock import MagicMock

    from magellon_sdk.bus._facade import get_bus as _get_bus

    bus = MagicMock()
    bus.tasks.send.side_effect = RuntimeError("broker down")
    _get_bus.override(bus)
    try:
        ok = messaging.publish_message_to_queue(
            _DummyPayload(x=1, label="hi"), "q.test", rabbitmq_settings=object()
        )
    finally:
        _get_bus.override(None)

    assert ok is False


def test_publish_message_to_queue_returns_false_when_receipt_not_ok():
    """A bus receipt with ok=False (e.g. AMQP channel error absorbed by
    the binder) still returns False."""
    from unittest.mock import MagicMock

    from magellon_sdk.bus import PublishReceipt
    from magellon_sdk.bus._facade import get_bus as _get_bus

    bus = MagicMock()
    bus.tasks.send.return_value = PublishReceipt(ok=False, message_id="", error="amqp")
    _get_bus.override(bus)
    try:
        ok = messaging.publish_message_to_queue(
            _DummyPayload(x=1, label="hi"), "q.test", rabbitmq_settings=object()
        )
    finally:
        _get_bus.override(None)

    assert ok is False
