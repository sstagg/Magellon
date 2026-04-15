"""Temporal dispatch for legacy plugin tasks.

This module is the flag-gated bridge between the existing RabbitMQ
dispatch path and the Temporal-based path introduced in Phase 2. When
``CTF_VIA_TEMPORAL`` is on, ``core.helper.dispatch_ctf_task`` routes
through :func:`dispatch_ctf_via_temporal` here instead of publishing
to RabbitMQ.

Kept out of ``core/helper.py`` so the Temporal imports (which pull in
grpc, protobuf, etc.) only load when the flag is actually on, and so
the characterization tests around helper.py don't change.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
from typing import Any

from config import app_settings
from models.plugins_models import CtfTask

logger = logging.getLogger(__name__)


def ctf_via_temporal_enabled() -> bool:
    """Env var wins over settings so operators can flip at runtime.

    Legal truthy values: ``1``, ``true``, ``yes``, ``on`` (case-insensitive).
    """
    env = os.environ.get("CTF_VIA_TEMPORAL")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "on")
    return bool(app_settings.temporal_settings.CTF_VIA_TEMPORAL)


def _run_coro_sync(coro) -> Any:
    """Run ``coro`` to completion from a sync caller.

    Works both when the caller is outside any event loop (the typical
    importer path) and when it is nested inside a running loop (a
    FastAPI request handler that forgot to ``await`` into a thread).
    In the second case we off-load to a worker thread rather than
    failing with "asyncio.run() cannot be called from a running loop".
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


async def _start_ctf_workflow(ctf_task: CtfTask) -> str:
    """Connect to Temporal and start ``CtfWorkflow`` for ``ctf_task``.

    Returns the workflow run id. Imports are deferred so importing this
    module (or ``core.helper``) doesn't pull Temporal in unless the flag
    is actually on.
    """
    from temporalio.client import Client

    from magellon_sdk.worker.types import PluginActivityInput
    from workflows.ctf_workflow import CTF_PLUGIN_ID, CTF_TASK_QUEUE, CtfWorkflow

    client = await Client.connect(
        app_settings.temporal_settings.TARGET,
        namespace=app_settings.temporal_settings.NAMESPACE,
    )

    # CtfTask.data is typed as CtfTaskData (Pydantic v2 coerces the dict
    # the factory passed in), so normalise back to a plain dict before
    # sending across the Temporal boundary.
    task_data = ctf_task.data
    if hasattr(task_data, "model_dump"):
        task_data = task_data.model_dump()

    payload = PluginActivityInput(
        plugin_id=CTF_PLUGIN_ID,
        job_id=str(ctf_task.job_id or ""),
        input=task_data,
    )
    handle = await client.start_workflow(
        CtfWorkflow.run,
        payload,
        id=f"ctf-{ctf_task.id}",
        task_queue=CTF_TASK_QUEUE,
    )
    return handle.result_run_id


def dispatch_ctf_via_temporal(ctf_task: CtfTask) -> bool:
    """Sync façade around :func:`_start_ctf_workflow` for helper.py.

    Returns True on successful workflow start (not on workflow
    completion — CTF jobs can take minutes to hours and we don't block
    the caller). Errors are logged and swallowed to match the RabbitMQ
    path's semantics, so a flag-on failure behaves the same way a
    RabbitMQ outage does from the caller's perspective.
    """
    try:
        run_id = _run_coro_sync(_start_ctf_workflow(ctf_task))
        logger.info(
            "CTF task %s dispatched via Temporal (run_id=%s)", ctf_task.id, run_id
        )
        return True
    except Exception as exc:
        logger.error("Failed to dispatch CTF task via Temporal: %s", exc)
        return False


__all__ = [
    "ctf_via_temporal_enabled",
    "dispatch_ctf_via_temporal",
]
