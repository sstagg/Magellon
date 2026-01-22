import os
import socket
import json
# import sys
# import traceback
# from rich import traceback as rich_traceback

# import fastapi
import uvicorn
from PIL.Image import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
# from rich.logging import RichHandler
from rich.traceback import Traceback
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette import status as starlette_status
import secrets


from configs.production_test import production_intilization
from config import app_settings
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
from controllers.import_export_controller import export_router
# from controllers.particle_picking_jobitem_controller import ppji_router
from controllers.slack_controller import slack_router

from controllers.security.auth_controller import router as auth_router
from controllers.security.sys_sec_user_controller import sys_sec_user_router
from controllers.security.sys_sec_role_controller import sys_sec_role_router
from controllers.security.sys_sec_user_role_controller import sys_sec_user_role_router
from controllers.security.sys_sec_permission_controller import sys_sec_permission_router
from controllers.security.sys_sec_permission_mgmt_controller import sys_sec_permission_mgmt_router
from controllers.security.session_access_controller_v2 import session_access_router
from controllers.schema_controller import schema_router


from controllers.test_controller import test_router
from controllers.test_rls_controller import test_rls_router

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
from services.casbin_service import CasbinService
from services.casbin_policy_sync_service import CasbinPolicySyncService

rich.traceback.install(show_locals=True)

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[magenta]{title}[/magenta]')

logger = logging.getLogger(__name__)
logging.config.dictConfig(LOGGING_CONFIG)
# Set SQLAlchemy logging to WARNING to reduce noise in logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


production_intilization()


# Create a RichHandler for the logger
# handler = RichHandler()
# handler.setLevel(logging.DEBUG)
#
# # Set the formatter for the RichHandler
# handler.setFormatter(logging.Formatter("%(message)s"))
# # Add the RichHandler to the logger
# logger.addHandler(handler)

# Initialize HTTP Basic Authentication for API docs
security = HTTPBasic(auto_error=False)

def verify_docs_credentials(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Verify authentication credentials for API documentation access.

    Supports TWO authentication methods:
    1. HTTP Basic Auth - username/password from api_docs_settings
    2. JWT Bearer Token - same token used for API endpoints

    Users can authenticate using either method.
    """
    if not app_settings.api_docs_settings.ENABLED:
        # If authentication is disabled, allow access
        return True

    # Method 1: Try JWT Bearer Token authentication first
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        try:
            # Import here to avoid circular imports
            from dependencies.auth import decode_token

            token = authorization.replace("Bearer ", "")
            payload = decode_token(token)

            if payload:
                user_id = payload.get("sub")
                username = payload.get("username", "unknown")
                logger.info(f"Successful API docs authentication via JWT for user: {username}")
                return True
        except Exception as e:
            logger.debug(f"JWT token validation failed for docs access: {str(e)}")
            # Fall through to Basic Auth

    # Method 2: Try HTTP Basic Authentication
    if credentials:
        # Use secrets.compare_digest to prevent timing attacks
        correct_username = secrets.compare_digest(
            credentials.username.encode("utf8"),
            app_settings.api_docs_settings.USERNAME.encode("utf8")
        )
        correct_password = secrets.compare_digest(
            credentials.password.encode("utf8"),
            app_settings.api_docs_settings.PASSWORD.encode("utf8")
        )

        if correct_username and correct_password:
            logger.info(f"Successful API docs authentication via Basic Auth for user: {credentials.username}")
            return True
        else:
            logger.warning(f"Failed API docs Basic Auth attempt from username: {credentials.username}")

    # Both methods failed
    raise HTTPException(
        status_code=starlette_status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials for API documentation. Use HTTP Basic Auth (username/password) or Bearer token.",
        headers={"WWW-Authenticate": "Basic"},
    )

# Disable default docs and openapi endpoints
app = FastAPI(
    title="Magellon Core Service",
    description="Magellon Core Service that provides main services",
    version="1.0.0",
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
    openapi_url=None  # Disable default openapi.json
)

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_methods=["*"],
                   allow_headers=["*"],
                   allow_credentials=True)


# Custom protected docs endpoints
@app.get("/docs", include_in_schema=False)
async def get_documentation(authenticated: bool = Depends(verify_docs_credentials)):
    """
    Protected Swagger UI documentation endpoint.
    Requires HTTP Basic Authentication (username/password from api_docs_settings).
    """
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{app.title} - Documentation",
        swagger_favicon_url="/static/favicon.ico"
    )


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(authenticated: bool = Depends(verify_docs_credentials)):
    """
    Protected ReDoc documentation endpoint.
    Requires HTTP Basic Authentication (username/password from api_docs_settings).

    ReDoc provides a cleaner, three-panel documentation interface as an alternative to Swagger UI.
    Note: OpenAPI schema is inlined to avoid authentication issues with AJAX requests.
    """
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Properly serialize the OpenAPI schema to JSON
    openapi_json = json.dumps(openapi_schema)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{app.title} - ReDoc</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="icon" type="image/x-icon" href="/static/favicon.ico">
    </head>
    <body>
        <div id="redoc-container"></div>
        <script src="https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js"></script>
        <script>
            var spec = {openapi_json};
            Redoc.init(spec, {{}}, document.getElementById('redoc-container'));
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(authenticated: bool = Depends(verify_docs_credentials)):
    """
    Protected OpenAPI schema endpoint.
    Requires HTTP Basic Authentication (username/password from api_docs_settings).
    """
    return JSONResponse(
        content=get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
    )


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
app.include_router(export_router, tags=["Export"], prefix="/export")
app.include_router(test_router, tags=["Test"], prefix="/test")
app.include_router(camera_router, tags=["Cameras"], prefix="/db/cameras")
app.include_router(image_meta_data_category_router, tags=["MetaData Category"], prefix="/db/meta-data-category")
app.include_router(image_meta_data_router, tags=["MetaData"], prefix="/db/meta-data")
app.include_router(deployment_docker_router, tags=["Docker"], prefix="/deployment/docker")
app.include_router(image_processing_router, tags=['Image Processing'], prefix="/image")
app.include_router(webapp_router, tags=['Image Viewer - WebApp'], prefix="/web")
app.include_router(graph_router, tags=['Graphs'], prefix="/graphs")
app.include_router(slack_router, tags=['Communication'], prefix='/io')

# Authentication - must be registered before protected endpoints
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

app.include_router(sys_sec_user_router, prefix="/db/security/users", tags=["Security - Users"])
app.include_router(sys_sec_role_router, prefix="/db/security/roles", tags=["Security - Roles"])
app.include_router(sys_sec_user_role_router, prefix="/db/security/user-roles", tags=["Security - User Roles"])
app.include_router(sys_sec_permission_router, prefix="/db/security/permissions", tags=["Security - Permissions"])
app.include_router(sys_sec_permission_mgmt_router, prefix="/db/security", tags=["Security - Permission Management"])
app.include_router(session_access_router, tags=["Security - Session Access"])
app.include_router(test_rls_router, tags=["RLS Testing"])
app.include_router(schema_router, tags=["Database Schema"])


Instrumentator().instrument(app).expose(app)

app.include_router(strawberry_graphql_router, prefix="/graphql")


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    import threading
    
    logger.info("=" * 60)
    logger.info("Starting Magellon Core Service...")
    logger.info("=" * 60)

    # Initialize Casbin Authorization
    try:
        logger.info("Initializing Casbin authorization system...")
        CasbinService.initialize()

        # Sync policies from sys_sec_* tables
        logger.info("Syncing policies from sys_sec_* tables...")
        db = session_local()
        try:
            stats = CasbinPolicySyncService.sync_all_policies(db, clear_existing=True)
            logger.info(f"[OK] Synced {stats['total_policies']} policies and {stats['user_roles']} role assignments")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize Casbin: {e}")
        logger.warning("[WARNING] Application will start but authorization may not work correctly!")

    # Start motioncor test result processor thread
    try:
        from core.motioncor_test_result_processor import result_consumer_engine
        logger.info("Starting motioncor test result processor...")
        result_processor_thread = threading.Thread(target=result_consumer_engine, daemon=True)
        result_processor_thread.start()
        logger.info("[OK] Motioncor test result processor started")
    except Exception as e:
        logger.error(f"[WARNING] Failed to start result processor: {e}")

    logger.info("=" * 60)
    logger.info("[OK] Magellon Core Service started successfully")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("=" * 60)
    logger.info("Shutting down Magellon Core Service...")
    logger.info("=" * 60)


@app.exception_handler(Exception)
def app_exception_handler(request, err):
    return JSONResponse(status_code=400,
                        content={"message": f"Failed to execute: {request.method}: {request.url}. Detail: {err}"})
