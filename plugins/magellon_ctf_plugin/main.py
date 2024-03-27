import logging
import threading

from fastapi import FastAPI
from fastapi.logger import logger
from rich import traceback

from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import make_asgi_app, Info

from core.execution_engine import worker_engine
from core.model_dto import CryoEmFftTaskDetailDto
# from core.process_async_rabbitmq import consume_queue, publish_message
from core.settings import AppSettingsSingleton
from service.info import get_plugin_info
from service.service import execute, InputParams, check_requirements
from core.logger_config import setup_logging

plugin_info = get_plugin_info()
setup_logging()
logger = logging.getLogger(__name__)

# Install the Rich error handler
traceback.install()

app = FastAPI(debug=False, title=f"Magellan {plugin_info.name}", description=plugin_info.description,version=plugin_info.version)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],allow_credentials=True)

i = Info('plugin', 'information about magellons plugin')
if plugin_info.description is not None:
    i.info({'name': plugin_info.name, 'description': plugin_info.description, 'instance': plugin_info.instance_id})
else:
    i.info({'name': plugin_info.name, 'description': 'No description', 'instance': plugin_info.instance_id})


@app.on_event("startup")
async def startup_event():
    rabbitmq_thread = threading.Thread(target=worker_engine, daemon=True)
    rabbitmq_thread.start()


@app.on_event("shutdown")
async def shutdown_event():
    # Your cleanup logic here
    pass


@app.get("/", summary="Get Plugin Information")
async def root():
    number = AppSettingsSingleton.get_instance().port_number
    logger.info("Hello behdad %s", number)
    return {"message": "Welcome ", "plugin_info": plugin_info.dict()}


# This function checks for all the requirements of the plugin, attempts to install and fix them,
# and returns success or failure codes along with relevant messages and instructions for the user.
@app.get("/setup", summary="Check and Set Up Plugin Requirements")
async def setup():
    logger.info("Executing setup endpoint")
    return await check_requirements()


@app.post("/execute", summary="Execute Plugin Operation")
async def execute(request: CryoEmFftTaskDetailDto):
    return await execute(request)


Instrumentator().instrument(app).expose(app)


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
