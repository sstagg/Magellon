"""Magellon Plugin SDK.

Stable, versioned contract for building Magellon plugins — in-process or
remote. CoreService depends on this package; plugins should depend only
on this package and never on CoreService internals.

The most common types are re-exported here so plugin authors can write:

    from magellon_sdk import (
        PluginBase, PluginBrokerRunner,       # the runtime
        PluginInfo, PluginManifest,           # identity + capability metadata
        TaskMessage, TaskResultMessage,       # wire envelopes
        Envelope,                             # CloudEvents wrapper
        install_rmq_bus,                      # bus bootstrap
        NullReporter, ProgressReporter,       # progress reporting
    )

Less common types stay under their submodules (``magellon_sdk.models``,
``magellon_sdk.categories``, ``magellon_sdk.events``, etc.).

Public contract scope: see ``CONTRACT.md`` at the repo root.
"""
from __future__ import annotations

from magellon_sdk.base import PluginBase
from magellon_sdk.bus.bootstrap import (
    install_inmemory_bus,
    install_mock_bus,
    install_rmq_bus,
)
from magellon_sdk.envelope import Envelope
from magellon_sdk.models import (
    PluginInfo,
    PluginManifest,
    TaskMessage,
    TaskResultMessage,
)
from magellon_sdk.progress import JobCancelledError, NullReporter, ProgressReporter
from magellon_sdk.runner import PluginBrokerRunner

__version__ = "2.1.0"

__all__ = [
    # Runtime
    "PluginBase",
    "PluginBrokerRunner",
    # Bus bootstrap — install_rmq_bus for production, install_inmemory_bus
    # for integration tests, install_mock_bus for unit tests. See
    # CONTRACT.md §2.6 for when to pick which.
    "install_rmq_bus",
    "install_inmemory_bus",
    "install_mock_bus",
    # Wire shapes
    "Envelope",
    "TaskMessage",
    "TaskResultMessage",
    # Plugin identity + capability
    "PluginInfo",
    "PluginManifest",
    # Progress
    "NullReporter",
    "ProgressReporter",
    "JobCancelledError",
    # Version
    "__version__",
]
