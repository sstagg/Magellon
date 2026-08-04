"""CTF test-queue consumer — bus-driven, mirrors the motioncor test_consumer.

The test queue carries denormalized task payloads from the frontend
(image_path + ctf_params dict) and translates them into a proper
CtfInput + TaskMessage before calling do_execute. Output goes to
CTF_TEST_OUT_QUEUE_NAME so CoreService can WebSocket the result
back to the browser.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional
from uuid import uuid4

from magellon_sdk.bus import ConsumerHandle, get_bus
from magellon_sdk.bus.routes import TaskRoute
from magellon_sdk.envelope import Envelope
from magellon_sdk.errors import PermanentError

from magellon_sdk.models import (
    FAILED,
    CtfInput,
    TaskCategory,
    TaskMessage,
    TaskResultMessage,
    TaskStatus,
)

from core.helper import publish_message_to_queue
from core.settings import AppSettingsSingleton
from service.service import do_execute

logger = logging.getLogger(__name__)

# Dedicated daemon loop — same pattern as the motioncor test consumer.
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(
    target=_loop.run_forever, name="ctf-test-consumer-loop", daemon=True,
)
_loop_thread.start()


def _resolve_test_out_queue() -> str:
    return (
        AppSettingsSingleton.get_instance().rabbitmq_settings.CTF_TEST_OUT_QUEUE_NAME
        or "ctf_test_outqueue"
    )


def _normalize_test_task(task_dto: TaskMessage) -> TaskMessage:
    """Translate the frontend test payload into a proper TaskMessage
    carrying CtfInput. Frontend sends image_path + ctf_params dict."""
    task_data = task_dto.data if task_dto.data else {}
    ctf_params = task_data.get("ctf_params", {}) or {}

    image_path = task_data.get("image_path", "")
    image_name = (
        image_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if image_path else "unknown"
    )

    ctf_task_data = CtfInput(
        image_id=uuid4(),
        image_name=image_name,
        image_path=image_path,
        inputFile=image_path,
        outputFile="output.mrc",
        pixelSize=float(ctf_params.get("PixSize", 1.0)),
        accelerationVoltage=float(ctf_params.get("kV", 300.0)),
        sphericalAberration=float(ctf_params.get("Cs", 2.7)),
        amplitudeContrast=float(ctf_params.get("AmpContrast", 0.1)),
        sizeOfAmplitudeSpectrum=int(ctf_params.get("SpectrumSize", 512)),
        minimumResolution=float(ctf_params.get("MinRes", 30.0)),
        maximumResolution=float(ctf_params.get("MaxRes", 5.0)),
        minimumDefocus=float(ctf_params.get("MinDefocus", 5000.0)),
        maximumDefocus=float(ctf_params.get("MaxDefocus", 50000.0)),
        defocusSearchStep=float(ctf_params.get("DefocusStep", 500.0)),
        binning_x=1,
    )

    return TaskMessage(
        id=task_dto.id,
        worker_instance_id=uuid4(),
        job_id=uuid4(),
        data=ctf_task_data.model_dump(),
        status=getattr(task_dto, "status", None) or TaskStatus(
            code=1, name="in_progress", description="Task in progress",
        ),
        type=getattr(task_dto, "type", None) or TaskCategory(
            code=2, name="CTF", description="CTF Estimation",
        ),
        session_name=task_data.get("session_name") or (image_name.split("_")[0] if image_name else "test"),
        start_on=datetime.now(),
    )


def _build_unexpected_result(task_dto: TaskMessage, raw) -> TaskResultMessage:
    return TaskResultMessage(
        task_id=task_dto.id,
        status=FAILED,
        message="CTF test task returned an unexpected result shape",
        output_data={"raw": str(raw)[:1000]},
        meta_data=[],
        output_files=[],
    )


def _on_envelope(envelope: Envelope) -> None:
    """Bus handler for one CTF test-queue delivery."""
    test_out_queue = _resolve_test_out_queue()
    try:
        task_dto = TaskMessage.model_validate(envelope.data)
    except Exception as exc:
        raise PermanentError(f"undecodable TaskMessage: {exc}") from exc

    try:
        normalized = _normalize_test_task(task_dto)
    except Exception as exc:
        raise PermanentError(f"ctf test-task translation failed: {exc}") from exc

    logger.info("ctf test consumer: executing task %s", task_dto.id)
    future = asyncio.run_coroutine_threadsafe(do_execute(params=normalized), _loop)
    result = future.result()

    if isinstance(result, dict) and "error" in result:
        error_result = TaskResultMessage(
            task_id=task_dto.id,
            status=FAILED,
            message=f"CTF test task failed: {result.get('error', 'Unknown error')}",
            output_data=result,
            meta_data=[],
            output_files=[],
        )
        publish_message_to_queue(error_result, test_out_queue)
        logger.error("ctf test task error published for %s", task_dto.id)
        return

    if hasattr(result, "model_dump"):
        result_dict = result.model_dump()
        result_dict["task_id"] = task_dto.id
        publish_message_to_queue(TaskResultMessage(**result_dict), test_out_queue)
        logger.info("ctf test result published for %s", task_dto.id)
        return

    publish_message_to_queue(_build_unexpected_result(task_dto, result), test_out_queue)
    logger.error(
        "ctf test task: unexpected result type %s for %s",
        type(result).__name__, task_dto.id,
    )


def start_test_consumer() -> Optional[ConsumerHandle]:
    """Subscribe to the CTF test queue via the bus. Returns the handle.

    No-op when CTF_TEST_QUEUE_NAME isn't set — the test path is opt-in.
    """
    settings = AppSettingsSingleton.get_instance().rabbitmq_settings
    test_in_queue = getattr(settings, "CTF_TEST_QUEUE_NAME", None)
    if not test_in_queue:
        logger.info("ctf test consumer: CTF_TEST_QUEUE_NAME unset — skipping")
        return None
    bus = get_bus()
    handle = bus.tasks.consumer(TaskRoute.named(test_in_queue), _on_envelope)
    logger.info("ctf test consumer: subscribed to %s", test_in_queue)
    return handle


__all__ = ["start_test_consumer"]
