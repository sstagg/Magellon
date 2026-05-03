"""Stack-maker plugin — particle extraction.

* ``algorithm.py`` — pure numpy compute (vendored from
  ``Sandbox/magellon_stack_maker``, with the two integration bugs from
  ``MAGELLON_PARTICLE_PIPELINE.md`` fixed in place).
* ``compute.py`` — file I/O + plumbing around the algorithm.
* ``plugin.py`` — :class:`StackMakerPlugin` (SDK contract) and
  ``build_extraction_result``.
* ``events.py`` — step-event publisher binding.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import StackMakerPlugin, build_extraction_result

__all__ = [
    "StackMakerPlugin",
    "STEP_NAME",
    "build_extraction_result",
    "get_publisher",
]
