"""External BoxNet picker plugin.

* ``algorithm.py`` — vendored BoxnetPT graph trace + ``pick_with_boxnet``
  picker entry. The ``flexible_forward`` graph trace is auto-generated
  by onnx2torch; do not hand-edit. See
  ``Sandbox/particle_picking_boxnet/boxnet_pt.py`` for the validation
  story (parity to particle_mean=0.0228 / max=0.967 on great.png).
* ``compute.py`` — file I/O + parameter mapping (``_load_mrc``,
  ``run_boxnet_pick``).
* ``plugin.py`` — :class:`BoxnetPickerPlugin` (SDK contract) and
  ``build_pick_result``.
* ``events.py`` — step-event publisher binding.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import BoxnetPickerPlugin, build_pick_result

__all__ = [
    "BoxnetPickerPlugin",
    "STEP_NAME",
    "build_pick_result",
    "get_publisher",
]
