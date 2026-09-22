"""Construction of a configured CoreService FastAPI application."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Optional

from fastapi import FastAPI

from core.application_lifecycle import application_lifespan
from core.application_middleware import register_middleware
from core.router_registry import register_routers, register_static_files
from database import engine, session_local


def create_app(
    *,
    lifespan: Any = None,
    startup: Optional[Callable[[], Awaitable[None]]] = None,
    shutdown: Optional[Callable[[], Awaitable[None]]] = None,
) -> FastAPI:
    """Build the application without importing the module-level app.

    Tests and command-line tools can use this factory with no startup hooks;
    production supplies the real background-service lifecycle callbacks.
    """
    configured_lifespan = lifespan
    if startup is not None or shutdown is not None:
        if startup is None or shutdown is None:
            raise ValueError("startup and shutdown must be supplied together")

        async def _lifespan(app: FastAPI):
            async with application_lifespan(app, startup, shutdown):
                yield

        configured_lifespan = _lifespan

    app = FastAPI(
        title="Magellon Core Service",
        description="Magellon Core Service that provides main services",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=configured_lifespan,
    )
    app.dbengine = engine
    app.dbsession = session_local
    register_middleware(app)
    register_static_files(app)
    register_routers(app)
    return app
