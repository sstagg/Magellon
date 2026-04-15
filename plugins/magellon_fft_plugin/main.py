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
from core.rabbitmq_consumer_engine import consumer_engine
from core.settings import AppSettingsSingleton
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


@app.on_event("startup")
async def startup_event():
    try:
        # Discovery + dynamic config ride the broker now (P6/P7).
        rabbitmq_thread = threading.Thread(target=consumer_engine, daemon=True)
        rabbitmq_thread.start()
    except Exception as e:
        print(f"Error during startup: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    pass


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
