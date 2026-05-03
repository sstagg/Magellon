"""CAN classifier plugin — 2D classification.

* ``compute.py`` — algorithm glue (Phase 7b vendors the actual CAN
  algorithm from ``Sandbox/magellon_can_classifier`` into
  ``algorithm.py``).
* ``plugin.py`` — :class:`CanClassifierPlugin` (SDK contract) and
  ``build_classification_result``.
* ``events.py`` — step-event publisher binding.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import CanClassifierPlugin, build_classification_result

__all__ = [
    "CanClassifierPlugin",
    "STEP_NAME",
    "build_classification_result",
    "get_publisher",
]
