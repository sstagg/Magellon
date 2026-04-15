import logging
import os
import socket
import threading

from dotenv import load_dotenv
from fastapi import FastAPI
from prometheus_client import Info
from prometheus_fastapi_instrumentator import Instrumentator
from rich import traceback
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from core.logger_config import setup_logging
from core.model_dto import TaskDto
from core.settings import AppSettingsSingleton
from magellon_sdk.categories.contract import FFT
from service.plugin import FftBrokerRunner, FftPlugin, build_fft_result
from service.service import check_requirements, do_execute, get_manifest, get_plugin_info


plugin_info = get_plugin_info()
setup_logging()
logger = logging.getLogger(__name__)

traceback.install()
load_dotenv()

app = FastAPI(
    debug=False,
    title=f"Magellan {plugin_info.name}",
    description=plugin_info.description,
    version=plugin_info.version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

local_hostname = socket.gethostname()
if os.environ.get("APP_ENV", "development") == "production":
    local_ip_address = AppSettingsSingleton.get_instance().LOCAL_IP_ADDRESS
else:
    local_ip_address = socket.gethostbyname(local_hostname)
local_port_number = AppSettingsSingleton.get_instance().PORT_NUMBER


i = Info("plugin", "information about magellons plugin")
if plugin_info.description is not None:
    i.info(
        {
            "name": plugin_info.name,
            "description": plugin_info.description,
            "instance": plugin_info.instance_id,
        }
    )
else:
    i.info(
        {
            "name": plugin_info.name,
            "description": "No description",
            "instance": plugin_info.instance_id,
        }
    )


_runner: FftBrokerRunner | None = None


@app.on_event("startup")
async def startup_event():
    """Spin up the broker runner on a daemon thread.

    The runner harness (P5) owns the pika loop, discovery + heartbeat
    (P6), dynamic config (P7), provenance stamping (P4), and typed
    failure routing (P2). We just hand it the plugin + queue names.
    """
    global _runner
    try:
        rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
        _runner = FftBrokerRunner(
            plugin=FftPlugin(),
            settings=rmq,
            in_queue=rmq.QUEUE_NAME,
            out_queue=rmq.OUT_QUEUE_NAME,
            result_factory=build_fft_result,
            contract=FFT,
        )
        threading.Thread(
            target=_runner.start_blocking, name="fft-broker-runner", daemon=True
        ).start()
    except Exception as e:
        logger.exception("Error during startup: %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    if _runner is not None:
        try:
            _runner.stop()
        except Exception:
            logger.exception("FftBrokerRunner: stop() raised")


@app.get("/", summary="Get Plugin Information")
async def root():
    return {"message": "Welcome ", "plugin_info": plugin_info.dict()}


@app.get("/manifest", summary="Plugin capability manifest")
async def manifest_endpoint():
    """Capability manifest consumed by the CoreService plugin manager.

    Same shape as in-house plugins' ``instance.manifest()`` output, so
    the manager can treat this plugin uniformly whether it's mounted
    in-process or running in its own container.
    """
    return get_manifest().model_dump(mode="json")


@app.get("/setup", summary="Check and Set Up Plugin Requirements")
async def setup():
    logger.info("Executing setup endpoint")
    return await check_requirements()


@app.post("/execute", summary="Execute Plugin Operation")
async def execute_endpoint(request: TaskDto):
    return await do_execute(request)


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
