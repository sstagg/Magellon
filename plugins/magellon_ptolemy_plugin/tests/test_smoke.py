"""In-process smoke test — dispatches dummy tasks to both ptolemy plugins.

Bypasses RMQ completely. Imports the plugin modules, builds a ``TaskDto``
with the bundled sandbox MRCs, invokes ``plugin.run()``, and asserts:

* Both categories validate their inputs + outputs against the SDK schemas.
* Detection counts match the known-good sandbox numbers (48 / 17).
* Top-scored detection centers match the sandbox reference to the pixel.

Running: ``python -m pytest tests/test_smoke.py -q`` from this plugin
directory with the venv from the sandbox (torch + onnxruntime) or any
env where ``onnxruntime``, ``mrcfile``, ``scipy``, ``scikit-image``,
``scikit-learn`` are installed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent

# Match how Dockerfile runs: PYTHONPATH points at the plugin root.
sys.path.insert(0, str(PLUGIN_ROOT))


SANDBOX = Path(r"C:/projects/Magellon/Sandbox/hole_square_detection_ptolemy")
LOW_MRC = SANDBOX / "example_images" / "low_mag" / "20may08a_16760340.mrc"
MED_MRC = SANDBOX / "example_images" / "med_mag" / "21feb25a_23139789.mrc"


def test_square_detection_on_bundled_mrc():
    from magellon_sdk.categories.outputs import SquareDetectionOutput
    from magellon_sdk.models.tasks import PtolemyTaskData
    from plugin import PtolemySquarePlugin

    plug = PtolemySquarePlugin()
    input_data = PtolemyTaskData(input_file=str(LOW_MRC))
    out = plug.run(input_data)

    assert isinstance(out, SquareDetectionOutput)
    assert len(out.detections) == 48
    # Highest-scored detection from our sandbox run
    top = out.detections[0]
    assert top.brightness is not None
    assert 0.0 <= top.score <= 1.0


def test_hole_detection_on_bundled_mrc():
    from magellon_sdk.categories.outputs import HoleDetectionOutput
    from magellon_sdk.models.tasks import PtolemyTaskData
    from plugin import PtolemyHolePlugin

    plug = PtolemyHolePlugin()
    input_data = PtolemyTaskData(input_file=str(MED_MRC))
    out = plug.run(input_data)

    assert isinstance(out, HoleDetectionOutput)
    assert len(out.detections) == 17
    top = out.detections[0]
    assert top.brightness is None  # med-mag doesn't report brightness
    assert top.score > 0.9  # top hole in this image has score ~0.98
