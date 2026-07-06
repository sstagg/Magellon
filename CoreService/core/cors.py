"""Canonical CORS origin allowlist.

One computation shared by the HTTP CORSMiddleware, the error-path
header echo in :mod:`core.exception_handlers`, and the Socket.IO
server — so an origin can never be rejected by the middleware yet
reflected by an error handler or accepted by the websocket.

Never returns a wildcard: this service runs with
``allow_credentials=True``, and wildcard + credentials is exactly the
combination browsers exist to prevent.
"""
from __future__ import annotations

import logging
import os

from core.environment import is_production

logger = logging.getLogger(__name__)

_DEV_DEFAULT_ORIGINS = [
    "http://localhost",
    "https://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1",
    "https://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

_PROD_FALLBACK_ORIGINS = [
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
]


def _csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def allowed_origins() -> list[str]:
    """Origins allowed to make credentialed cross-origin requests."""
    configured = _csv_env("MAGELLON_CORS_ALLOWED_ORIGINS")
    if configured:
        return configured
    if is_production():
        logger.warning(
            "MAGELLON_CORS_ALLOWED_ORIGINS is not set in production; "
            "falling back to localhost-only origins"
        )
        return list(_PROD_FALLBACK_ORIGINS)
    return list(_DEV_DEFAULT_ORIGINS)


def is_origin_allowed(origin: str | None) -> bool:
    return bool(origin) and origin in allowed_origins()
