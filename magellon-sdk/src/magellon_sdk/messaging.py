"""Shared message/file helpers used by every plugin's ``core/helper.py``.

Post-MB6.2 ``publish_message_to_queue`` is a thin wrapper over
``bus.tasks.send`` — plugins publish via the MessageBus like every
other producer. The ``rabbitmq_settings`` argument is retained for
backcompat with pre-MB6.2 plugin helpers; it is no longer consulted
(the bus was configured at startup from the same settings).
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from pydantic import BaseModel

from magellon_sdk.models import TaskDto, TaskResultDto

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
    rabbitmq_settings=None,
) -> bool:
    """Publish ``message`` (as JSON) to ``queue_name`` via the MessageBus.

    Post-MB6.2: delegates to ``bus.tasks.send`` on a
    :class:`TaskRoute.named` — the binder owns the connection /
    publish / error classification. Returns ``True`` on success,
    ``False`` on any error (connection down, bus not installed, etc.)
    so plugin helpers can treat this as fire-and-forget.

    The ``rabbitmq_settings`` argument is retained for backcompat with
    pre-MB6.2 callers (plugin ``core/helper.py`` files, CoreService
    smoke scripts). It is no longer consulted — the bus was
    configured at startup from the same settings block.
    """
    from magellon_sdk.bus import get_bus
    from magellon_sdk.bus.routes import TaskRoute
    from magellon_sdk.envelope import Envelope

    try:
        envelope = Envelope.wrap(
            source="magellon/sdk/messaging",
            type="magellon.task.dispatch",
            subject=queue_name,
            data=message,
        )
        receipt = get_bus().tasks.send(TaskRoute.named(queue_name), envelope)
        if receipt.ok:
            logger.info("Message published to %s", queue_name)
        else:
            logger.error(
                "Error publishing message to %s: %s", queue_name, receipt.error
            )
        return receipt.ok
    except Exception as e:
        logger.error("Error publishing message to %s: %s", queue_name, e)
        return False


__all__ = [
    "append_json_to_file",
    "create_directory",
    "custom_replace",
    "parse_message_to_task_object",
    "parse_message_to_task_result_object",
    "publish_message_to_queue",
]
