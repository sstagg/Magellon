import asyncio
import json
import logging
import os
import socket
import threading

# Step-event observability defaults — flipped on so this plugin emits
# lifecycle events without operators having to set env vars by hand.
# RMQ mirror is enabled because most local-dev setups don't run NATS
# JetStream, and CoreService's RMQ step-event forwarder is the path
# that delivers events to the React UI in those setups. ``setdefault``
# means production deployments that explicitly turn these off win.
# Must run before SDK imports below — the publisher reads these at init.
os.environ.setdefault("MAGELLON_STEP_EVENTS_ENABLED", "1")
os.environ.setdefault("MAGELLON_STEP_EVENTS_RMQ", "1")

from rich import traceback

from fastapi import FastAPI, WebSocket, Response
from fastapi.logger import logger

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Info

from magellon_sdk.bus.bootstrap import install_rmq_bus
from magellon_sdk.categories.contract import CTF

from magellon_sdk.models import TaskDto

from core.settings import AppSettingsSingleton
from plugin import CtfBrokerRunner, CtfPlugin, build_ctf_result
from service.service import do_execute, check_requirements, get_manifest, get_plugin_info
from core.logger_config import setup_logging
from dotenv import load_dotenv

# import pdb


plugin_info = get_plugin_info()
setup_logging()
logger = logging.getLogger(__name__)

# Install the Rich error handler
traceback.install()

load_dotenv()

app = FastAPI(debug=False,
              title=f"Magellan {plugin_info.name}",
              description=plugin_info.description,
              version=plugin_info.version)

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"],
                   allow_credentials=True)

local_hostname = socket.gethostname()
# local_ip_address = socket.gethostbyname(local_hostname)

if os.environ.get('APP_ENV', "development") == 'production':
    local_ip_address = AppSettingsSingleton.get_instance().LOCAL_IP_ADDRESS
else:
    local_ip_address = socket.gethostbyname(local_hostname)
local_port_number = AppSettingsSingleton.get_instance().PORT_NUMBER

# local_ip_address = "host.docker.internal"
# local_ip_address = "host.docker.internal"
# local_port_number = uvicorn.Config(app).port

i = Info('plugin', 'information about magellons plugin')
if plugin_info.description is not None:
    i.info({'name': plugin_info.name, 'description': plugin_info.description, 'instance': plugin_info.instance_id})
else:
    i.info({'name': plugin_info.name, 'description': 'No description', 'instance': plugin_info.instance_id})


_runner: CtfBrokerRunner | None = None
_plugin = CtfPlugin()


@app.on_event("startup")
async def startup_event():
    """MB4.2: install the process-wide MessageBus, pre-warm the
    step-event publisher, then spin up the broker runner on a daemon
    thread. Replaces the hand-rolled core.rabbitmq_consumer_engine."""
    global _runner
    try:
        rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
        install_rmq_bus(rmq)

        # Pre-warm the step-event publisher so the first task doesn't pay
        # the cold-start cost (NATS connect attempt + JetStream add_stream
        # timeout, then RMQ exchange declare). Without this, _make_reporter
        # races the first dispatch and times out → those tasks emit no
        # events. Fire-and-forget on the plugin's dedicated daemon loop.
        try:
            from plugin.plugin import _get_loop
            from service.step_events import get_publisher
            asyncio.run_coroutine_threadsafe(get_publisher(), _get_loop())
            logger.info("step-event publisher pre-warm scheduled")
        except Exception:
            logger.exception("step-event publisher pre-warm scheduling failed (non-fatal)")

        _runner = CtfBrokerRunner(
            plugin=_plugin,
            settings=rmq,
            in_queue=rmq.QUEUE_NAME,
            out_queue=rmq.OUT_QUEUE_NAME,
            result_factory=build_ctf_result,
            contract=CTF,
        )
        threading.Thread(
            target=_runner.start_blocking, name="ctf-broker-runner", daemon=True,
        ).start()
        logger.info("CtfBrokerRunner started")
    except Exception:
        logger.exception("CtfBrokerRunner: startup failed")
        raise


# def callback(key, value, **kwargs):
#     print(f"Key '{key}' updated. New value: {value}")


@app.on_event("shutdown")
async def shutdown_event():
    if _runner is not None:
        try:
            _runner.stop()
        except Exception:
            logger.exception("CtfBrokerRunner: stop() raised")


@app.get("/", summary="Get Plugin Information")
async def root():
    # pdb.set_trace()
    return {"message": "Welcome ", "plugin_info": plugin_info.dict()}


@app.get("/manifest", summary="Plugin capability manifest")
async def manifest_endpoint():
    """Capability manifest for the plugin manager — same shape as
    in-house plugins' ``instance.manifest()``."""
    return get_manifest().model_dump(mode="json")


# This function checks for all the requirements of the plugin, attempts to install and fix them,
# and returns success or failure codes along with relevant messages and instructions for the user.
@app.get("/setup", summary="Check and Set Up Plugin Requirements")
async def setup():
    logger.info("Executing setup endpoint")
    return await check_requirements()


@app.post("/execute", summary="Execute Plugin Operation")
async def execute_endpoint(request: TaskDto):
    return await do_execute(request)


Instrumentator().instrument(app).expose(app)


@app.get('/health')
async def health_check():
    return {'status': 'ok'}


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(status_code=400,
                        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"})

# Data to be streamed (replace with your data source)
# async def get_data():
#     for i in range(10):
#         await asyncio.sleep(1)
#         yield {"data": f"Message {i+1}"}


# @app.websocket("/sse")
# async def sse_endpoint(websocket: WebSocket):
#     logger.info("SSE endpoint")
#     await websocket.accept()
#     await websocket.send_text("Hi")
#     # Stream data to the client
#     async for message in get_data():
#         await websocket.send_text(json.dumps(message))


# def setup_metrics_route():
#     # Add prometheus asgi middleware to route /metrics requests
#     metrics_app = make_asgi_app()
#     app.mount("/metrics", metrics_app)
# setup_metrics_route()


# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)
