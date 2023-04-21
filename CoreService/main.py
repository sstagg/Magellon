from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from controllers.camera_controller import camera_router
from controllers.db_controller import db_router
from controllers.graph_controller import graph_router
from controllers.home_controller import home_router
from controllers.image_processing_controller import image_processing_router
from controllers.particle_picking_jobitem_controller import ppji_router
from controllers.webapp_controller import webapp_router

from database import engine, session_local
import logging

from logger_config import LOGGING_CONFIG

logger = logging.getLogger(__name__)
# FORMAT = "%(levelname)s:%(message)s"
# logging.basicConfig(format=FORMAT, level=logging.INFO)
logging.config.dictConfig(LOGGING_CONFIG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


app = FastAPI(title="Magellon Core Service", description="Magellon Core Service that provides main services",
              version="1.0.0", )

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
                   allow_credentials=True)

app.dbengine = engine
app.dbsession = session_local

app.include_router(home_router)
app.include_router(db_router, tags=["Database"], prefix="/db")
app.include_router(camera_router, tags=["Cameras"], prefix="/db/cameras")
app.include_router(ppji_router, tags=["Particle Picking Job Item"], prefix="/db/ppji")
app.include_router(image_processing_router, tags=['Image Processing'], prefix="/image")
app.include_router(webapp_router, tags=['Image Viewer - WebApp'], prefix="/web")
app.include_router(graph_router, tags=['Graphs'], prefix="/graphs")


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    base_error_message = f"Failed to execute: {request.method}: {request.url}"
    return JSONResponse(status_code=400, content={"message": f"{base_error_message}. Detail: {err}"})


