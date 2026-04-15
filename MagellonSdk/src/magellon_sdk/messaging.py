"""Shared message/file helpers used by every plugin's ``core/helper.py``.

The RabbitMQ-touching helpers take ``rabbitmq_settings`` explicitly so
this module stays decoupled from each plugin's ``AppSettingsSingleton``.
Plugin shims wire the singleton in at call time.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from pydantic import BaseModel

from magellon_sdk.models import TaskDto, TaskResultDto
from magellon_sdk.transport import RabbitmqClient

logger = logging.getLogger(__name__)


def create_directory(path: str) -> None:
    """Ensure the parent directory of ``path`` exists."""
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    except Exception as e:
        logger.error("Error creating directory for %s: %s", path, e)


def custom_replace(
    input_string: str,
    replace_type: str,
    replace_pattern: str,
    replace_with: str,
) -> str:
    """Replace substrings or regex matches based on ``replace_type``.

    ``replace_type`` is one of ``none`` (pass-through), ``standard``
    (literal ``str.replace``), or ``regex`` (``re.sub``).
    """
    if replace_type == "none":
        return input_string
    if replace_type == "standard":
        return input_string.replace(replace_pattern, replace_with)
    if replace_type == "regex":
        return re.sub(replace_pattern, replace_with, input_string)
    raise ValueError("Invalid replace_type. Use 'none', 'standard', or 'regex'.")


def append_json_to_file(file_path: str, json_str: str) -> bool:
    """Append ``json_str`` as a new line to ``file_path``."""
    try:
        with open(file_path, "a") as file:
            file.write(json_str + "\n")
        return True
    except Exception as e:
        logger.error("Error appending JSON to file %s: %s", file_path, e)
        return False


def parse_message_to_task_object(message_str: str) -> TaskDto:
    return TaskDto.model_validate_json(message_str)


def parse_message_to_task_result_object(message_str: str) -> TaskResultDto:
    return TaskResultDto.model_validate_json(message_str)


def publish_message_to_queue(
    message: BaseModel,
    queue_name: str,
    rabbitmq_settings,
) -> bool:
    """Publish ``message`` (as JSON) to ``queue_name``.

    ``rabbitmq_settings`` is any object exposing the attributes a
    :class:`RabbitmqClient` consumes (HOST_NAME, PORT, USER_NAME, …).
    Plugin shims pass in their ``AppSettingsSingleton`` RabbitMQ block.

    Returns ``True`` on success, ``False`` on error. The connection is
    always closed, even when publish fails, so callers do not leak
    sockets when RabbitMQ is flaky.
    """
    client: Optional[RabbitmqClient] = None
    try:
        client = RabbitmqClient(rabbitmq_settings)
        client.connect()
        client.publish_message(message.model_dump_json(), queue_name)
        logger.info("Message published to %s", queue_name)
        return True
    except Exception as e:
        logger.error("Error publishing message to %s: %s", queue_name, e)
        return False
    finally:
        if client is not None:
            try:
                client.close_connection()
            except Exception:
                pass


__all__ = [
    "append_json_to_file",
    "create_directory",
    "custom_replace",
    "parse_message_to_task_object",
    "parse_message_to_task_result_object",
    "publish_message_to_queue",
]
