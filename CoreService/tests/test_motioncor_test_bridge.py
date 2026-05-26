"""MotionCor test bridge regression coverage.

The MotionCor test path is legacy UI plumbing, but it is still mounted
under ``/web``. These tests keep it from silently breaking when shared
RabbitMQ helpers move in the SDK.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4


def test_motioncor_test_modules_import_sdk_rabbitmq_client():
    import core.motioncor_test_result_processor as processor
    import services.motioncor_test_service as service

    expected = "magellon_sdk.bus.binders.rmq._client"
    assert service.RabbitmqClient.__module__ == expected
    assert processor.RabbitmqClient.__module__ == expected


def test_motioncor_test_publish_uses_configured_queue_and_closes(monkeypatch):
    import services.motioncor_test_service as service

    monkeypatch.setattr(
        service.app_settings.rabbitmq_settings,
        "MOTIONCOR_TEST_QUEUE_NAME",
        "motioncor_test_tasks_queue",
        raising=False,
    )

    calls: list[tuple] = []

    class FakeRabbitmqClient:
        def __init__(self, settings):
            calls.append(("init", settings))

        def connect(self):
            calls.append(("connect",))

        def publish_message(self, message, queue_name):
            calls.append(("publish", json.loads(message), queue_name))

        def close_connection(self):
            calls.append(("close",))

    monkeypatch.setattr(service, "RabbitmqClient", FakeRabbitmqClient)
    task_id = uuid4()
    task = service.MotioncorTestTaskManager.create_test_task(
        task_id=task_id,
        image_path="/gpfs/test/movie.mrc",
        gain_path="/gpfs/test/gain.mrc",
        defects_path=None,
        session_name="test-session",
        task_params={"PixSize": 1.0},
        motioncor_settings={"FtBin": 2},
    )

    assert service.MotioncorTestTaskManager.publish_task_to_queue(task) is True

    assert calls[0][0] == "init"
    assert ("connect",) in calls
    publish = next(call for call in calls if call[0] == "publish")
    assert publish[1]["id"] == str(task_id)
    assert publish[2] == "motioncor_test_tasks_queue"
    assert calls[-1] == ("close",)


def test_motioncor_test_result_processor_broadcasts_and_acks(monkeypatch):
    import core.motioncor_test_result_processor as processor

    sent: list[tuple[str, dict]] = []

    async def fake_broadcast(task_id, message):
        sent.append((task_id, message))

    monkeypatch.setattr(processor, "broadcast_to_task_connections", fake_broadcast)
    channel = SimpleNamespace(
        acked=[],
        nacked=[],
        basic_ack=lambda delivery_tag: channel.acked.append(delivery_tag),
        basic_nack=lambda delivery_tag, requeue: channel.nacked.append(
            (delivery_tag, requeue)
        ),
    )
    method = SimpleNamespace(delivery_tag="tag-1")
    body = json.dumps({
        "task_id": "task-123",
        "code": 200,
        "message": "ok",
        "output_files": ["/gpfs/out.mrc"],
    }).encode("utf-8")

    processor.process_result_message(channel, method, None, body)

    assert channel.acked == ["tag-1"]
    assert channel.nacked == []
    assert sent[0][0] == "task-123"
    assert sent[0][1]["type"] == "result"
    assert sent[0][1]["status"] == "completed"


def test_motioncor_test_result_processor_nacks_invalid_json():
    import core.motioncor_test_result_processor as processor

    channel = SimpleNamespace(
        acked=[],
        nacked=[],
        basic_ack=lambda delivery_tag: channel.acked.append(delivery_tag),
        basic_nack=lambda delivery_tag, requeue: channel.nacked.append(
            (delivery_tag, requeue)
        ),
    )
    method = SimpleNamespace(delivery_tag="tag-2")

    processor.process_result_message(channel, method, None, b"{not-json")

    assert channel.acked == []
    assert channel.nacked == [("tag-2", False)]
