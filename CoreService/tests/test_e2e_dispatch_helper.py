from __future__ import annotations

import json
import uuid

from tests.integration._e2e_helpers.dispatch import (
    _settings_from_rmq_url,
    build_fft_task_message,
    dispatch_fft_task_via_rmq,
)


def test_settings_from_rmq_url_maps_sdk_client_fields():
    settings = _settings_from_rmq_url(
        "amqp://rabbit:behd%211d2@rabbitmq.local:5673/magellon"
    )

    assert settings.HOST_NAME == "rabbitmq.local"
    assert settings.PORT == 5673
    assert settings.USER_NAME == "rabbit"
    assert settings.PASSWORD == "behd!1d2"
    assert settings.VIRTUAL_HOST == "magellon"


def test_dispatch_fft_task_via_rmq_publishes_raw_task_message(monkeypatch):
    calls = []

    class FakeRabbitmqClient:
        def __init__(self, settings):
            self.settings = settings

        def connect(self):
            calls.append(("connect", self.settings.HOST_NAME, self.settings.PORT))

        def publish_message(self, message, queue_name=None):
            calls.append(("publish", queue_name, json.loads(message)))

        def close_connection(self):
            calls.append(("close",))

    monkeypatch.setattr(
        "magellon_sdk.bus.binders.rmq._client.RabbitmqClient",
        FakeRabbitmqClient,
    )

    task = build_fft_task_message(
        job_id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        image_path="/gpfs/in.mrc",
        target_path="/gpfs/out",
        image_id=uuid.uuid4(),
        image_name="in.mrc",
    )

    dispatch_fft_task_via_rmq(
        task,
        rmq_url="amqp://rabbit:behd1d2@127.0.0.1:5672/",
        queue_name="fft-test",
    )

    assert calls[0] == ("connect", "127.0.0.1", 5672)
    assert calls[1] == ("publish", "fft-test", task)
    assert calls[2] == ("close",)
