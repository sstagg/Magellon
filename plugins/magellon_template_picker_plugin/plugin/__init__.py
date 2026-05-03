"""External template-picker plugin (Phase 6).

* ``algorithm.py`` — vendored numpy / scipy compute (FindEM-like
  normalized template matching) from
  ``Sandbox/magellon_template_picker/picker.py``.
* ``compute.py`` — file I/O + parameter mapping around the algorithm.
* ``plugin.py`` — :class:`TemplatePickerPlugin` (SDK contract) and
  ``build_pick_result``.
* ``events.py`` — step-event publisher binding.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import TemplatePickerPlugin, build_pick_result

__all__ = [
    "TemplatePickerPlugin",
    "STEP_NAME",
    "build_pick_result",
    "get_publisher",
]
