from __future__ import annotations

import logging
import traceback
from typing import Callable

from fastapi import FastAPI
from starlette.responses import JSONResponse

from core.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    FileProcessingError,
    MagellonError,
    PermissionDeniedError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _cors_headers(request) -> dict:
    """Echo CORS headers onto error responses so browsers keep the body."""
    origin = request.headers.get("origin") if request is not None else None
    if not origin:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


def register_exception_handlers(app: FastAPI, *, is_production: Callable[[], bool]) -> None:
    @app.exception_handler(EntityNotFoundError)
    def handle_not_found(request, err):
        return JSONResponse(
            status_code=404,
            content={"message": str(err)},
            headers=_cors_headers(request),
        )

    @app.exception_handler(DuplicateEntityError)
    def handle_duplicate(request, err):
        return JSONResponse(
            status_code=409,
            content={"message": str(err)},
            headers=_cors_headers(request),
        )

    @app.exception_handler(ValidationError)
    def handle_validation(request, err):
        return JSONResponse(
            status_code=422,
            content={"message": str(err)},
            headers=_cors_headers(request),
        )

    @app.exception_handler(PermissionDeniedError)
    def handle_permission(request, err):
        return JSONResponse(
            status_code=403,
            content={"message": str(err)},
            headers=_cors_headers(request),
        )

    @app.exception_handler(FileProcessingError)
    def handle_file_error(request, err):
        return JSONResponse(
            status_code=500,
            content={"message": str(err)},
            headers=_cors_headers(request),
        )

    @app.exception_handler(MagellonError)
    def handle_domain_error(request, err):
        return JSONResponse(
            status_code=400,
            content={"message": str(err)},
            headers=_cors_headers(request),
        )

    @app.exception_handler(Exception)
    def app_exception_handler(request, err):
        tb = traceback.format_exc()
        logger.error(f"Unhandled exception on {request.method} {request.url}:\n{tb}")
        if is_production():
            content = {
                "message": "Internal server error",
                "path": str(request.url.path),
            }
        else:
            content = {
                "message": f"{type(err).__name__}: {err}",
                "path": str(request.url),
            }
        return JSONResponse(
            status_code=500,
            content=content,
            headers=_cors_headers(request),
        )

