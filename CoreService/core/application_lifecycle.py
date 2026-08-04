"""Reusable ASGI lifecycle composition."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def application_lifespan(
    app: FastAPI,
    startup: Callable[[], Awaitable[None]],
    shutdown: Callable[[], Awaitable[None]],
):
    """Run application hooks with one consistent ASGI lifespan boundary."""
    await startup()
    try:
        yield
    finally:
        await shutdown()

