"""SAM2 particle-picker plugin — FastAPI host.

Mounts:
  * PluginBrokerRunner  — consumes TaskMessages from RMQ
  * POST /execute       — SYNC capability (via SDK make_sync_router)
  * POST /preview + retune + DELETE  — PREVIEW capability
  * POST /click-pick    — interactive single-click segmentation
  * GET  /health
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
from magellon_sdk.capabilities import make_preview_router, make_sync_router
from magellon_sdk.categories.contract import PARTICLE_PICKER
from magellon_sdk.logging_config import setup_logging
from magellon_sdk.models.manifest import Capability
from magellon_sdk.runner import PluginBrokerRunner
from plugin import Sam2Plugin, build_pick_result
from plugin.models import ClickPickRequest, ClickPickResult

_plugin = Sam2Plugin()
_plugin_info = _plugin.get_info()
setup_logging(_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()

_runner: PluginBrokerRunner | None = None


def _resolve_http_endpoint() -> str | None:
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
        except Exception:
            logger.debug("step-event publisher pre-warm failed (non-fatal)")

        http_endpoint = _resolve_http_endpoint()
        sync_caps = {Capability.SYNC, Capability.PREVIEW}
        advertised = sync_caps & set(_plugin.capabilities or [])
        if advertised and not http_endpoint:
            logger.warning(
                "Plugin advertises %s but no http_endpoint resolved — set "
                "MAGELLON_PLUGIN_HTTP_ENDPOINT. CoreService sync/click calls will 503.",
                sorted(c.value for c in advertised),
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
            name="sam2-broker-runner",
            daemon=True,
        ).start()
    except Exception:
        logger.exception("PluginBrokerRunner startup failed")

    yield

    if _runner is not None:
        try:
            _runner.stop()
        except Exception:
            logger.exception("PluginBrokerRunner stop() raised")


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

Info("plugin", "Magellon plugin info").info({
    "name": _plugin_info.name,
    "description": _plugin_info.description or "",
    "instance": str(_plugin_info.instance_id),
})

Instrumentator().instrument(app).expose(app)

# SDK capability routers
if Capability.SYNC in _plugin.capabilities:
    app.include_router(make_sync_router(_plugin))
if Capability.PREVIEW in _plugin.capabilities:
    app.include_router(make_preview_router(_plugin))


# ------------------------------------------------------------------
# Custom endpoint: interactive single-click segmentation
# ------------------------------------------------------------------

@app.post(
    "/click-pick",
    response_model=ClickPickResult,
    summary="SAM2 interactive click-to-pick",
    description=(
        "Segment the particle under the supplied prompt point(s).  "
        "The image embedding is cached so the first call embeds the image (~2-5 s CPU / ~0.3 s GPU); "
        "subsequent calls for the same micrograph return in under 500 ms."
    ),
)
async def click_pick_endpoint(req: ClickPickRequest) -> ClickPickResult:
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: _plugin.click_segment(req))
    return result


@app.get("/health")
async def health_check():
    return {"status": "ok", "plugin": _plugin_info.name, "version": _plugin_info.version}


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(
        status_code=500,
        content={"message": f"Failed: {request.method} {request.url} — {err}"},
    )
