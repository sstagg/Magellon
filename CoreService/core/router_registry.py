"""Central router and infrastructure registration for the FastAPI app."""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.staticfiles import StaticFiles

from controllers.admin_broker_controller import admin_broker_router
from controllers.admin_dispatch_cache_controller import admin_dispatch_cache_router
from controllers.admin_plugin_install_controller import admin_plugin_install_router
from controllers.artifacts_controller import artifacts_router
from controllers.camera_controller import camera_router
from controllers.cancellation_controller import cancellation_router
from controllers.db_controller import db_router
from controllers.deployment_docker_controller import deployment_docker_router
from controllers.dispatch_controller import dispatch_router
from controllers.graph_controller import graph_router
from controllers.health_controller import health_router
from controllers.home_controller import home_router
from controllers.image_meta_data_category_controller import image_meta_data_category_router
from controllers.image_meta_data_controller import image_meta_data_router
from controllers.image_processing_controller import image_processing_router
from controllers.import_controller import import_router
from controllers.import_export_controller import export_router
from controllers.ops_controller import ops_router
from controllers.particle_export_pipeline_controller import particle_export_pipeline_router
from controllers.particle_picking_controller import particle_picking_router
from controllers.pipelines_controller import pipelines_router
from controllers.relion_controller import relion_router
from controllers.schema_controller import schema_router
from controllers.slack_controller import slack_router
from controllers.system_stats_controller import system_stats_router
from controllers.webapp_atlas_controller import atlas_router
from controllers.webapp_controller import webapp_router
from controllers.webapp_motioncor_controller import motioncor_router
from controllers.webapp_particles_controller import particles_router
from controllers.security.auth_controller import router as auth_router
from controllers.security.session_access_controller import session_access_router
from controllers.security.sys_sec_permission_controller import sys_sec_permission_router
from controllers.security.sys_sec_permission_mgmt_controller import sys_sec_permission_mgmt_router
from controllers.security.sys_sec_role_controller import sys_sec_role_router
from controllers.security.sys_sec_user_controller import sys_sec_user_router
from controllers.security.sys_sec_user_role_controller import sys_sec_user_role_router
from core.dev_routes import dev_routes_enabled, register_dev_routes
from dependencies.auth import get_current_user_id
from models.graphql_strawberry_schema import strawberry_graphql_router
from plugins.controller import plugins_router
from core.socketio_server import sio
from socketio import ASGIApp


def register_routers(app: FastAPI) -> None:
    registrations = [
        (home_router, "Home", None), (health_router, "Health", "/health"),
        (db_router, "Database", "/db"), (export_router, "Export", "/export"),
        (import_router, "Import", "/export"), (relion_router, "RELION", "/export"),
        (particle_export_pipeline_router, "Particle Export Pipeline", "/export"),
        (camera_router, "Cameras", "/db/cameras"),
        (image_meta_data_category_router, "MetaData Category", "/db/meta-data-category"),
        (image_meta_data_router, "MetaData", "/db/meta-data"),
        (deployment_docker_router, "Docker", "/deployment/docker"),
        (image_processing_router, "Image Processing", "/image"),
        (webapp_router, "Image Viewer - WebApp", "/web"),
        (motioncor_router, "MotionCor & File Browsing", "/web"),
        (atlas_router, "Atlas", "/web"), (particles_router, "Particle Picking", "/web"),
        (graph_router, "Graphs", "/graphs"), (slack_router, "Communication", "/io"),
        (pipelines_router, "Pipeline Runs", "/pipelines"),
        (artifacts_router, "Artifacts", "/artifacts"),
        (auth_router, "Authentication", "/auth"),
        (sys_sec_user_router, "Security - Users", "/db/security/users"),
        (sys_sec_role_router, "Security - Roles", "/db/security/roles"),
        (sys_sec_user_role_router, "Security - User Roles", "/db/security/user-roles"),
        (sys_sec_permission_router, "Security - Permissions", "/db/security/permissions"),
        (sys_sec_permission_mgmt_router, "Security - Permission Management", "/db/security"),
        (session_access_router, "Security - Session Access", None),
        (schema_router, "Database Schema", None),
        (particle_picking_router, "Particle Picking", "/particle-picking"),
        (dispatch_router, "Dispatch", "/dispatch"), (plugins_router, "Plugins", "/plugins"),
        (cancellation_router, "Cancellation", "/cancellation"),
        (admin_broker_router, "Admin - Broker", "/admin/broker"),
        (admin_plugin_install_router, "Admin - Plugin Install", "/admin/plugins"),
        (admin_dispatch_cache_router, "Admin - Dispatch Cache", "/admin/dispatch-cache"),
        (system_stats_router, "System Stats", "/system"),
        (ops_router, "Ops Log", "/web/ops"),
    ]
    for router, tag, prefix in registrations:
        kwargs = {"tags": [tag]}
        if prefix is not None:
            kwargs["prefix"] = prefix
        app.include_router(router, **kwargs)

    if dev_routes_enabled():
        register_dev_routes(app)
    app.include_router(strawberry_graphql_router, prefix="/graphql", dependencies=[Depends(get_current_user_id)])
    app.mount("/socket.io", ASGIApp(sio, socketio_path=""))
    Instrumentator().instrument(app).expose(app)


def register_static_files(app: FastAPI) -> None:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")

