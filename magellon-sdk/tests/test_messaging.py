"""Unit tests for the shared messaging helpers.

The rabbitmq-touching helpers are tested with a stub client so the
tests never touch a real broker.
"""
from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from magellon_sdk import messaging
from magellon_sdk.models import TaskDto, TaskResultDto


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
    task = TaskDto(data={"k": "v"})
    parsed = messaging.parse_message_to_task_object(task.model_dump_json())
    assert parsed.data == {"k": "v"}


def test_parse_message_to_task_result_object_round_trip():
    result = TaskResultDto(code=200, message="ok")
    parsed = messaging.parse_message_to_task_result_object(result.model_dump_json())
    assert parsed.code == 200
    assert parsed.message == "ok"
    assert parsed.task_id is None
    assert parsed.image_id is None


class _StubClient:
    def __init__(self, settings, **_kwargs):
        self.settings = settings
        self.connected = False
        self.closed = False
        self.published = None

    def connect(self):
        self.connected = True

    def publish_message(self, body, queue_name):
        self.published = (body, queue_name)

    def close_connection(self):
        self.closed = True


class _ExplodingClient(_StubClient):
    def publish_message(self, body, queue_name):
        raise RuntimeError("broker down")


def test_publish_message_to_queue_success(monkeypatch):
    created: list = []

    def _factory(settings, **kwargs):
        client = _StubClient(settings, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(messaging, "RabbitmqClient", _factory)

    ok = messaging.publish_message_to_queue(
        _DummyPayload(x=1, label="hi"), "q.test", rabbitmq_settings=object()
    )

    assert ok is True
    [client] = created
    assert client.connected and client.closed
    body, qname = client.published
    assert qname == "q.test"
    assert json.loads(body) == {"x": 1, "label": "hi"}


def test_publish_message_to_queue_closes_on_error(monkeypatch):
    created: list = []

    def _factory(settings, **kwargs):
        client = _ExplodingClient(settings, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(messaging, "RabbitmqClient", _factory)

    ok = messaging.publish_message_to_queue(
        _DummyPayload(x=1, label="hi"), "q.test", rabbitmq_settings=object()
    )

    assert ok is False
    [client] = created
    assert client.closed, "connection must be closed even on publish failure"
