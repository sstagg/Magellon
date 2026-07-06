import asyncio
import os
import socket
import json

import socketio
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette import status as starlette_status
import secrets

from config import app_settings
from controllers.camera_controller import camera_router
from controllers.admin_broker_controller import admin_broker_router
from controllers.admin_dispatch_cache_controller import admin_dispatch_cache_router
from controllers.admin_plugin_install_controller import admin_plugin_install_router
from controllers.plugin_registry_controller import plugin_registry_router
from controllers.system_stats_controller import system_stats_router
from controllers.artifacts_controller import artifacts_router
from controllers.cancellation_controller import cancellation_router
from controllers.pipelines_controller import pipelines_router
from controllers.db_controller import db_router
from controllers.deployment_docker_controller import deployment_docker_router
from controllers.graph_controller import graph_router
from controllers.health_controller import health_router
from controllers.home_controller import home_router
from controllers.image_meta_data_category_controller import image_meta_data_category_router
from controllers.image_meta_data_controller import image_meta_data_router
from controllers.image_processing_controller import image_processing_router
from controllers.dispatch_controller import dispatch_router
from controllers.import_export_controller import export_router
from controllers.import_controller import import_router
from controllers.particle_export_pipeline_controller import particle_export_pipeline_router
from controllers.particle_picking_controller import particle_picking_router
from controllers.relion_controller import relion_router
from controllers.slack_controller import slack_router

from controllers.security.auth_controller import router as auth_router
from controllers.security.sys_sec_user_controller import sys_sec_user_router
from controllers.security.sys_sec_role_controller import sys_sec_role_router
from controllers.security.sys_sec_user_role_controller import sys_sec_user_role_router
from controllers.security.sys_sec_permission_controller import sys_sec_permission_router
from controllers.security.sys_sec_permission_mgmt_controller import sys_sec_permission_mgmt_router
from controllers.security.session_access_controller_v2 import session_access_router
from controllers.schema_controller import schema_router


from controllers.webapp_controller import webapp_router
from controllers.webapp_motioncor_controller import motioncor_router
from controllers.webapp_atlas_controller import atlas_router
from controllers.webapp_particles_controller import particles_router
from controllers.ops_controller import ops_router
from plugins.controller import plugins_router

from prometheus_fastapi_instrumentator import Instrumentator
from rich import print
import pyfiglet as pyfiglet

from database import engine, session_local
import logging

from logger_config import LOGGING_CONFIG

from models.graphql_strawberry_schema import strawberry_graphql_router

import rich.traceback

from core.dev_routes import dev_routes_enabled, register_dev_routes
from core.exception_handlers import register_exception_handlers
from core.request_observability import register_request_observability
from services.casbin_service import CasbinService
from services.casbin_policy_sync_service import CasbinPolicySyncService
from core.socketio_server import sio

rich.traceback.install(show_locals=True)

title = pyfiglet.figlet_format('Magellon', font='speed')
print(f'[magenta]{title}[/magenta]')

logger = logging.getLogger(__name__)
logging.config.dictConfig(LOGGING_CONFIG)
# Set SQLAlchemy logging to WARNING to reduce noise in logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Initialize HTTP Basic Authentication for API docs
security = HTTPBasic(auto_error=False)


def _is_production() -> bool:
    env = os.environ.get("APP_ENV") or getattr(app_settings, "ENV_TYPE", None)
    return str(env or "").lower() == "production"


def _csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _cors_origins() -> list[str]:
    configured = _csv_env("MAGELLON_CORS_ALLOWED_ORIGINS")
    if configured:
        return configured
    if _is_production():
        logger.warning(
            "MAGELLON_CORS_ALLOWED_ORIGINS is not set in production; "
            "falling back to localhost-only origins"
        )
        return [
            "http://localhost",
            "https://localhost",
            "http://127.0.0.1",
            "https://127.0.0.1",
        ]
    return ["*"]

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

register_exception_handlers(app, is_production=_is_production)
register_request_observability(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


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


# Get the hostname of the computer
local_hostname = socket.gethostname()
local_ip_address = socket.gethostbyname(local_hostname)
local_port_number = uvicorn.Config(app).port

app.dbengine = engine
app.dbsession = session_local

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")


app.include_router(home_router, tags=["Home"])
app.include_router(health_router, tags=["Health"], prefix="/health")
app.include_router(db_router, tags=["Database"], prefix="/db")
app.include_router(export_router, tags=["Export"], prefix="/export")
app.include_router(import_router, tags=["Import"], prefix="/export")
app.include_router(relion_router, tags=["RELION"], prefix="/export")
app.include_router(particle_export_pipeline_router, tags=["Particle Export Pipeline"], prefix="/export")
if dev_routes_enabled():
    register_dev_routes(app)
app.include_router(camera_router, tags=["Cameras"], prefix="/db/cameras")
app.include_router(image_meta_data_category_router, tags=["MetaData Category"], prefix="/db/meta-data-category")
app.include_router(image_meta_data_router, tags=["MetaData"], prefix="/db/meta-data")
app.include_router(deployment_docker_router, tags=["Docker"], prefix="/deployment/docker")
app.include_router(image_processing_router, tags=['Image Processing'], prefix="/image")
app.include_router(webapp_router, tags=['Image Viewer - WebApp'], prefix="/web")
app.include_router(motioncor_router, tags=['MotionCor & File Browsing'], prefix="/web")
app.include_router(atlas_router, tags=['Atlas'], prefix="/web")
app.include_router(particles_router, tags=['Particle Picking'], prefix="/web")
app.include_router(graph_router, tags=['Graphs'], prefix="/graphs")
app.include_router(slack_router, tags=['Communication'], prefix='/io')
# Phase 8 (2026-05-03) — PipelineRun rollup over child ImageJobs.
app.include_router(pipelines_router, tags=['Pipeline Runs'], prefix='/pipelines')
# Reviewer-flagged Medium #7 (2026-05-04) — read surface for the
# Artifact entity (particle_stack, class_averages, ...) so UI and
# orchestrators can resolve lineage over HTTP.
app.include_router(artifacts_router, tags=['Artifacts'], prefix='/artifacts')

# Authentication - must be registered before protected endpoints
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])

app.include_router(sys_sec_user_router, prefix="/db/security/users", tags=["Security - Users"])
app.include_router(sys_sec_role_router, prefix="/db/security/roles", tags=["Security - Roles"])
app.include_router(sys_sec_user_role_router, prefix="/db/security/user-roles", tags=["Security - User Roles"])
app.include_router(sys_sec_permission_router, prefix="/db/security/permissions", tags=["Security - Permissions"])
app.include_router(sys_sec_permission_mgmt_router, prefix="/db/security", tags=["Security - Permission Management"])
app.include_router(session_access_router, tags=["Security - Session Access"])
app.include_router(schema_router, tags=["Database Schema"])

# Plugins — simple direct HTTP (no RabbitMQ)
# Plugin-specific routes (template-pick, preview, retune) registered first so
# their literal paths match before the generic {plugin_id:path} catch-all.
app.include_router(
    particle_picking_router,
    tags=["Particle Picking"],
    prefix="/particle-picking",
)
# PT-6 (2026-05-04): generic dispatch surface — every category that
# pins a default plugin advertising Capability.SYNC / PREVIEW gets
# /dispatch/{category}/run, /preview, /preview/{id}/retune,
# /preview/{id}. Particle-picking keeps its feature-named URLs above
# for back-compat with the React UI; new categories adopt the
# generic shape automatically.
app.include_router(
    dispatch_router,
    tags=["Dispatch"],
    prefix="/dispatch",
)
app.include_router(plugins_router, tags=["Plugins"], prefix="/plugins")

# P9 — operator hard-stop levers (queue purge + container kill).
app.include_router(cancellation_router, tags=["Cancellation"], prefix="/cancellation")

# Pipeline-health page backend (Magellon-domain projection of RMQ state).
app.include_router(admin_broker_router, tags=["Admin - Broker"], prefix="/admin/broker")

# v1 plugin install pipeline (P7) — upload .mpn, upgrade, uninstall, list.
app.include_router(
    admin_plugin_install_router,
    tags=["Admin - Plugin Install"],
    prefix="/admin/plugins",
)

# PE2 dispatch cache — manual invalidation. Lookup + populate happen
# inline on the dispatch path; this endpoint is the operator escape
# hatch for clearing a bad run's cached output.
app.include_router(
    admin_dispatch_cache_router,
    tags=["Admin - Dispatch Cache"],
    prefix="/admin/dispatch-cache",
)

# PE4 registry — merge of hub index + local install state. Powers
# the React /panel/plugins/registry page.
app.include_router(
    plugin_registry_router,
    tags=["Plugin Registry"],
    prefix="/plugins/registry",
)

# Live host metrics for the plugins dashboard. Administrator-gated;
# polled by the React UI every 1-2 s.
app.include_router(
    system_stats_router,
    tags=["System Stats"],
    prefix="/system",
)


app.include_router(ops_router, tags=["Ops Log"], prefix="/web/ops")

Instrumentator().instrument(app).expose(app)

app.include_router(strawberry_graphql_router, prefix="/graphql")


# Mount Socket.IO inside FastAPI (handles both HTTP polling and WebSocket)
app.mount('/socket.io', socketio.ASGIApp(sio, socketio_path=''))



@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    import threading
    from core.background_services import ensure_background_registry

    background_services = ensure_background_registry(app)

    logger.info("=" * 60)
    logger.info("Starting Magellon Core Service...")
    logger.info("=" * 60)

    # Capture the asgi event loop so sync callers (RMQ result consumer,
    # outgoing dispatch audit) can schedule Socket.IO emits via
    # run_coroutine_threadsafe. Same trick the RMQ step-event forwarder
    # already uses (loop=asyncio.get_running_loop() at :474).
    try:
        from core.socketio_server import set_asgi_loop
        set_asgi_loop(asyncio.get_running_loop())
    except Exception:
        logger.exception("failed to capture asgi loop for socketio")

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

    # Install the process-wide MessageBus before any consumer thread
    # spawns. Result consumer, step-event forwarder, and liveness
    # listener all call get_bus() on their threads — without this the
    # first one to boot races and crashes with "No MessageBus configured".
    try:
        from core.dispatcher_registry import install_core_bus
        logger.info("Installing process-wide MessageBus (RMQ binder)...")
        install_core_bus()
        logger.info("[OK] MessageBus installed")
    except Exception as e:
        logger.error(f"[ERROR] MessageBus install failed: {e}")
        logger.warning("[WARNING] Bus consumers will fail to start")

    # PI-6: the in-process announce loop is gone. Architecture B is
    # retired — no PluginBase subclasses live inside CoreService
    # anymore; the registry walks an empty filesystem. All plugins
    # are external broker plugins, announcing themselves directly.

    # Start motioncor test result processor thread
    try:
        from core.motioncor_test_result_processor import result_consumer_engine
        logger.info("Starting motioncor test result processor...")
        result_processor_thread = threading.Thread(target=result_consumer_engine, daemon=True)
        result_processor_thread.start()
        app.state.motioncor_test_result_processor = result_processor_thread
        background_services.started("motioncor_test_result_processor", result_processor_thread)
        logger.info("[OK] Motioncor test result processor started")
    except Exception as e:
        background_services.failed("motioncor_test_result_processor", e)
        logger.error(f"[WARNING] Failed to start result processor: {e}")

    # Plugin liveness listener (P6). Subscribes to magellon.plugins.*
    # so announce + heartbeat messages from PluginBrokerRunner-based
    # plugins land in an in-memory registry. Replaces Consul service
    # registration as the source of truth for "what's alive right now".
    if os.environ.get("MAGELLON_PLUGIN_LIVENESS_LISTENER", "1") != "0":
        try:
            from core.plugin_liveness_registry import start_liveness_listener
            from config import app_settings as _app_settings
            logger.info("Starting plugin liveness listener...")
            app.state.plugin_liveness_listener = start_liveness_listener(
                _app_settings.rabbitmq_settings
            )
            background_services.started("plugin_liveness_listener", app.state.plugin_liveness_listener)
            logger.info("[OK] Plugin liveness listener started")
        except Exception as e:
            background_services.failed("plugin_liveness_listener", e)
            logger.error(f"[WARNING] Failed to start plugin liveness listener: {e}")
    else:
        background_services.disabled("plugin_liveness_listener")

    # Operational event tap. This is intentionally not event sourcing:
    # bus.events.subscribe uses anonymous auto-delete queues, so it gives
    # operators visibility without creating a durable catch-all backlog.
    app.state.operational_event_logger = None
    if os.environ.get("MAGELLON_OPERATIONAL_EVENT_LOGGER", "1") != "0":
        try:
            from magellon_sdk.bus import get_bus
            from magellon_sdk.bus.services import start_operational_event_logger
            logger.info("Starting operational event logger...")
            app.state.operational_event_logger = start_operational_event_logger(
                bus=get_bus()
            )
            background_services.started("operational_event_logger", app.state.operational_event_logger)
            logger.info("[OK] Operational event logger started")
        except Exception as e:
            background_services.failed("operational_event_logger", e)
            logger.error(f"[WARNING] Operational event logger failed to start: {e}")
    else:
        background_services.disabled("operational_event_logger")

    # Start in-process result-processor (P3). Sole result writer since
    # A.4 deleted the out-of-tree magellon_result_processor plugin:
    # every task-result queue declared in rabbitmq_settings.OUT_QUEUES
    # is consumed here and projected straight into the DB on the same
    # engine the rest of CoreService uses. Empty OUT_QUEUES = the loop
    # exits immediately.
    try:
        from core.result_consumer import result_consumer_engine as run_result_consumer
        logger.info("Starting in-process result-processor (OUT_QUEUES)...")
        result_consumer_thread = threading.Thread(target=run_result_consumer, daemon=True)
        result_consumer_thread.start()
        app.state.result_consumer = result_consumer_thread
        background_services.started("result_consumer", result_consumer_thread)
        logger.info("[OK] In-process result-processor started")
    except Exception as e:
        background_services.failed("result_consumer", e)
        logger.error(f"[WARNING] Failed to start in-process result-processor: {e}")

    # Start RMQ → job_event forwarder. Default-on; set
    # MAGELLON_RMQ_STEP_EVENTS_FORWARDER=0 to disable (e.g. local dev
    # without RMQ). Sibling of the NATS forwarder below; both write to
    # the same job_event row keyed on event_id, so re-delivery across
    # channels dedupes at the DB. Both also drive the JobManager state
    # projector — that's how /image/fft/dispatch jobs transition from
    # QUEUED -> RUNNING -> COMPLETED in the DB.
    app.state.rmq_step_event_forwarder = None
    if os.environ.get("MAGELLON_RMQ_STEP_EVENTS_FORWARDER", "1") != "0":
        try:
            from core.rmq_step_event_forwarder import build_default_rmq_forwarder
            from core.socketio_server import emit_step_event
            from core.step_event_forwarder import chain_downstream, log_step_event
            from database import session_local as _session_local
            from services.job_state_projector import project_step_event
            # Capture the asgi event loop so the RMQ consumer daemon thread
            # can dispatch the async Socket.IO emit via run_coroutine_threadsafe.
            # Order: projector first (DB state must be fresh before the UI
            # reads it on receipt), then Socket.IO emit, then log line.
            rmq_forwarder = build_default_rmq_forwarder(
                app_settings.rabbitmq_settings,
                _session_local,
                downstream=chain_downstream(project_step_event, emit_step_event, log_step_event),
                loop=asyncio.get_running_loop(),
            )
            rmq_forwarder.start()
            app.state.rmq_step_event_forwarder = rmq_forwarder
            background_services.started("rmq_step_event_forwarder", rmq_forwarder)
            logger.info("[OK] RMQ step-event forwarder started (with state projector)")
        except Exception as e:
            background_services.failed("rmq_step_event_forwarder", e)
            logger.error(f"[WARNING] RMQ step-event forwarder failed to start: {e}")
    else:
        background_services.disabled("rmq_step_event_forwarder")

    # Start NATS → job_event forwarder. Default-on; set
    # MAGELLON_STEP_EVENTS_FORWARDER=0 to disable. When NATS/stream is
    # absent the service still boots — the forwarder is purely a
    # read-side bridge that can catch up once the publisher is up.
    app.state.step_event_forwarder = None
    if os.environ.get("MAGELLON_STEP_EVENTS_FORWARDER", "1") != "0":
        try:
            from core.step_event_forwarder import build_default_forwarder, chain_downstream, log_step_event
            from core.socketio_server import emit_step_event
            from database import session_local as _session_local
            from services.job_state_projector import project_step_event
            forwarder = build_default_forwarder(
                _session_local,
                downstream=chain_downstream(project_step_event, emit_step_event, log_step_event),
            )
            # Hard timeout so a stuck NATS consumer (e.g. a previous
            # process still holding the durable, or JetStream wedged on
            # add_stream) can't block uvicorn from binding the socket —
            # which would render the entire HTTP API + Socket.IO unreachable.
            try:
                started = await asyncio.wait_for(forwarder.start(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.error(
                    "[ERROR] Step-event forwarder: NATS start timed out after 5s — "
                    "skipping. Other services unaffected."
                )
                started = False
            if started:
                app.state.step_event_forwarder = forwarder
                background_services.started("step_event_forwarder", forwarder)
                logger.info("[OK] Step-event forwarder (NATS -> job_event) started (with state projector)")
            else:
                # With ensure_stream=True (the default) we should never get
                # here unless the NATS broker itself is unreachable — the
                # consumer auto-creates the stream when missing.
                logger.error(
                    "[ERROR] Step-event forwarder: could not attach to NATS "
                    "(broker reachable? JetStream enabled?) — events will not "
                    "be projected this boot"
                )
                background_services.failed("step_event_forwarder", RuntimeError("could not attach to NATS"))
        except Exception as e:
            background_services.failed("step_event_forwarder", e)
            logger.error(f"[WARNING] Step-event forwarder failed to start: {e}")
    else:
        background_services.disabled("step_event_forwarder")

    logger.info("=" * 60)
    logger.info("[OK] Magellon Core Service started successfully")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    from core.background_services import ensure_background_registry

    background_services = ensure_background_registry(app)

    logger.info("=" * 60)
    logger.info("Shutting down Magellon Core Service...")
    logger.info("=" * 60)

    forwarder = getattr(app.state, "step_event_forwarder", None)
    if forwarder is not None:
        try:
            await forwarder.stop()
            background_services.stopped("step_event_forwarder", forwarder)
            logger.info("[OK] Step-event forwarder stopped")
        except Exception as e:
            background_services.failed("step_event_forwarder", e)
            logger.error(f"[WARNING] Step-event forwarder stop failed: {e}")

    rmq_forwarder = getattr(app.state, "rmq_step_event_forwarder", None)
    if rmq_forwarder is not None:
        try:
            rmq_forwarder.stop()
            background_services.stopped("rmq_step_event_forwarder", rmq_forwarder)
            logger.info("[OK] RMQ step-event forwarder stopped")
        except Exception as e:
            background_services.failed("rmq_step_event_forwarder", e)
            logger.error(f"[WARNING] RMQ step-event forwarder stop failed: {e}")

    liveness_listener = getattr(app.state, "plugin_liveness_listener", None)
    if liveness_listener is not None:
        try:
            liveness_listener.stop()
            background_services.stopped("plugin_liveness_listener", liveness_listener)
            logger.info("[OK] Plugin liveness listener stopped")
        except Exception as e:
            background_services.failed("plugin_liveness_listener", e)
            logger.error(f"[WARNING] Plugin liveness listener stop failed: {e}")

    operational_logger = getattr(app.state, "operational_event_logger", None)
    if operational_logger is not None:
        try:
            operational_logger.stop()
            background_services.stopped("operational_event_logger", operational_logger)
            logger.info("[OK] Operational event logger stopped")
        except Exception as e:
            background_services.failed("operational_event_logger", e)
            logger.error(f"[WARNING] Operational event logger stop failed: {e}")


