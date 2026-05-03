"""Topaz plugin entry point — FastAPI host + two broker runners.

One container serves both ``TOPAZ_PARTICLE_PICKING`` and
``MICROGRAPH_DENOISING``. Each gets its own ``PluginBrokerRunner`` on
its own daemon thread; the three ONNX models cache per-process so the
two runners share InferenceSession objects.

Phase 1b (2026-05-03): use the SDK :class:`PluginBrokerRunner` directly
(no ``TopazBrokerRunner`` subclass — the SDK now owns the active-task
ContextVar). Phase 2: lifespan replaces deprecated ``on_event``;
exception handler returns 500 not 400.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager

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
from magellon_sdk.categories.contract import DENOISE, TOPAZ_PICK
from magellon_sdk.logging_config import setup_logging
from magellon_sdk.runner import PluginBrokerRunner
from plugin import (
    TopazDenoisePlugin,
    TopazPickPlugin,
    build_denoise_result,
    build_pick_result,
)


_pick_plugin = TopazPickPlugin()
_denoise_plugin = TopazDenoisePlugin()
_pick_info = _pick_plugin.get_info()
_denoise_info = _denoise_plugin.get_info()

setup_logging(_pick_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()


_pick_runner:    PluginBrokerRunner | None = None
_denoise_runner: PluginBrokerRunner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pick_runner, _denoise_runner
    try:
        settings = AppSettingsSingleton.get_instance()
        rmq = settings.rabbitmq_settings
        install_rmq_bus(rmq)

        try:
            from magellon_sdk.runner import get_step_event_loop
            from plugin.events import get_publisher
            asyncio.run_coroutine_threadsafe(get_publisher(), get_step_event_loop())
            logger.info("step-event publisher pre-warm scheduled")
        except Exception:
            logger.exception("step-event publisher pre-warm failed (non-fatal)")

        _pick_runner = PluginBrokerRunner(
            plugin=_pick_plugin,
            settings=rmq,
            in_queue=settings.PICK_QUEUE_NAME,
            out_queue=settings.PICK_OUT_QUEUE_NAME,
            result_factory=build_pick_result,
            contract=TOPAZ_PICK,
        )
        threading.Thread(
            target=_pick_runner.start_blocking,
            name="topaz-pick-broker-runner",
            daemon=True,
        ).start()

        _denoise_runner = PluginBrokerRunner(
            plugin=_denoise_plugin,
            settings=rmq,
            in_queue=settings.DENOISE_QUEUE_NAME,
            out_queue=settings.DENOISE_OUT_QUEUE_NAME,
            result_factory=build_denoise_result,
            contract=DENOISE,
        )
        threading.Thread(
            target=_denoise_runner.start_blocking,
            name="topaz-denoise-broker-runner",
            daemon=True,
        ).start()

        logger.info("topaz plugin: both runners started")
    except Exception:
        logger.exception("topaz plugin: startup failed")

    yield

    for runner, name in ((_pick_runner, "pick"), (_denoise_runner, "denoise")):
        if runner is not None:
            try:
                runner.stop()
            except Exception:
                logger.exception("topaz %s runner: stop() raised", name)


app = FastAPI(
    debug=False,
    title="Magellon Topaz Plugin",
    description="Particle picking + denoising via topaz (ONNX backed).",
    version=_pick_info.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

Info("plugin", "topaz plugin information").info({
    "pick_name":     _pick_info.name,
    "denoise_name":  _denoise_info.name,
    "version":       _pick_info.version,
    "pick_instance":    str(_pick_info.instance_id),
    "denoise_instance": str(_denoise_info.instance_id),
})


Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Synchronous /execute — same convention as ptolemy/CTF/MotionCor.
# Routes by task.type.code; useful for contract tests + debugging.
# ---------------------------------------------------------------------------

from magellon_sdk.models import TaskMessage  # noqa: E402


@app.post("/execute", summary="Execute Plugin Operation (sync)")
async def execute_endpoint(task: TaskMessage):
    type_code = task.type.code if task.type else None
    if type_code == TOPAZ_PICK.category.code:
        validated = _pick_plugin.input_schema().model_validate(task.data)
        return build_pick_result(task, _pick_plugin.run(validated))
    if type_code == DENOISE.category.code:
        validated = _denoise_plugin.input_schema().model_validate(task.data)
        return build_denoise_result(task, _denoise_plugin.run(validated))
    return JSONResponse(
        status_code=400,
        content={
            "message": (
                f"Unsupported task.type.code={type_code}. "
                f"Expected {TOPAZ_PICK.category.code} (TopazParticlePicking) "
                f"or {DENOISE.category.code} (MicrographDenoising)."
            )
        },
    )


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(
        status_code=500,
        content={
            "message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"
        },
    )
