"""Plugin-settings-bound publish helper.

Wraps :func:`magellon_sdk.messaging.publish_message_to_queue` with this
plugin's :class:`AppSettingsSingleton` so callers don't have to thread
RMQ settings through every call site. Used by the integration test
(``tests/integration/test_fft_messaging_e2e.py``); production task
publishing flows through the bus via :class:`PluginBrokerRunner`.
"""
from pydantic import BaseModel

from magellon_sdk.messaging import publish_message_to_queue as _sdk_publish

from core.settings import AppSettingsSingleton


def publish_message_to_queue(message: BaseModel, queue_name: str) -> bool:
    return _sdk_publish(
        message,
        queue_name,
        rabbitmq_settings=AppSettingsSingleton.get_instance().rabbitmq_settings,
    )
