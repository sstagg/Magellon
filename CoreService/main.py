import os
import socket
# import sys
# import traceback
# from rich import traceback as rich_traceback

# import fastapi
import uvicorn
from PIL.Image import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
# from rich.logging import RichHandler
from rich.traceback import Traceback
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles


from configs.production_test import production_intilization
# from starlette_graphene3 import GraphQLApp, make_graphiql_handler
# from strawberry.fastapi import GraphQLRouter

# from config import register_with_consul, CONSUL_SERVICE_NAME, CONSUL_SERVICE_ID
from controllers.camera_controller import camera_router
from controllers.db_controller import db_router
from controllers.deployment_docker_controller import deployment_docker_router
from controllers.graph_controller import graph_router
from controllers.home_controller import home_router
from controllers.image_meta_data_category_controller import image_meta_data_category_router
from controllers.image_meta_data_controller import image_meta_data_router
from controllers.image_processing_controller import image_processing_router
# from controllers.particle_picking_jobitem_controller import ppji_router
from controllers.slack_controller import slack_router

from controllers.webapp_controller import webapp_router

from prometheus_fastapi_instrumentator import Instrumentator
from rich import print
import pyfiglet as pyfiglet

from database import engine, session_local
import logging

from logger_config import LOGGING_CONFIG

# from models import graphql_strawberry_schema
from models.graphql_strawberry_schema import strawberry_graphql_router
# from rich.console import Console

# from rich import get_console

import rich.traceback

from services.importers.TiffHelper import convert_tiff_to_jpeg, parse_tif

rich.traceback.install(show_locals=True)

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[magenta]{title}[/magenta]')

logger = logging.getLogger(__name__)
logging.config.dictConfig(LOGGING_CONFIG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


production_intilization()


# Create a RichHandler for the logger
# handler = RichHandler()
# handler.setLevel(logging.DEBUG)
#
# # Set the formatter for the RichHandler
# handler.setFormatter(logging.Formatter("%(message)s"))
# # Add the RichHandler to the logger
# logger.addHandler(handler)

app = FastAPI(title="Magellon Core Service", description="Magellon Core Service that provides main services",
              version="1.0.0", )

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"],
                   allow_credentials=True)

# Get the IP address and port
# ip_address = uvicorn.Config(app).host
# Get the hostname of the computer
local_hostname = socket.gethostname()
local_ip_address = socket.gethostbyname(local_hostname)
local_port_number = uvicorn.Config(app).port

# Register application with Consul
# register_with_consul(app,local_ip_address, CONSUL_SERVICE_NAME, CONSUL_SERVICE_ID, local_port_number, 'health')

app.dbengine = engine
app.dbsession = session_local

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


@app.post("/convert-tiff-to-jpeg/")
async def convert_tiff_to_jpeg_route(file: UploadFile = File(...)):
    # Ensure the file is a TIFF
    if not file.filename.lower().endswith(".tiff"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a TIFF file.")
    try:
        # Define the file paths

        tiff_path = "C:/temp/test/" + file.filename
        jpeg_path = tiff_path.rsplit(".", 1)[0] + ".jpeg"
        # Save the uploaded TIFF file temporarily
        # Parse the TIFF file
        result = parse_tif(tiff_path)
        convert_tiff_to_jpeg(tiff_path,jpeg_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting TIFF to JPEG: {str(e)}")
    # finally:
    #     os.remove(tiff_path)  # Clean up the TIFF file after conversion

    return JSONResponse(content={"message": "TIFF file converted to JPEG", "jpeg_path": jpeg_path})



app.include_router(home_router, tags=["Home"])
app.include_router(db_router, tags=["Database"], prefix="/db")
app.include_router(camera_router, tags=["Cameras"], prefix="/db/cameras")
app.include_router(image_meta_data_category_router, tags=["MetaData Category"], prefix="/db/meta-data-category")
app.include_router(image_meta_data_router, tags=["MetaData"], prefix="/db/meta-data")
app.include_router(deployment_docker_router, tags=["Docker"], prefix="/deployment/docker")

app.include_router(image_processing_router, tags=['Image Processing'], prefix="/image")
app.include_router(webapp_router, tags=['Image Viewer - WebApp'], prefix="/web")
app.include_router(graph_router, tags=['Graphs'], prefix="/graphs")
app.include_router(slack_router, tags=['Communication'], prefix='/io')
Instrumentator().instrument(app).expose(app)

app.include_router(strawberry_graphql_router, prefix="/graphql")


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(status_code=400,
                        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"})
