"""MB4.3 test-queue consumer — bus-driven replacement for the legacy
``process_test_message`` callback.

The test queue carries denormalized task payloads from the frontend
(image_path + gain_path + ``motioncor_settings`` dict) and expects the
plugin to translate them into a proper ``CryoEmMotionCorTaskData`` +
fresh ``TaskDto`` before calling ``do_execute``. That translation
doesn't fit ``PluginBrokerRunner``'s strict input_schema validation,
so the test path lives here as its own ``bus.tasks.consumer``
subscription rather than as a second runner.

Output goes to ``MOTIONCOR_TEST_OUT_QUEUE_NAME`` via
``publish_message_to_queue`` — preserved from the legacy code so the
test result_processor wiring on the CoreService side is unchanged.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from magellon_sdk.bus import ConsumerHandle, get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

from magellon_sdk.models import (
    FAILED,
    CryoEmMotionCorTaskData,
    TaskCategory,
    TaskDto,
    TaskResultDto,
    TaskStatus,
)

from core.helper import publish_message_to_queue
from core.settings import AppSettingsSingleton
from service.service import do_execute

logger = logging.getLogger(__name__)


# Daemon loop for invoking async ``do_execute`` from the binder's sync
# handler — same pattern the standard plugin runner uses.
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(
    target=_loop.run_forever, name="motioncor-test-consumer-loop", daemon=True,
)
_loop_thread.start()


def _resolve_test_out_queue() -> str:
    return (
        AppSettingsSingleton.get_instance().rabbitmq_settings.MOTIONCOR_TEST_OUT_QUEUE_NAME
        or "motioncor_test_outqueue"
    )


def _normalize_test_task(task_dto: TaskDto) -> TaskDto:
    """Translate the test queue's denormalized shape into a proper
    TaskDto carrying ``CryoEmMotionCorTaskData``. Mirrors the logic
    of the legacy ``process_test_message`` callback."""
    task_data = task_dto.data if task_dto.data else {}
    motioncor_settings = task_data.get("motioncor_settings", {}) or {}

    image_path = task_data.get("image_path", "")
    image_name = (
        image_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if image_path else "unknown"
    )

    motioncor_task_data = CryoEmMotionCorTaskData(
        image_id=uuid4(),
        image_name=image_name,
        image_path=image_path,
        inputFile=image_path,
        OutMrc="output.mrc",
        Gain=task_data.get("gain_path", ""),
        DefectFile=task_data.get("defects_path"),
        PatchesX=int(motioncor_settings.get("PatchesX", 5)),
        PatchesY=int(motioncor_settings.get("PatchesY", 5)),
        FmDose=float(motioncor_settings["FmDose"]) if "FmDose" in motioncor_settings else None,
        PixSize=float(motioncor_settings["PixSize"]) if "PixSize" in motioncor_settings else None,
        kV=int(motioncor_settings.get("kV", 300)),
        Group=int(motioncor_settings["Group"]) if "Group" in motioncor_settings else None,
        FtBin=float(motioncor_settings.get("FtBin", 2)),
        Iter=int(motioncor_settings.get("Iter", 5)),
        Tol=float(motioncor_settings.get("Tol", 0.5)),
        Bft=int(motioncor_settings.get("Bft_global", 100)),
        FlipGain=int(motioncor_settings.get("FlipGain", 0)),
        RotGain=int(motioncor_settings.get("RotGain", 0)),
        Gpu="0",
    )

    return TaskDto(
        id=task_dto.id,
        worker_instance_id=uuid4(),
        job_id=uuid4(),
        data=motioncor_task_data.model_dump(),
        status=getattr(task_dto, "status", None) or TaskStatus(
            code=1, name="in_progress", description="Task in progress",
        ),
        type=getattr(task_dto, "type", None) or TaskCategory(
            code=5, name="MOTIONCOR", description="Motion Correction",
        ),
        session_name=task_data.get("session_name") or (image_name.split("_")[0] if image_name else "test"),
        start_on=datetime.now(),
    )


def _build_unexpected_result(task_dto: TaskDto, raw) -> TaskResultDto:
    """Wrap an unexpected ``do_execute`` return shape in a FAILED
    TaskResultDto so the publish path doesn't crash on ``model_dump``.
    Defensive: matches the audit fix in the legacy callback."""
    return TaskResultDto(
        task_id=task_dto.id,
        status=FAILED,
        message="Motioncor test task returned an unexpected result shape",
        output_data={"raw": str(raw)[:1000]},
        meta_data=[],
        output_files=[],
    )


def _on_envelope(envelope: Envelope) -> None:
    """Bus handler for one test-queue delivery."""
    test_out_queue = _resolve_test_out_queue()
    try:
        task_dto = TaskDto.model_validate(envelope.data)
    except Exception as exc:
        # Malformed payload — DLQ via PermanentError.
        raise PermanentError(f"undecodable TaskDto: {exc}") from exc

    try:
        normalized = _normalize_test_task(task_dto)
    except Exception as exc:
        # Translation failure — also DLQ. The frontend has a contract
        # for this queue's shape; if we can't translate, the message
        # is structurally wrong.
        raise PermanentError(f"test-task translation failed: {exc}") from exc

    logger.info("motioncor test consumer: executing task %s", task_dto.id)
    future = asyncio.run_coroutine_threadsafe(do_execute(params=normalized), _loop)
    result = future.result()

    if isinstance(result, dict) and "error" in result:
        error_result = TaskResultDto(
            task_id=task_dto.id,
            status=FAILED,
            message=f"Motioncor test task failed: {result.get('error', 'Unknown error')}",
            output_data=result,
            meta_data=[],
            output_files=[],
        )
        publish_message_to_queue(error_result, test_out_queue)
        logger.error("motioncor test task error published for %s", task_dto.id)
        return

    if hasattr(result, "model_dump"):
        result_dict = result.model_dump()
        result_dict["task_id"] = task_dto.id
        publish_message_to_queue(TaskResultDto(**result_dict), test_out_queue)
        logger.info("motioncor test result published for %s", task_dto.id)
        return

    publish_message_to_queue(_build_unexpected_result(task_dto, result), test_out_queue)
    logger.error(
        "motioncor test task: unexpected result type %s for %s",
        type(result).__name__, task_dto.id,
    )


def start_test_consumer() -> Optional[ConsumerHandle]:
    """Subscribe the test queue via the bus. Returns the handle so
    main.py can close it on shutdown.

    No-op (returns None) when ``MOTIONCOR_TEST_QUEUE_NAME`` isn't set
    — the test path is opt-in for deployments that exercise it.
    """
    settings = AppSettingsSingleton.get_instance().rabbitmq_settings
    test_in_queue = getattr(settings, "MOTIONCOR_TEST_QUEUE_NAME", None)
    if not test_in_queue:
        logger.info(
            "motioncor test consumer: MOTIONCOR_TEST_QUEUE_NAME unset — skipping",
        )
        return None
    bus = get_bus()
    handle = bus.tasks.consumer(TaskRoute.named(test_in_queue), _on_envelope)
    logger.info("motioncor test consumer: subscribed to %s", test_in_queue)
    return handle


__all__ = ["start_test_consumer"]
