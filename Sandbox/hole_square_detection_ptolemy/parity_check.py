#!/usr/bin/env python
"""Torch vs ONNX numerical parity check for the 3 ptolemy models."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import onnxruntime as ort
import torch

from ptolemy.models import LowMag_64x5_2ep, BasicUNet, AveragePoolModel

ROOT = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(ROOT, 'weights')

CASES = [
    ('lowmag',  LowMag_64x5_2ep,             '211215_lowmag_64x5_defaultadam_tightw_e2.torchmodel', 'lowmag.onnx',  [(1, 1, 240, 240), (4, 1, 240, 240)]),
    ('unet',    lambda: BasicUNet(64, 9),    '211026_unet_9x64_ep6.torchmodel',                      'unet.onnx',    [(1, 1, 1024, 1024), (1, 1, 1024, 1440)]),
    ('avgpool', lambda: AveragePoolModel(4, 128), '211214_medmag_128x4_avgpool_e5.torchmodel',       'avgpool.onnx', [(1, 1, 270, 270), (5, 1, 270, 270)]),
]

ATOL = 1e-5
all_pass = True

for name, ctor, torch_w, onnx_w, shapes in CASES:
    torch_model = ctor()
    torch_model.load_state_dict(torch.load(os.path.join(W, torch_w), map_location='cpu'))
    torch_model.eval()

    sess = ort.InferenceSession(os.path.join(W, onnx_w), providers=['CPUExecutionProvider'])
    in_name = sess.get_inputs()[0].name

    for shape in shapes:
        rng = np.random.default_rng(seed=sum(shape))
        x = rng.standard_normal(shape).astype(np.float32)
        with torch.no_grad():
            t_out = torch_model(torch.from_numpy(x)).cpu().numpy()
        o_out = sess.run(None, {in_name: x})[0]

        max_abs = float(np.max(np.abs(t_out - o_out)))
        ok = np.allclose(t_out, o_out, atol=ATOL)
        all_pass &= ok
        verdict = 'PASS' if ok else 'FAIL'
        print(f"{verdict}  {name:10s} shape={str(shape):25s} out={str(t_out.shape):22s} max|diff|={max_abs:.3e}")

print()
print('OVERALL:', 'PASS' if all_pass else 'FAIL')
sys.exit(0 if all_pass else 1)
