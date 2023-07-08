import socket

import fastapi
import uvicorn
from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette_graphene3 import GraphQLApp, make_graphiql_handler
from strawberry.fastapi import GraphQLRouter

from config import register_with_consul, CONSUL_SERVICE_NAME, CONSUL_SERVICE_ID
from controllers.camera_controller import camera_router
from controllers.db_controller import db_router
from controllers.graph_controller import graph_router
from controllers.home_controller import home_router
from controllers.image_processing_controller import image_processing_router
from controllers.particle_picking_jobitem_controller import ppji_router
from controllers.slack_controller import slack_router

from controllers.webapp_controller import webapp_router

from prometheus_fastapi_instrumentator import Instrumentator

from database import engine, session_local, get_db
import logging

from logger_config import LOGGING_CONFIG

# from starlette_graphene3 import GraphQLApp
from sqlalchemy.orm import Session, joinedload

from models import graphql_strawberry_schema
from models.graphql_strawberry_schema import strawberry_graphql_router

logger = logging.getLogger(__name__)
# FORMAT = "%(levelname)s:%(message)s"
# logging.basicConfig(format=FORMAT, level=logging.INFO)
logging.config.dictConfig(LOGGING_CONFIG)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

app = FastAPI(title="Magellon Core Service", description="Magellon Core Service that provides main services",
              version="1.0.0", )

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
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

app.include_router(home_router, tags=["Home"])
app.include_router(db_router, tags=["Database"], prefix="/db")
app.include_router(camera_router, tags=["Cameras"], prefix="/db/cameras")
app.include_router(ppji_router, tags=["Particle Picking Job Item"], prefix="/db/ppji")
app.include_router(image_processing_router, tags=['Image Processing'], prefix="/image")
app.include_router(webapp_router, tags=['Image Viewer - WebApp'], prefix="/web")
app.include_router(graph_router, tags=['Graphs'], prefix="/graphs")
app.include_router(slack_router, tags=['Communication'], prefix='/io')
Instrumentator().instrument(app).expose(app)

app.include_router(strawberry_graphql_router, prefix="/graphql")
# app.add_route("/graphql", GraphQLApp(schema=schema))
# @app.post("/graphql")
# async def post_graphql(
#         request: fastapi.Request,
#         session: Session = Depends(get_db()),
# ):
#     content_type = request.headers.get("Content-Type", "")
#
#     if "application/json" in content_type:
#         data = await request.json()
#
#     elif "application/graphql" in content_type:
#         body = await request.body()
#         text = body.decode()
#         data = {"query": text}
#
#     elif "query" in request.query_params:
#         data = request.query_params
#
#     else:
#         raise fastapi.HTTPException(
#             status_code=fastapi.status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
#             detail="Unsupported Media Type",
#         )
#
#     if not (q_body := data.get("query")):
#         raise fastapi.HTTPException(status_code=400, detail=f"Unsupported method: {q_body}")
#
#     res = graphene_schema.execute(
#         q_body,
#         context_value={"request": request, "session": session},
#     )
#
#     return res.to_dict()

# app.mount("/graphql", GraphQLApp(graphene_schema, on_get=make_graphiql_handler()))  # Graphiql IDE


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    base_error_message = f"Failed to execute: {request.method}: {request.url}"
    return JSONResponse(status_code=400, content={"message": f"{base_error_message}. Detail: {err}"})
