#!/usr/bin/env python
"""
Export ptolemy's three pretrained PyTorch models to ONNX.

Writes:
  weights/lowmag.onnx   (LowMag_64x5_2ep  — square classifier, low-mag)
  weights/unet.onnx     (BasicUNet(64, 9) — hole segmenter, med-mag)
  weights/avgpool.onnx  (AveragePoolModel(4, 128) — hole classifier, med-mag)

All three use dynamic axes for H/W (and N for avgpool) so a single .onnx
handles any image size. Opset 17 (released 2022) — widely supported by
onnxruntime, TensorRT, CoreML.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
from ptolemy.models import LowMag_64x5_2ep, BasicUNet, AveragePoolModel

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, 'weights')
OPSET = 17


def _load(ctor, torchmodel_filename):
    model = ctor()
    state = torch.load(os.path.join(WEIGHTS, torchmodel_filename), map_location='cpu')
    model.load_state_dict(state)
    model.eval()  # CRITICAL — otherwise BatchNorm uses batch stats not running stats
    return model


def export_lowmag():
    # Accepts a cropped square image, 1x1xHxW, returns score grid 1x1x?x?
    model = _load(LowMag_64x5_2ep, '211215_lowmag_64x5_defaultadam_tightw_e2.torchmodel')
    # Typical crop width is 240 (LowMag_Process_Crops.width=240)
    dummy = torch.randn(1, 1, 240, 240)
    out_path = os.path.join(WEIGHTS, 'lowmag.onnx')
    torch.onnx.export(
        model, dummy, out_path,
        input_names=['input'], output_names=['score'],
        dynamic_axes={'input': {0: 'N', 2: 'H', 3: 'W'}, 'score': {0: 'N'}},
        opset_version=OPSET, dynamo=False,
    )
    print(f"  wrote {out_path}  ({os.path.getsize(out_path)/1024:.1f} KB)")


def export_unet():
    # Accepts full med-mag image, 1x1xHxW (padded to multiples of 512 in caller)
    model = _load(lambda: BasicUNet(64, 9), '211026_unet_9x64_ep6.torchmodel')
    dummy = torch.randn(1, 1, 1024, 1024)
    out_path = os.path.join(WEIGHTS, 'unet.onnx')
    torch.onnx.export(
        model, dummy, out_path,
        input_names=['input'], output_names=['mask'],
        dynamic_axes={'input': {2: 'H', 3: 'W'}, 'mask': {2: 'H', 3: 'W'}},
        opset_version=OPSET, dynamo=False,
    )
    print(f"  wrote {out_path}  ({os.path.getsize(out_path)/1024:.1f} KB)")


def export_avgpool():
    # Accepts batch of hole crops, Nx1xCxC; score per crop.
    # MedMag_Process_Crops pads to 270 wide, so typical shape is Nx1x270x270.
    model = _load(lambda: AveragePoolModel(4, 128),
                  '211214_medmag_128x4_avgpool_e5.torchmodel')
    dummy = torch.randn(2, 1, 270, 270)
    out_path = os.path.join(WEIGHTS, 'avgpool.onnx')
    torch.onnx.export(
        model, dummy, out_path,
        input_names=['input'], output_names=['score'],
        dynamic_axes={'input': {0: 'N', 2: 'H', 3: 'W'}, 'score': {0: 'N'}},
        opset_version=OPSET, dynamo=False,
    )
    print(f"  wrote {out_path}  ({os.path.getsize(out_path)/1024:.1f} KB)")


if __name__ == '__main__':
    print("Exporting to ONNX (opset 17, dynamic axes) ...")
    export_lowmag()
    export_unet()
    export_avgpool()
    print("done.")
