"""Topaz plugin — vendored topaz internals + ONNX inference.

Layout:
  * ``topaz_lib/`` — vendored upstream topaz code (GPL-3.0):
                     downsample + GMM normalize, NMS, denoise tile/stitch.
                     All pure numpy/scipy, no torch.
  * ``weights/``   — three .onnx artifacts (resnet16/resnet8 detectors,
                     unet_l2 denoiser; ~17 MB total).
  * ``compute.py`` — onnxruntime-backed pipeline orchestration.
  * ``plugin.py``  — TopazPickPlugin + TopazDenoisePlugin + runners.
  * ``events.py``  — step-event publisher binding.
"""
from plugin.events import STEP_NAME, get_publisher
from plugin.plugin import (
    TopazBrokerRunner,
    TopazDenoisePlugin,
    TopazPickPlugin,
    build_denoise_result,
    build_pick_result,
    get_active_task,
)

__all__ = [
    "TopazBrokerRunner",
    "TopazDenoisePlugin",
    "TopazPickPlugin",
    "STEP_NAME",
    "build_denoise_result",
    "build_pick_result",
    "get_active_task",
    "get_publisher",
]
