"""Plugin discovery for the SDK worker CLI.

Two lookup paths, in priority order:

1. **Entry points** — a plugin package declares itself via::

       [project.entry-points."magellon.plugins"]
       "ctf/ctffind" = "my_pkg.service:CtffindPlugin"

   and ``magellon-plugin worker --plugin ctf/ctffind`` resolves it.

2. **Direct Python path** — when the supplied name contains a ``:`` it
   is interpreted as ``MODULE:CLASSNAME`` and imported directly. This
   is the unpackaged dev mode; useful before a plugin has a proper
   distribution, and in tests.

The dual mode lets the CLI work today (direct path) without blocking on
the plugin-packaging work that lands alongside Phase 6 (Plugin Hub).
"""
from __future__ import annotations

import importlib
from importlib.metadata import entry_points
from typing import Type

from magellon_sdk.base import PluginBase

ENTRY_POINT_GROUP = "magellon.plugins"


class PluginNotFound(LookupError):
    pass


def load_plugin(name_or_path: str) -> PluginBase:
    """Resolve ``name_or_path`` to an instantiated plugin.

    Checks entry points first, then falls back to interpreting the
    argument as ``MODULE:CLASSNAME``. Raises :class:`PluginNotFound`
    with a useful message if neither resolves.
    """
    cls = _resolve_class(name_or_path)
    instance = cls()
    if not isinstance(instance, PluginBase):
        raise TypeError(
            f"Loaded class {cls!r} does not subclass magellon_sdk.base.PluginBase"
        )
    return instance


def _resolve_class(name_or_path: str) -> Type[PluginBase]:
    eps = entry_points(group=ENTRY_POINT_GROUP)
    for ep in eps:
        if ep.name == name_or_path:
            return ep.load()

    if ":" in name_or_path:
        module_name, _, class_name = name_or_path.partition(":")
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise PluginNotFound(
                f"Could not import module {module_name!r} for plugin {name_or_path!r}: {exc}"
            ) from exc
        try:
            return getattr(module, class_name)
        except AttributeError as exc:
            raise PluginNotFound(
                f"Module {module_name!r} has no attribute {class_name!r}"
            ) from exc

    known = sorted({ep.name for ep in eps})
    raise PluginNotFound(
        f"No plugin registered under {name_or_path!r}. "
        f"Known entry-point plugins: {known or 'none'}. "
        f"Alternatively pass 'MODULE:CLASSNAME' for direct import."
    )


__all__ = ["ENTRY_POINT_GROUP", "PluginNotFound", "load_plugin"]
