"""SYNC capability — ``POST /execute`` sync alternative to bus dispatch.

A plugin advertising :class:`Capability.SYNC` lets a host call it
synchronously over HTTP with the category's ``input_model``, getting
back the category's ``output_model``. Same compute as the bus path;
different transport.

Plugin author API
=================

The plugin's PluginBase subclass must declare ``execute_sync(input)``::

    from magellon_sdk.base import PluginBase
    from magellon_sdk.models.manifest import Capability

    class MyPlugin(PluginBase):
        capabilities = [Capability.SYNC, ...]

        def execute_sync(self, input_data: MyInput) -> MyOutput:
            # Same compute as execute() but without the bus runner's
            # step-event machinery. For most plugins this is a
            # one-liner: ``return self.execute(input_data, reporter=NullReporter())``.
            # Don't call ``self.run(...)`` — run() re-validates input
            # against the schema, which the SDK router already did.
            ...

The plugin's ``main.py`` mounts the router::

    from magellon_sdk.capabilities import make_sync_router
    if Capability.SYNC in _plugin.capabilities:
        app.include_router(make_sync_router(_plugin))

Errors are mapped to standard HTTP statuses:
  - ``ValueError`` → 422 (input the plugin couldn't process)
  - ``FileNotFoundError`` → 404
  - anything else → 500
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException


def make_sync_router(plugin: Any) -> APIRouter:
    """Build a router that exposes ``POST /execute`` for ``plugin``.

    The plugin must implement ``execute_sync(input_data)`` and have
    a ``input_schema()`` / ``output_schema()`` pair returning the
    category's input / output Pydantic classes (the standard
    PluginBase contract).
    """
    if not hasattr(plugin, "execute_sync"):
        raise TypeError(
            f"{type(plugin).__name__} declares Capability.SYNC but does not "
            f"implement execute_sync(input_data) — see "
            f"magellon_sdk.capabilities.sync_router for the contract."
        )

    input_model = plugin.input_schema()
    output_model = plugin.output_schema()

    # Define the handler with a generic ``input_data`` parameter, then
    # patch its ``__annotations__`` so FastAPI's dependency injector
    # validates the body against the runtime-determined input_model.
    # Using the model directly as a type annotation in the def line
    # would fail because Pydantic can't resolve closure variables as
    # forward refs.
    async def execute(input_data):
        try:
            return plugin.execute_sync(input_data)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc))

    execute.__annotations__ = {
        "input_data": input_model,
        "return": output_model,
    }

    router = APIRouter()
    router.add_api_route(
        "/execute",
        execute,
        methods=["POST"],
        response_model=output_model,
        summary="Synchronous execute — sync alternative to bus dispatch",
    )
    return router


__all__ = ["make_sync_router"]
