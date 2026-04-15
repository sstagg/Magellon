"""FFT plugin entry point — slim FastAPI host for the broker runner.

This is intentionally a blueprint: a plugin author should be able to
copy this file, change ``FftPlugin``/``FFT``/``build_fft_result`` to
their own names, and have a working broker-native plugin.

Production task flow goes through the broker runner (RMQ →
``FftBrokerRunner`` → ``FftPlugin.execute`` → result queue), not over
HTTP. The HTTP surface here is minimal: ``/health`` for liveness probes
and Prometheus's ``/metrics`` from the instrumentator.
"""
from __future__ import annotations

import logging
import threading

from dotenv import load_dotenv
from fastapi import FastAPI
from prometheus_client import Info
from prometheus_fastapi_instrumentator import Instrumentator
from rich import traceback
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from core.settings import AppSettingsSingleton
from magellon_sdk.categories.contract import FFT
from magellon_sdk.logging_config import setup_logging
from plugin import FftBrokerRunner, FftPlugin, build_fft_result


_plugin = FftPlugin()
_plugin_info = _plugin.get_info()
setup_logging(_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()

app = FastAPI(
    debug=False,
    title=f"Magellan {_plugin_info.name}",
    description=_plugin_info.description,
    version=_plugin_info.version,
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


_runner: FftBrokerRunner | None = None


@app.on_event("startup")
async def startup_event():
    """Spin up the broker runner on a daemon thread.

    The runner harness owns the pika loop, discovery + heartbeat,
    dynamic config, provenance stamping, and typed failure routing.
    We just hand it the plugin + queue names.
    """
    global _runner
    try:
        rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
        _runner = FftBrokerRunner(
            plugin=_plugin,
            settings=rmq,
            in_queue=rmq.QUEUE_NAME,
            out_queue=rmq.OUT_QUEUE_NAME,
            result_factory=build_fft_result,
            contract=FFT,
        )
        threading.Thread(
            target=_runner.start_blocking, name="fft-broker-runner", daemon=True
        ).start()
    except Exception:
        logger.exception("FftBrokerRunner: startup failed")


@app.on_event("shutdown")
async def shutdown_event():
    if _runner is not None:
        try:
            _runner.stop()
        except Exception:
            logger.exception("FftBrokerRunner: stop() raised")


Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(
        status_code=400,
        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"},
    )
