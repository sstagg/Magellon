"""FFT plugin step-event binding — thin glue over magellon-sdk.

The heavy lifting (NATS+RMQ fanout, lazy init, env-var handling, error
fallback) lives in :func:`magellon_sdk.events.make_step_publisher`.
This file just supplies the plugin-local pieces: the step name and
the RMQ settings source.
"""
from __future__ import annotations

from typing import Optional

from magellon_sdk.events import StepEventPublisher, make_step_publisher

from core.settings import AppSettingsSingleton

STEP_NAME = "fft"


async def get_publisher() -> Optional[StepEventPublisher]:
    return await make_step_publisher(
        plugin_name=STEP_NAME,
        rmq_settings=AppSettingsSingleton.get_instance().rabbitmq_settings,
    )


__all__ = ["STEP_NAME", "get_publisher"]
