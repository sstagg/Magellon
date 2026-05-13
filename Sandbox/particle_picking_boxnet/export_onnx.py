#!/usr/bin/env python
"""
Export BoxNet v2 to ONNX.

The `.pt` file is a graph-trace (entire module, not just weights), which means
PyTorch's ONNX exporter can run against it directly once we re-attach the
`flexible_forward` method. The trick is identical to what BoxnetPT does at
inference time.

Writes:
  weights/boxnet.onnx

Notes:
  - Dynamic axes on H and W so the same ONNX file works for any micrograph
    size. The padding-to-multiple-of-256 happens in numpy outside the graph
    (see boxnet_pt.pad_to_unit_3d), so the ONNX runtime path mirrors the
    PyTorch path exactly.
  - Opset 17 matches the topaz sandbox.
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import torch

from boxnet_pt import flexible_forward

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
OPSET = 17


def _default_pt():
    pts = [f for f in os.listdir(WEIGHTS) if f.lower().endswith(".pt")]
    if len(pts) != 1:
        return None
    return os.path.join(WEIGHTS, pts[0])


def export(model_path: str, out_filename: str = "boxnet.onnx",
           dummy_hw=(512, 512)) -> None:
    model = torch.load(model_path, weights_only=False)
    setattr(model, 'forward', flexible_forward.__get__(model, type(model)))
    model.eval()

    h, w = dummy_hw
    dummy = torch.randn(1, 1, h, w)
    out_path = os.path.join(WEIGHTS, out_filename)

    torch.onnx.export(
        model, dummy, out_path,
        input_names=["input"], output_names=["softmax_tensor"],
        dynamic_axes={"input": {0: "N", 2: "H", 3: "W"},
                      "softmax_tensor": {0: "BHW"}},
        opset_version=OPSET, dynamo=False,
    )

    size_kb = os.path.getsize(out_path) / 1024.0
    print(f"  wrote {out_path}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    pt_path = _default_pt()
    if pt_path is None:
        sys.stderr.write(
            "Could not find exactly one *.pt under weights/. Drop boxnet.pt "
            "in weights/ and re-run.\n"
        )
        sys.exit(1)

    print(f"Exporting BoxNet to ONNX (opset {OPSET}, dynamic H/W) ...")
    print(f"  source: {pt_path}")
    export(pt_path)
    print("done.")
