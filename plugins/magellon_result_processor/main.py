import asyncio
import json
import logging
import os
import socket
import threading

from rich import traceback

from fastapi import FastAPI
from fastapi.logger import logger

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, StreamingResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Info

from core.consul import register_with_consul, init_consul_client, get_kv_value, get_services
from core.rabbitmq_consumer_engine import consumer_engine
from core.model_dto import TaskDto
from core.settings import AppSettingsSingleton
from service.service import do_execute, check_requirements, get_plugin_info
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


@app.on_event("startup")
async def startup_event():
    try:
        # Start RabbitMQ consumer thread
        rabbitmq_thread = threading.Thread(target=consumer_engine, daemon=True)
        rabbitmq_thread.start()
        # Initialize Consul client
        init_consul_client()
        # Register with Consul
        register_with_consul(
            app,
            local_ip_address,
            AppSettingsSingleton.get_instance().consul_settings.CONSUL_SERVICE_NAME,
            AppSettingsSingleton.get_instance().consul_settings.CONSUL_SERVICE_ID,
            local_port_number,
            'health'
        )

        # configurations_data = get_kv_value("magellon-ctf-service-configuration")
        # AppSettingsSingleton.update_settings_from_yaml(configurations_data)
        # services = get_services("magellon-ctf-service")


    except Exception as e:
        print(f"Error during startup: {e}")


# def callback(key, value, **kwargs):
#     print(f"Key '{key}' updated. New value: {value}")


@app.on_event("shutdown")
async def shutdown_event():
    # Your cleanup logic here
    pass


@app.get("/", summary="Get Plugin Information")
async def root():
    # pdb.set_trace()
    return {"message": "Welcome ", "plugin_info": plugin_info.dict()}


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
