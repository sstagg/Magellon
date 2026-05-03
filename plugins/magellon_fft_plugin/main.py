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

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager

# Step-event observability defaults — flipped on for this dev/blueprint
# plugin so the Tasks panel on the FFT test page sees lifecycle events
# without the operator having to set env vars by hand. RMQ mirror is
# enabled because most local-dev setups don't run NATS JetStream, and
# CoreService's RMQ step-event forwarder is the path that actually
# delivers events to the React UI in those setups. Use ``setdefault``
# so production deployments that explicitly turn these off still win.
# IMPORTANT: must run before SDK imports below — the publisher reads
# these at module init.
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
from magellon_sdk.categories.contract import FFT
from magellon_sdk.logging_config import setup_logging
from magellon_sdk.runner import PluginBrokerRunner
from plugin import FftPlugin, build_fft_result


_plugin = FftPlugin()
_plugin_info = _plugin.get_info()
setup_logging(_plugin.get_info)
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()


_runner: PluginBrokerRunner | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Spin up the broker runner on a daemon thread; shut it down cleanly.

    MB4.2: ``install_rmq_bus`` wires a process-wide ``MessageBus``
    backed by the plugin's RMQ settings. The runner's task I/O
    (consume + publish result) then flows through the bus; discovery
    + heartbeat + config still run on their own pika connections for
    now (MB5 folds them in too).
    """
    global _runner
    try:
        rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
        install_rmq_bus(rmq)

        # Pre-warm the step-event publisher so the first task doesn't pay
        # the cold-start cost (NATS connect attempt + JetStream add_stream
        # timeout, then RMQ exchange declare). Without this, make_step_reporter
        # races the first dispatch and times out → those tasks emit no
        # events. Fire-and-forget on the dedicated step-events daemon loop.
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
            result_factory=build_fft_result,
            contract=FFT,
        )
        threading.Thread(
            target=_runner.start_blocking, name="fft-broker-runner", daemon=True
        ).start()
    except Exception:
        logger.exception("FftBrokerRunner: startup failed")

    yield

    if _runner is not None:
        try:
            _runner.stop()
        except Exception:
            logger.exception("FftBrokerRunner: stop() raised")


app = FastAPI(
    debug=False,
    title=f"Magellan {_plugin_info.name}",
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
