"""Deployment-environment helpers shared by startup checks, CORS, and auth.

Single source of truth for "are we in production?" so security-sensitive
modules (JWT secret resolution, CORS allowlists, Socket.IO auth) can't
drift apart on how the environment is detected.
"""
from __future__ import annotations

import os


def is_production() -> bool:
    """True when APP_ENV (or the configured ENV_TYPE) says production.

    APP_ENV wins; ENV_TYPE from app settings is the fallback so
    container images configured purely via YAML behave the same.
    """
    env = os.environ.get("APP_ENV")
    if not env:
        try:
            from config import app_settings
            env = getattr(app_settings, "ENV_TYPE", None)
        except Exception:
            env = None
    return str(env or "").strip().lower() == "production"
