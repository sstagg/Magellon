"""Plugin-settings-bound publish helpers.

Wraps :func:`magellon_sdk.messaging.publish_message_to_queue` with this
plugin's :class:`AppSettingsSingleton` so callers don't have to thread
RMQ settings through every call site. After the MB4.3 cutover the
broker runner publishes results via the bus directly; these helpers
remain for the legacy HTTP ``/execute`` path, the test queue's
out-publish, and the debug-queue emits inside ``do_motioncor``.
"""
from pydantic import BaseModel

from magellon_sdk.messaging import publish_message_to_queue as _sdk_publish
from magellon_sdk.models import TaskDto, TaskResultDto

from core.settings import AppSettingsSingleton


def publish_message_to_queue(message: BaseModel, queue_name: str) -> bool:
    return _sdk_publish(
        message,
        queue_name,
        rabbitmq_settings=AppSettingsSingleton.get_instance().rabbitmq_settings,
    )


def push_result_to_out_queue(result: TaskResultDto):
    return publish_message_to_queue(
        result, AppSettingsSingleton.get_instance().rabbitmq_settings.OUT_QUEUE_NAME
    )


def push_task_to_task_queue(task: TaskDto):
    return publish_message_to_queue(
        task, AppSettingsSingleton.get_instance().rabbitmq_settings.QUEUE_NAME
    )


def push_info_to_debug_queue(info: BaseModel):
    return publish_message_to_queue(info, "debug_queue")
