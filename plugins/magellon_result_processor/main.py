import logging
import os
import socket
from typing import Optional

from rich import traceback

from fastapi import FastAPI, Depends
from fastapi.logger import logger
from sqlalchemy.orm import Session

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Info

from magellon_sdk.bus.bootstrap import install_rmq_bus

from magellon_sdk.models import TaskResultDto

from core.bus_consumer import start_result_consumers
from core.settings import AppSettingsSingleton
from services import service
from services.service import do_execute, check_requirements, get_manifest, get_plugin_info
from core.logger_config import setup_logging
from dotenv import load_dotenv

from core.database import engine, session_local, get_db

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

app.dbengine = engine
app.dbsession = session_local

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
    """MB4.4: install the process-wide MessageBus, then register one
    bus consumer per ``OUT_QUEUES`` entry. The binder owns the pika
    loop, ack/nack/DLQ classification, and reconnection — this module
    only declares what to subscribe to and what handler to run.
    Replaces the hand-rolled ``rabbitmq_consumer_engine.consumer_engine``
    daemon thread.
    """
    try:
        rmq = AppSettingsSingleton.get_instance().rabbitmq_settings
        install_rmq_bus(rmq)
        app.state.result_consumer_handles = start_result_consumers()
        logger.info(
            "result_processor: started %d bus consumer(s)",
            len(app.state.result_consumer_handles),
        )
    except Exception as e:
        logger.exception("result_processor: startup failed")
        # Surface so deployments don't think the process is healthy
        # while the bus consumers silently failed to attach.
        raise


# def callback(key, value, **kwargs):
#     print(f"Key '{key}' updated. New value: {value}")


@app.on_event("shutdown")
async def shutdown_event():
    handles = getattr(app.state, "result_consumer_handles", []) or []
    for h in handles:
        try:
            h.close()
        except Exception:
            logger.exception("result_processor: consumer handle close failed")


@app.get("/", summary="Get Plugin Information")
async def root():
    # pdb.set_trace()
    return {"message": "Welcome ", "plugin_info": plugin_info.dict()}


@app.get("/manifest", summary="Plugin capability manifest")
async def manifest_endpoint():
    return get_manifest().model_dump(mode="json")

@app.get('/cameras')
async def get_all_cameras(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the cameras camerad in database
    """
    cameras= await service.get_all_cameras(name, db)
    return {"result returned"}

# This function checks for all the requirements of the plugin, attempts to install and fix them,
# and returns success or failure codes along with relevant messages and instructions for the user.
@app.get("/setup", summary="Check and Set Up Plugin Requirements")
async def setup():
    logger.info("Executing setup endpoint")
    return await check_requirements()


@app.post("/execute", summary="Execute Plugin Operation")
async def execute_endpoint(request: TaskResultDto):
    # The HTTP /execute path mirrors what the RMQ consumer does on each
    # incoming result envelope — it expects a TaskResultDto, not a TaskDto.
    # do_execute opens its own DB session via TaskOutputProcessor, so
    # there's no db dependency to pass through.
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
