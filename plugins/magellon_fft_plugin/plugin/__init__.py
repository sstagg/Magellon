"""FFT plugin — developer-facing code lives in this directory.

If you're forking this plugin to build your own:

* ``compute.py`` is the algorithm (pure, no SDK awareness).
* ``plugin.py`` is the SDK contract: ``FftPlugin`` (schemas + execute)
  and ``build_fft_result`` (output → wire result).
* ``events.py`` binds the SDK's lazy step-event publisher to this
  plugin's step name and RMQ settings.

Everything outside this directory (``core/``, ``main.py``,
``Dockerfile``, ``requirements.txt``) is boilerplate — copy as-is.

Phase 1 (2026-05-03): the per-plugin ``FftBrokerRunner`` subclass is
gone — :class:`magellon_sdk.runner.PluginBrokerRunner` now owns the
ContextVar + daemon loop + step-reporter helpers. ``FftBrokerRunner`` /
``get_active_task`` survive as one-release back-compat shims in
``plugin.plugin``; new plugins shouldn't reference them.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import (
    FftBrokerRunner,
    FftPlugin,
    build_fft_result,
    get_active_task,
)

__all__ = [
    "FftBrokerRunner",
    "FftPlugin",
    "STEP_NAME",
    "build_fft_result",
    "get_active_task",
    "get_publisher",
]
