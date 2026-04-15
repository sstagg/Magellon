"""Magellon Plugin SDK.

Stable, versioned contract for building Magellon plugins — in-process or
remote. CoreService depends on this package; plugins should depend only
on this package and never on CoreService internals.

The most common types are re-exported here so plugin authors can write
``from magellon_sdk import PluginBase, Envelope, NullReporter``. Less
common types stay under their submodules.
"""
from __future__ import annotations

from magellon_sdk.base import PluginBase
from magellon_sdk.envelope import Envelope
from magellon_sdk.progress import JobCancelledError, NullReporter, ProgressReporter

__version__ = "0.1.0"

__all__ = [
    "Envelope",
    "JobCancelledError",
    "NullReporter",
    "PluginBase",
    "ProgressReporter",
    "__version__",
]
