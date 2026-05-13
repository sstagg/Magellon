"""BoxNet picker plugin entry — slim FastAPI host for the broker runner.

Same shape as the FFT / stack-maker / classifier / template-picker
plugins; PluginBrokerRunner consumes from ``QUEUE_NAME``, publishes
results to ``OUT_QUEUE_NAME``.
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
from magellon_sdk.capabilities import make_sync_router
from magellon_sdk.categories.contract import PARTICLE_PICKER
from magellon_sdk.logging_config import setup_logging
from magellon_sdk.models.manifest import Capability
from magellon_sdk.runner import PluginBrokerRunner
from plugin import BoxnetPickerPlugin, build_pick_result


_plugin = BoxnetPickerPlugin()
_plugin_info = _plugin.get_info()
setup_logging(_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()


_runner: PluginBrokerRunner | None = None


def _resolve_http_endpoint() -> str | None:
    """URL CoreService should use to reach this plugin's FastAPI.
    Same resolution order as the other plugins (PT-4, 2026-05-04).
    """
    explicit = os.environ.get("MAGELLON_PLUGIN_HTTP_ENDPOINT")
    if explicit:
        return explicit
    host = os.environ.get("MAGELLON_PLUGIN_HOST")
    port = os.environ.get("MAGELLON_PLUGIN_PORT")
    if host and port:
        return f"http://{host}:{port}"
    return None


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

        http_endpoint = _resolve_http_endpoint()
        sync_caps = {Capability.SYNC, Capability.PREVIEW}
        plugin_caps = set(_plugin.capabilities or [])
        advertised_sync = sync_caps & plugin_caps
        if advertised_sync and not http_endpoint:
            advertised = sorted(c.value for c in advertised_sync)
            logger.warning(
                "Plugin advertises %s but no http_endpoint resolved — set "
                "MAGELLON_PLUGIN_HTTP_ENDPOINT (or MAGELLON_PLUGIN_HOST + "
                "MAGELLON_PLUGIN_PORT) at deploy time. "
                "CoreService sync calls will 503 with BackendNotLive.",
                advertised,
            )

        _runner = PluginBrokerRunner(
            plugin=_plugin,
            settings=rmq,
            in_queue=rmq.QUEUE_NAME,
            out_queue=rmq.OUT_QUEUE_NAME,
            result_factory=build_pick_result,
            contract=PARTICLE_PICKER,
            http_endpoint=http_endpoint,
        )
        threading.Thread(
            target=_runner.start_blocking,
            name="boxnet-picker-broker-runner",
            daemon=True,
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


if Capability.SYNC in _plugin.capabilities:
    app.include_router(make_sync_router(_plugin))


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(
        status_code=500,
        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"},
    )
