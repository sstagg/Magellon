"""Compatibility shim — pure/file helpers come from the SDK; queue
pushes wire the plugin's settings into the shared publisher.
"""
from pydantic import BaseModel

from core.settings import AppSettingsSingleton
from magellon_sdk.messaging import (  # noqa: F401
    append_json_to_file,
    create_directory,
    custom_replace,
    parse_message_to_task_object,
)
from magellon_sdk.messaging import publish_message_to_queue as _sdk_publish
from magellon_sdk.models import CtfTaskData, TaskDto, TaskResultDto


def extract_task_data_from_object(task_object):
    return CtfTaskData.model_validate(task_object.data)


def parse_json_for_cryoemctftask(message_str):
    return CtfTaskData.model_validate(TaskDto.model_validate_json(message_str).data)


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
