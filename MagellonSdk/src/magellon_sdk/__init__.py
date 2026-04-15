"""Magellon Plugin SDK.

Stable, versioned contract for building Magellon plugins — in-process or
remote. CoreService depends on this package; plugins should depend only
on this package and never on CoreService internals.

Scaffold only at 0.1.0. The `PluginBase`, `ProgressReporter`, envelope
helpers, and executor protocols will land in subsequent 0.1.x releases
as Phase 1 of the platform refactor progresses.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
