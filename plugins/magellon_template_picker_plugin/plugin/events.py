"""Template-picker step-event binding."""
from __future__ import annotations

from typing import Optional

from magellon_sdk.events import StepEventPublisher, make_step_publisher

from core.settings import AppSettingsSingleton

STEP_NAME = "template_picker"


async def get_publisher() -> Optional[StepEventPublisher]:
    return await make_step_publisher(
        plugin_name=STEP_NAME,
        rmq_settings=AppSettingsSingleton.get_instance().rabbitmq_settings,
    )


__all__ = ["STEP_NAME", "get_publisher"]
