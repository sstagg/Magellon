"""Temporal worker scaffolding for plugins.

Requires the ``temporal`` extra:  ``pip install magellon-sdk[temporal]``.

Plugin authors don't write Temporal boilerplate. They implement
``PluginBase`` and call::

    import asyncio
    from magellon_sdk.worker import run_worker
    from my_plugin import MyPlugin

    asyncio.run(run_worker(MyPlugin()))

…and the SDK brings up a ``temporalio.worker.Worker`` on the right task
queue, registers one activity that invokes ``plugin.run``, and blocks.
The ``magellon-plugin worker`` CLI subcommand is a thin wrapper over
this function.
"""
from __future__ import annotations

from magellon_sdk.worker.runtime import (
    build_plugin_activity,
    plugin_task_queue,
    run_worker,
)
from magellon_sdk.worker.types import PluginActivityInput, PluginActivityOutput

__all__ = [
    "PluginActivityInput",
    "PluginActivityOutput",
    "build_plugin_activity",
    "plugin_task_queue",
    "run_worker",
]
