"""Wire types for the plugin activity.

Kept in a dedicated leaf module so workflows can import these without
pulling in :class:`PluginBase` (and its ABC / generic machinery, which
Temporal's workflow sandbox walks during validation).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class PluginActivityInput(BaseModel):
    """Wire shape accepted by every plugin activity.

    Kept minimal — the activity is a thin adapter. Rich routing /
    subject metadata lives on the surrounding `Envelope` (see
    magellon_sdk.envelope).
    """

    plugin_id: str
    job_id: Optional[str] = None
    input: Dict[str, Any]


class PluginActivityOutput(BaseModel):
    """Wire shape returned by every plugin activity."""

    output: Dict[str, Any]


__all__ = ["PluginActivityInput", "PluginActivityOutput"]
