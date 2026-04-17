import asyncio
import logging
import os
import socket
import threading

# Step-event observability defaults — flipped on so this plugin emits
# lifecycle events without operators having to set env vars by hand.
# RMQ mirror is enabled because most local-dev setups don't run NATS
# JetStream; CoreService's RMQ step-event forwarder delivers events
# to the React UI in those setups. ``setdefault`` lets production
# deployments that explicitly turn these off still win.
# Must run before SDK imports below — the publisher reads these at init.
os.environ.setdefault("MAGELLON_STEP_EVENTS_ENABLED", "1")
os.environ.setdefault("MAGELLON_STEP_EVENTS_RMQ", "1")

from rich import traceback

from fastapi import FastAPI, HTTPException
from fastapi.logger import logger

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Info

from core.rabbitmq_consumer_engine import consumer_engine
from core.model_dto import CryoEmMotionCorTaskData, TaskDto,CreateFrameAlignRequest
from core.settings import AppSettingsSingleton
from service.service import do_execute, check_requirements, get_manifest, get_plugin_info
from core.logger_config import setup_logging
from utils import createframealignCenterImage, createframealignImage
# import pdb


plugin_info = get_plugin_info()
setup_logging()
logger = logging.getLogger(__name__)

# Install the Rich error handler
traceback.install()

app = FastAPI(debug=False, title=f"Magellan {plugin_info.name}", description=plugin_info.description,
              version=plugin_info.version)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
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


@app.on_event("startup")
async def startup_event():
    try:
        # Pre-warm the step-event publisher so the first task doesn't pay
        # the cold-start cost (NATS connect attempt + JetStream add_stream
        # timeout, then RMQ exchange declare). Fire-and-forget on the
        # consumer engine's daemon loop so it completes in the background
        # before the first task arrives.
        try:
            from core.rabbitmq_consumer_engine import _loop
            from service.step_events import get_publisher
            asyncio.run_coroutine_threadsafe(get_publisher(), _loop)
            logger.info("step-event publisher pre-warm scheduled")
        except Exception:
            logger.exception("step-event publisher pre-warm scheduling failed (non-fatal)")

        # Start RabbitMQ consumer thread. Discovery + dynamic config
        # ride the broker now (P6/P7) — Consul is gone.
        rabbitmq_thread = threading.Thread(target=consumer_engine, daemon=True)
        rabbitmq_thread.start()
    except Exception as e:
        print(f"Error during startup: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    # Your cleanup logic here
    pass


@app.get("/", summary="Get Plugin Information")
async def root():
    number = AppSettingsSingleton.get_instance().PORT_NUMBER
    # pdb.set_trace()
    logger.info("Hello behdad %s", number)
    return {"message": "Welcome ", "plugin_info": plugin_info.dict()}


@app.get("/manifest", summary="Plugin capability manifest")
async def manifest_endpoint():
    """Capability manifest — the plugin manager relies on this to avoid
    scheduling MotionCor anywhere that can't satisfy its GPU / memory
    demands. Same shape as in-house plugins' ``instance.manifest()``."""
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



#usage 
# curl -X 'POST' 'http://127.0.0.1:8001/create-frame-align-center-image/'     -H 'Content-Type: application/json'     -d '{
    #    "outputmrcpath": "/mnt/c/Users/punee/Desktop/test_jobs/49f76a1a-7b91-41ce-b5d0-8f44c928cc4d/output.files_DW.mrc",
    #    "data": [[0, 10, 20], [1, -5, 15]],
    #    "directory_path": "/mnt/c/Users/punee/Desktop/test_jobs/49f76a1a-7b91-41ce-b5d0-8f44c928cc4d",
    #    "originalsize": [4096, 4096]
    #  }'
@app.post("/create-frame-align-center-image/")
async def create_frame_align_center_image(request: CreateFrameAlignRequest):
    try:
        modified_center_image_path = createframealignCenterImage(
            request.outputmrcpath, request.data, request.directory_path, request.originalsize
        )
        return {"message": "Image created successfully","modified_center_image_path": modified_center_image_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
#usage
# curl -X 'POST' 'http://127.0.0.1:8001/create-frame-align-image/'     -H 'Content-Type: application/json'     -d '{
#        "outputmrcpath": "/mnt/c/Users/punee/Desktop/test_jobs/49f76a1a-7b91-41ce-b5d0-8f44c928cc4d/output.files_DW.mrc",
#        "data": [[0, 896, 895, -1,-2 ,0], [1,896,896, -5, 15,0]],
#        "directory_path": "/mnt/c/Users/punee/Desktop/test_jobs/49f76a1a-7b91-41ce-b5d0-8f44c928cc4d",
#        "originalsize": [4096, 4096]
#      }'
@app.post("/create-frame-align-image/")
async def create_frame_align_image(request: CreateFrameAlignRequest):
    try:
        
        modified_image_path = createframealignImage(
            request.outputmrcpath, request.data, request.directory_path, request.originalsize
        )
        return {"message": "Image created successfully", "modified_image_path": modified_image_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


Instrumentator().instrument(app).expose(app)

# Define a health check route
@app.get('/health')
async def health_check():
    logger.info("Logger is working")
    print("Health check")
    return {'status': 'ok'}

@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(status_code=400,
                        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"})

# def setup_metrics_route():
#     # Add prometheus asgi middleware to route /metrics requests
#     metrics_app = make_asgi_app()
#     app.mount("/metrics", metrics_app)
# setup_metrics_route()


# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)
