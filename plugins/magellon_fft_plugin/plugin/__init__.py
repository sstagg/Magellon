"""FFT plugin — developer-facing code lives in this directory.

If you're forking this plugin to build your own:

* ``compute.py`` is the algorithm (pure, no SDK awareness).
* ``plugin.py`` is the SDK contract: ``FftPlugin`` (schemas + execute),
  ``FftBrokerRunner`` (broker glue), and ``build_fft_result``
  (output → wire result).
* ``events.py`` binds the SDK's lazy step-event publisher to this
  plugin's step name and RMQ settings.

Everything outside this directory (``core/``, ``main.py``,
``Dockerfile``, ``requirements.txt``) is boilerplate — copy as-is.
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
