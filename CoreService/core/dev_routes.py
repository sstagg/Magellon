"""Helpers for opt-in development and diagnostic HTTP routes."""
from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any


_TRUE_VALUES = {"1", "true", "yes", "on"}


def dev_routes_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether development-only route modules should be mounted."""
    source = os.environ if env is None else env
    return source.get("MAGELLON_ENABLE_DEV_ROUTES", "").strip().lower() in _TRUE_VALUES


def register_dev_routes(app: Any) -> None:
    """Mount development-only routers on ``app``."""
    from controllers.test_controller import test_router
    from controllers.test_rls_controller import test_rls_router

    app.include_router(test_router, tags=["Test"])
    app.include_router(test_rls_router, tags=["RLS Testing"])
