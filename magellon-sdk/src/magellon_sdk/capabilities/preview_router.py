"""PREVIEW capability — interactive preview-and-retune flow.

A plugin advertising :class:`Capability.PREVIEW` exposes three
endpoints under its FastAPI app::

  POST   /preview                       → :class:`PickingPreviewResult`
  POST   /preview/{preview_id}/retune   → :class:`PickingRetuneResult`
  DELETE /preview/{preview_id}          → ``{"deleted": True}``

Use case: the React picker UX renders an overlay on a micrograph;
the operator drags a threshold slider. Each slider tick calls
``/retune``; only the initial frame calls ``/preview``. The plugin
caches score maps in memory between calls (typically a TTLCache).

Plugin author API
=================

The plugin's PluginBase subclass implements three methods::

    from magellon_sdk.capabilities import (
        PickingPreviewResult,
        PickingRetuneRequest,
        PickingRetuneResult,
    )

    class TemplatePickerPlugin(PluginBase):
        capabilities = [Capability.PREVIEW, ...]

        def preview(self, input_data) -> PickingPreviewResult: ...
        def retune(self, preview_id: str, params: PickingRetuneRequest
                   ) -> Optional[PickingRetuneResult]: ...
        def discard_preview(self, preview_id: str) -> bool: ...

``retune`` returns ``None`` when the preview_id is unknown / expired
(404). ``discard_preview`` returns ``True`` on hit, ``False`` on miss
(404 maps the boolean).

The plugin's ``main.py`` mounts the router::

    from magellon_sdk.capabilities import make_preview_router
    if Capability.PREVIEW in _plugin.capabilities:
        app.include_router(make_preview_router(_plugin))

Wire shapes today are picker-specific. A future category that adopts
PREVIEW (denoising-with-preview, stitching-preview, etc.) defines
its own ``Picking*Result`` analogues and the SDK ships an analogous
router factory.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from magellon_sdk.capabilities.preview_models import (
    PickingPreviewResult,
    PickingRetuneRequest,
    PickingRetuneResult,
)


def make_preview_router(plugin: Any) -> APIRouter:
    """Build a router that mounts the PREVIEW contract for ``plugin``.

    The plugin must implement ``preview(input)``, ``retune(preview_id,
    params)``, and ``discard_preview(preview_id)``. ``input_schema()``
    is the category's ``input_model`` (we re-use the same shape as the
    bus task — preview is just "run it but cache the intermediate
    maps").
    """
    for required in ("preview", "retune", "discard_preview"):
        if not hasattr(plugin, required):
            raise TypeError(
                f"{type(plugin).__name__} declares Capability.PREVIEW but "
                f"does not implement {required}() — see "
                f"magellon_sdk.capabilities.preview_router for the contract."
            )

    input_model = plugin.input_schema()

    # See sync_router.py for why we patch ``__annotations__`` rather
    # than annotating in the def line. Pydantic can't resolve closure
    # variables as forward refs.
    async def preview(input_data):
        try:
            return plugin.preview(input_data)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=str(exc))

    preview.__annotations__ = {
        "input_data": input_model,
        "return": PickingPreviewResult,
    }

    async def retune(preview_id: str, params: PickingRetuneRequest):
        result = plugin.retune(preview_id, params)
        if result is None:
            raise HTTPException(
                status_code=404, detail="Preview not found or expired",
            )
        return result

    async def discard(preview_id: str):
        if plugin.discard_preview(preview_id):
            return {"deleted": True}
        raise HTTPException(status_code=404, detail="Preview not found")

    router = APIRouter()
    router.add_api_route(
        "/preview",
        preview,
        methods=["POST"],
        response_model=PickingPreviewResult,
        summary="Compute correlation maps; return picks + score map",
    )
    router.add_api_route(
        "/preview/{preview_id}/retune",
        retune,
        methods=["POST"],
        response_model=PickingRetuneResult,
        summary="Re-extract particles with new tunable params",
    )
    router.add_api_route(
        "/preview/{preview_id}",
        discard,
        methods=["DELETE"],
        summary="Discard a preview and free memory",
    )
    return router


__all__ = ["make_preview_router"]
