"""CoreService-side re-export of the plugin base contract.

The authoritative definition of :class:`PluginBase` lives in the SDK
(`magellon_sdk.base`). This module re-exports it so existing CoreService
call sites — and plugins that haven't been migrated to import from the
SDK yet — keep working without changes.

New code should import directly from ``magellon_sdk.base``.
"""
from __future__ import annotations

from magellon_sdk.base import InputT, OutputT, PluginBase

__all__ = ["InputT", "OutputT", "PluginBase"]
