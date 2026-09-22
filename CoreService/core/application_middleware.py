"""Application middleware composition."""
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.cors import allowed_origins
from core.exception_handlers import register_exception_handlers
from core.environment import is_production
from core.request_observability import register_request_observability


def register_middleware(app: FastAPI) -> None:
    register_exception_handlers(app, is_production=is_production)
    register_request_observability(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

