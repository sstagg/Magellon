"""Ptolemy plugin — vendored SMLC-NYSBC ptolemy, ONNX inference.

Layout:
  * ``ptolemy/``  — vendored upstream modules (CC BY-NC 4.0). `models.py`
                    replaced with an onnxruntime-backed Wrapper; `algorithms.py`
                    patched so `UNet_Segmenter` loads an `.onnx` file.
  * ``weights/``  — three `.onnx` artifacts exported from the pretrained
                    `.torchmodel` weights (6 MB total).
  * ``compute.py`` — pipeline orchestration, MRC → ranked detections.
  * ``plugin.py`` — the two ``PluginBase`` classes (Square, Hole) + runners.
  * ``events.py`` — step-event publisher binding.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import (
    PtolemyBrokerRunner,
    PtolemyHolePlugin,
    PtolemySquarePlugin,
    build_hole_result,
    build_square_result,
    get_active_task,
)

__all__ = [
    "PtolemyBrokerRunner",
    "PtolemyHolePlugin",
    "PtolemySquarePlugin",
    "STEP_NAME",
    "build_hole_result",
    "build_square_result",
    "get_active_task",
    "get_publisher",
]
