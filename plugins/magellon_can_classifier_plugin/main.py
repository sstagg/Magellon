"""CAN classifier plugin entry — slim FastAPI host for the broker runner.

Phase 7 scaffold. RMQ → PluginBrokerRunner → CanClassifierPlugin.execute
→ result queue. HTTP: /health + Prometheus /metrics.
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
from magellon_sdk.categories.contract import TWO_D_CLASSIFICATION_CATEGORY
from magellon_sdk.logging_config import setup_logging
from magellon_sdk.runner import PluginBrokerRunner
from plugin import CanClassifierPlugin, build_classification_result


_plugin = CanClassifierPlugin()
_plugin_info = _plugin.get_info()
setup_logging(_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()


_runner: PluginBrokerRunner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _runner
    try:
        rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
        install_rmq_bus(rmq)

        try:
            from magellon_sdk.runner import get_step_event_loop
            from plugin.events import get_publisher
            asyncio.run_coroutine_threadsafe(get_publisher(), get_step_event_loop())
            logger.info("step-event publisher pre-warm scheduled")
        except Exception:
            logger.exception("step-event publisher pre-warm scheduling failed (non-fatal)")

        _runner = PluginBrokerRunner(
            plugin=_plugin,
            settings=rmq,
            in_queue=rmq.QUEUE_NAME,
            out_queue=rmq.OUT_QUEUE_NAME,
            result_factory=build_classification_result,
            contract=TWO_D_CLASSIFICATION_CATEGORY,
        )
        threading.Thread(
            target=_runner.start_blocking, name="can-classifier-broker-runner", daemon=True
        ).start()
    except Exception:
        logger.exception("PluginBrokerRunner: startup failed")

    yield

    if _runner is not None:
        try:
            _runner.stop()
        except Exception:
            logger.exception("PluginBrokerRunner: stop() raised")


app = FastAPI(
    debug=False,
    title=f"Magellon {_plugin_info.name}",
    description=_plugin_info.description,
    version=_plugin_info.version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

Info("plugin", "information about magellons plugin").info(
    {
        "name": _plugin_info.name,
        "description": _plugin_info.description or "No description",
        "instance": str(_plugin_info.instance_id),
    }
)


Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(
        status_code=500,
        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"},
    )
