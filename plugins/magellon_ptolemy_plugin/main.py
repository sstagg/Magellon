"""Ptolemy plugin entry point — FastAPI host + two broker runners.

One container serves both ``SQUARE_DETECTION`` and ``HOLE_DETECTION``
categories. Each gets its own ``PluginBrokerRunner`` on its own daemon
thread; the three ONNX models are loaded lazily and cached per-process
so the two runners share the same InferenceSession objects.

Mirrors ``magellon_fft_plugin/main.py`` layout for familiarity.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading

os.environ.setdefault("MAGELLON_STEP_EVENTS_ENABLED", "1")
os.environ.setdefault("MAGELLON_STEP_EVENTS_RMQ", "1")

from dotenv import load_dotenv
from fastapi import FastAPI
from prometheus_client import Info
from prometheus_fastapi_instrumentator import Instrumentator
from rich import traceback
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from core.settings import AppSettingsSingleton
from magellon_sdk.bus.bootstrap import install_rmq_bus
from magellon_sdk.categories.contract import HOLE_DETECT, SQUARE_DETECT
from magellon_sdk.logging_config import setup_logging
from plugin import (
    PtolemyBrokerRunner,
    PtolemyHolePlugin,
    PtolemySquarePlugin,
    build_hole_result,
    build_square_result,
)


_square_plugin = PtolemySquarePlugin()
_hole_plugin = PtolemyHolePlugin()
_square_info = _square_plugin.get_info()
_hole_info = _hole_plugin.get_info()

setup_logging(_square_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()

app = FastAPI(
    debug=False,
    title="Magellon Ptolemy Plugin",
    description="Square + hole detection with pickability scoring (ONNX backed).",
    version=_square_info.version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

Info("plugin", "ptolemy plugin information").info({
    "square_name":    _square_info.name,
    "hole_name":      _hole_info.name,
    "version":        _square_info.version,
    "square_instance": str(_square_info.instance_id),
    "hole_instance":   str(_hole_info.instance_id),
})


_square_runner: PtolemyBrokerRunner | None = None
_hole_runner:   PtolemyBrokerRunner | None = None


@app.on_event("startup")
async def startup_event() -> None:
    """Install the bus once, pre-warm the step publisher, and start both
    runners on their own daemon threads."""
    global _square_runner, _hole_runner
    try:
        settings = AppSettingsSingleton.get_instance()
        rmq = settings.rabbitmq_settings
        install_rmq_bus(rmq)

        # Pre-warm step publisher on the shared plugin event loop.
        try:
            from plugin.events import get_publisher
            from plugin.plugin import _get_loop
            asyncio.run_coroutine_threadsafe(get_publisher(), _get_loop())
            logger.info("step-event publisher pre-warm scheduled")
        except Exception:
            logger.exception("step-event publisher pre-warm failed (non-fatal)")

        _square_runner = PtolemyBrokerRunner(
            plugin=_square_plugin,
            settings=rmq,
            in_queue=settings.SQUARE_QUEUE_NAME,
            out_queue=settings.SQUARE_OUT_QUEUE_NAME,
            result_factory=build_square_result,
            contract=SQUARE_DETECT,
        )
        threading.Thread(
            target=_square_runner.start_blocking,
            name="ptolemy-square-broker-runner",
            daemon=True,
        ).start()

        _hole_runner = PtolemyBrokerRunner(
            plugin=_hole_plugin,
            settings=rmq,
            in_queue=settings.HOLE_QUEUE_NAME,
            out_queue=settings.HOLE_OUT_QUEUE_NAME,
            result_factory=build_hole_result,
            contract=HOLE_DETECT,
        )
        threading.Thread(
            target=_hole_runner.start_blocking,
            name="ptolemy-hole-broker-runner",
            daemon=True,
        ).start()

        logger.info("ptolemy plugin: both runners started")
    except Exception:
        logger.exception("ptolemy plugin: startup failed")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    for runner, name in ((_square_runner, "square"), (_hole_runner, "hole")):
        if runner is not None:
            try:
                runner.stop()
            except Exception:
                logger.exception("ptolemy %s runner: stop() raised", name)


Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Synchronous /execute endpoint — routes to the right plugin by task.type.
# Broker is still the production path; this is for contract tests + manual
# debugging, mirroring the CTF / MotionCor plugin convention.
# ---------------------------------------------------------------------------

from magellon_sdk.categories.contract import HOLE_DETECT, SQUARE_DETECT  # noqa: E402
from magellon_sdk.models import TaskDto  # noqa: E402
from plugin import build_hole_result, build_square_result  # noqa: E402


@app.post("/execute", summary="Execute Plugin Operation (sync)")
async def execute_endpoint(task: TaskDto):
    """Route the task to the matching plugin and return a TaskResultDto."""
    type_code = task.type.code if task.type else None
    if type_code == SQUARE_DETECT.category.code:
        validated = _square_plugin.input_schema().model_validate(task.data)
        output = _square_plugin.run(validated)
        return build_square_result(task, output)
    if type_code == HOLE_DETECT.category.code:
        validated = _hole_plugin.input_schema().model_validate(task.data)
        output = _hole_plugin.run(validated)
        return build_hole_result(task, output)
    return JSONResponse(
        status_code=400,
        content={
            "message": (
                f"Unsupported task.type.code={type_code}. "
                f"Expected {SQUARE_DETECT.category.code} (SquareDetection) "
                f"or {HOLE_DETECT.category.code} (HoleDetection)."
            )
        },
    )


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(
        status_code=400,
        content={
            "message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"
        },
    )
