"""Capability contracts — endpoints plugins expose when they
advertise the corresponding :class:`Capability` flag (PT-2, 2026-05-04).

Plugins declare what they support via ``capabilities = [...]`` on
their PluginBase subclass. CoreService's sync_dispatcher and the
React UI both read those flags to decide what shapes to call. The
contract endpoints themselves are wired by the routers in this
package: plugin authors don't hand-roll FastAPI per capability.

Currently shipped:

  * :func:`make_sync_router` — :class:`Capability.SYNC`. Mounts
    ``POST /execute`` so a host can call the plugin synchronously
    with the category's input shape and get back the category's
    output shape. Stays alongside the bus path; both can serve
    the same plugin.

  * :func:`make_preview_router` — :class:`Capability.PREVIEW`.
    Mounts the interactive preview-and-retune flow:
    ``POST /preview`` (compute once, cache score maps),
    ``POST /preview/{id}/retune`` (re-threshold without recompute),
    ``DELETE /preview/{id}`` (free memory). The plugin author
    implements three methods (``preview``, ``retune``,
    ``discard_preview``); the router enforces the wire shape.

Future capabilities (``STREAM``, ``NOTEBOOK``, etc.) follow the
same pattern: one router factory per capability, contract shapes
declared on the :class:`CategoryContract`.
"""
from magellon_sdk.capabilities.preview_models import (
    PickingPreviewResult,
    PickingRetuneRequest,
    PickingRetuneResult,
)
from magellon_sdk.capabilities.preview_router import make_preview_router
from magellon_sdk.capabilities.sync_router import make_sync_router

__all__ = [
    "PickingPreviewResult",
    "PickingRetuneRequest",
    "PickingRetuneResult",
    "make_preview_router",
    "make_sync_router",
]
