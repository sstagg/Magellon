"""Temporal worker runtime for Magellon plugins.

Exposed surface:

- ``plugin_task_queue(plugin)`` — the canonical task queue name for a
  plugin (host and plugin must agree).
- ``build_plugin_activity(plugin)`` — wraps ``plugin.run`` in a
  Temporal activity function registered under ``plugin.<category>.run``.
- ``run_worker(plugin, *, client=None, ...)`` — the blocking
  one-shot entry point used by ``magellon-plugin worker``.

Rationale: the Magellon host shouldn't care *which* Temporal activity
ID a given plugin exposes — only that "the CTF plugin is reachable via
the queue named ``magellon.ctf/ctffind``". Pinning the naming scheme in
the SDK lets the host dispatch by `PluginInfo` alone.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Sequence

from magellon_sdk.base import PluginBase
from magellon_sdk.worker.types import PluginActivityInput, PluginActivityOutput

try:  # pragma: no cover — import guard, exercised only when extra is absent
    from temporalio.activity import defn as _activity_defn
    from temporalio.client import Client
    from temporalio.worker import Worker
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "magellon-sdk worker runtime requires the 'temporal' extra. "
        "Install with:  pip install magellon-sdk[temporal]"
    ) from exc


def plugin_task_queue(plugin: PluginBase) -> str:
    """Canonical Temporal task queue name for a plugin.

    One queue per plugin keeps worker fleets independent — CTF workers
    can scale on GPU nodes while MotionCor workers scale on a different
    pool, and a failing queue drains in isolation.
    """
    info = plugin.get_info()
    category = plugin.task_category.name.lower().replace(" ", "-")
    name = (info.name or "plugin").lower()
    return f"magellon.{category}/{name}"


def _activity_name_for(plugin: PluginBase) -> str:
    info = plugin.get_info()
    category = plugin.task_category.name.lower().replace(" ", "-")
    name = (info.name or "plugin").lower()
    return f"plugin.{category}/{name}.run"


def build_plugin_activity(plugin: PluginBase):
    """Return a Temporal activity callable that invokes ``plugin.run``.

    The activity is registered under a deterministic name — workflows
    start it by name; plugin authors never write ``@activity.defn``.
    """
    activity_name = _activity_name_for(plugin)

    @_activity_defn(name=activity_name)
    async def _run(payload: PluginActivityInput) -> PluginActivityOutput:
        # plugin.run is synchronous (Pydantic validation + compute).
        # Off-load to a thread so the activity doesn't block the worker
        # loop, and so a slow plugin can't starve heartbeats on other
        # activities in the same worker.
        def _invoke() -> Dict[str, Any]:
            result = plugin.run(payload.input)
            return result.model_dump()

        output = await asyncio.to_thread(_invoke)
        return PluginActivityOutput(output=output)

    return _run


async def run_worker(
    plugin: PluginBase,
    *,
    client: Optional[Client] = None,
    target: str = "localhost:7233",
    namespace: str = "default",
    task_queue: Optional[str] = None,
    workflows: Sequence[type] = (),
) -> None:
    """Boot a Temporal worker for one plugin and block.

    Parameters
    ----------
    plugin
        An initialised plugin instance. Lifecycle (``setup``/``teardown``)
        is the plugin author's responsibility — call them before/after
        ``run_worker`` as needed.
    client
        Optional pre-connected Temporal client. When omitted, connects
        to ``target``/``namespace``. Supplying a client is the test
        seam (see ``temporalio.testing.WorkflowEnvironment``).
    task_queue
        Override the default queue name. Defaults to
        :func:`plugin_task_queue` so hosts can dispatch by plugin info
        without asking the worker.
    workflows
        Workflow classes to register alongside the plugin activity.
        Most plugin images only run activities; hosts running workflow
        workers (like ``CtfWorkflow``) pass their workflow classes here.
    """
    if client is None:
        client = await Client.connect(target, namespace=namespace)

    queue = task_queue or plugin_task_queue(plugin)
    plugin.setup()

    try:
        worker = Worker(
            client,
            task_queue=queue,
            activities=[build_plugin_activity(plugin)],
            workflows=list(workflows),
        )
        await worker.run()
    finally:
        plugin.teardown()
