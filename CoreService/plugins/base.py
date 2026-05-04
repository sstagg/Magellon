"""CoreService-side re-export of the plugin base contract.

The authoritative definition of :class:`PluginBase` lives in the SDK
(`magellon_sdk.base`). This module re-exports it so existing CoreService
call sites — and plugins that haven't been migrated to import from the
SDK yet — keep working without changes.

**PI-6 (2026-05-04): VESTIGIAL.** Architecture B is retired; no live
in-process PluginBase subclass exists in CoreService anymore (the
last one, ``pp/template-picker``, moved to plain functions in
``services/particle_picking/`` in PI-5). This module + the registry
that walks for subclasses + the in-process branches in
``plugins/controller.py`` are dead code on the happy path. Removable
in a follow-up PR once any straggler external imports
(``from plugins.base import PluginBase``) are flushed.

New code should import directly from ``magellon_sdk.base``.
"""
from __future__ import annotations

from magellon_sdk.base import InputT, OutputT, PluginBase

__all__ = ["InputT", "OutputT", "PluginBase"]
