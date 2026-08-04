from __future__ import annotations

import logging
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


def _error_payload(request, code: str, message: str, details=None) -> dict:
    """Build the stable error envelope used by all domain handlers."""
    payload = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        payload["details"] = details
    return payload


def _cors_headers(request) -> dict:
    """Echo CORS headers onto error responses so browsers keep the body.

    Only origins on the canonical allowlist are echoed — reflecting an
    arbitrary Origin with allow-credentials would hand any site a
    credentialed read of our error bodies, bypassing the middleware.
    """
    from core.cors import is_origin_allowed

    origin = request.headers.get("origin") if request is not None else None
    if not is_origin_allowed(origin):
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
            content=_error_payload(request, "ENTITY_NOT_FOUND", str(err)),
            headers=_cors_headers(request),
        )

    @app.exception_handler(DuplicateEntityError)
    def handle_duplicate(request, err):
        return JSONResponse(
            status_code=409,
            content=_error_payload(request, "DUPLICATE_ENTITY", str(err)),
            headers=_cors_headers(request),
        )

    @app.exception_handler(ValidationError)
    def handle_validation(request, err):
        return JSONResponse(
            status_code=422,
            content=_error_payload(request, "VALIDATION_ERROR", str(err)),
            headers=_cors_headers(request),
        )

    @app.exception_handler(PermissionDeniedError)
    def handle_permission(request, err):
        return JSONResponse(
            status_code=403,
            content=_error_payload(request, "PERMISSION_DENIED", str(err)),
            headers=_cors_headers(request),
        )

    @app.exception_handler(FileProcessingError)
    def handle_file_error(request, err):
        return JSONResponse(
            status_code=500,
            content=_error_payload(request, "FILE_PROCESSING_ERROR", str(err)),
            headers=_cors_headers(request),
        )

    @app.exception_handler(MagellonError)
    def handle_domain_error(request, err):
        return JSONResponse(
            status_code=400,
            content=_error_payload(request, "DOMAIN_ERROR", str(err)),
            headers=_cors_headers(request),
        )

    @app.exception_handler(Exception)
    def app_exception_handler(request, err):
        logger.exception("unhandled_request_exception method=%s path=%s", request.method, request.url.path)
        if is_production():
            content = _error_payload(request, "INTERNAL_SERVER_ERROR", "Internal server error")
        else:
            content = _error_payload(
                request, "INTERNAL_SERVER_ERROR", f"{type(err).__name__}: {err}",
            )
        return JSONResponse(
            status_code=500,
            content=content,
            headers=_cors_headers(request),
        )
