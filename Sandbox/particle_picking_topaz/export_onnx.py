#!/usr/bin/env python
"""
Export topaz pretrained models to ONNX.

Writes:
  weights/topaz_resnet16_u64.onnx  (LinearClassifier(ResNet16) — particle picker)
  weights/topaz_resnet8_u64.onnx   (LinearClassifier(ResNet8) — particle picker, smaller)
  weights/topaz_unet_l2.onnx       (UDenoiseNet — denoiser)

Critical step: detector models must have `.eval()` + `.fill()` called BEFORE
export. `fill()` rewrites Conv2d.dilation/stride/padding so that the strided
training-time graph becomes a fully-convolutional inference graph that
returns a per-pixel score map — same trick topaz's `score_images` does at
inference time. Skip it and the exported ONNX graph reproduces the strided
classifier instead.
"""
import os
import sys
import warnings

import torch

# Topaz uses several deprecated torch APIs — silence them so the export logs
# stay focused on real warnings.
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

from topaz.model.factory import load_model as load_detector
from topaz.denoising.models import load_model as load_denoiser

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
os.makedirs(WEIGHTS, exist_ok=True)

OPSET = 17


def export_detector(name: str, out_filename: str, dummy_hw=(512, 512)) -> None:
    """Export a topaz detector to ONNX with the FCN trick applied."""
    model = load_detector(name)
    model.eval()
    # `fill()` flips the strided classifier into a fully-convolutional one.
    # WITHOUT this, the score map output shape is wrong and pick coordinates
    # come out off by the stride factor (8x for resnet8/16).
    model.fill()

    h, w = dummy_hw
    dummy = torch.randn(1, 1, h, w)
    out_path = os.path.join(WEIGHTS, out_filename)
    torch.onnx.export(
        model, dummy, out_path,
        input_names=["input"], output_names=["score_map"],
        dynamic_axes={"input": {0: "N", 2: "H", 3: "W"},
                      "score_map": {0: "N", 2: "H", 3: "W"}},
        opset_version=OPSET, dynamo=False,
    )
    size_kb = os.path.getsize(out_path) / 1024.0
    print(f"  wrote {out_path}  ({size_kb:.1f} KB)")


def export_denoiser(name: str, out_filename: str, dummy_hw=(512, 512)) -> None:
    """Export a topaz denoiser. UNet uses F.interpolate(size=...) which
    exports to dynamic-shape Resize ops — fine with `dynamic_axes`.
    """
    model = load_denoiser(name)
    model.eval()

    h, w = dummy_hw
    dummy = torch.randn(1, 1, h, w)
    out_path = os.path.join(WEIGHTS, out_filename)
    torch.onnx.export(
        model, dummy, out_path,
        input_names=["input"], output_names=["denoised"],
        dynamic_axes={"input": {0: "N", 2: "H", 3: "W"},
                      "denoised": {0: "N", 2: "H", 3: "W"}},
        opset_version=OPSET, dynamo=False,
    )
    size_kb = os.path.getsize(out_path) / 1024.0
    print(f"  wrote {out_path}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    print("Exporting topaz models to ONNX (opset 17, dynamic axes) ...")

    print("[detector]")
    export_detector("resnet16", "topaz_resnet16_u64.onnx")
    export_detector("resnet8", "topaz_resnet8_u64.onnx")

    print("[denoiser]")
    export_denoiser("unet", "topaz_unet_l2.onnx")

    print("done.")
