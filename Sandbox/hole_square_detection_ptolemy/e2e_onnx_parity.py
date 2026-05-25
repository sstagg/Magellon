#!/usr/bin/env python
"""
End-to-end parity: run the full lowmag + medmag pipelines with
OnnxWrapper swapped in for the torch Wrapper, and confirm detection
JSONs match the torch runs to 4 decimal places.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch

from onnx_wrapper import OnnxWrapper
from ptolemy.images import load_mrc, Exposure
import ptolemy.algorithms as algorithms
import ptolemy.models as models


ROOT = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(ROOT, 'weights')

LOWMAG_MRC  = os.path.join(ROOT, 'example_images', 'low_mag',  '20may08a_16760340.mrc')
MEDMAG_MRC  = os.path.join(ROOT, 'example_images', 'med_mag',  '21feb25a_23139789.mrc')
LOWMAG_TORCH_JSON = os.path.join(ROOT, 'runs', 'lowmag_torch_eval.json')
MEDMAG_TORCH_JSON = os.path.join(ROOT, 'runs', 'medmag_torch_eval.json')


def run_lowmag_onnx():
    img = load_mrc(LOWMAG_MRC)
    ex = Exposure(img)
    ex.make_mask(algorithms.PMM_Segmenter())
    ex.process_mask(algorithms.LowMag_Process_Mask())
    ex.get_crops(algorithms.LowMag_Process_Crops())
    # Swap torch Wrapper for ONNX
    wrapper = OnnxWrapper(os.path.join(W, 'lowmag.onnx'))
    ex.score_crops(wrapper, final=False)

    out = []
    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    intens   = ex.mean_intensities
    scores   = ex.crops.scores
    order    = np.argsort(scores)[::-1]
    for i in order:
        out.append({'vertices': vertices[i], 'center': centers[i],
                    'area': float(areas[i]),
                    'brightness': float(intens[i]),
                    'score': float(scores[i])})
    return out


def run_medmag_onnx():
    img = load_mrc(MEDMAG_MRC)
    ex = Exposure(img)
    # UNet segmenter swapped
    seg = algorithms.UNet_Segmenter(64, 9, model_path=os.path.join(W, '211026_unet_9x64_ep6.torchmodel'))
    seg.model = OnnxWrapper(os.path.join(W, 'unet.onnx'))
    ex.make_mask(seg)
    ex.process_mask(algorithms.MedMag_Process_Mask())
    ex.get_crops(algorithms.MedMag_Process_Crops())
    # Classifier swapped
    wrapper = OnnxWrapper(os.path.join(W, 'avgpool.onnx'))
    ex.score_crops(wrapper, final=False)

    out = []
    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    scores   = ex.crops.scores
    order    = np.argsort(scores)[::-1]
    for i in order:
        out.append({'vertices': vertices[i], 'center': centers[i],
                    'area': float(areas[i]), 'score': float(scores[i])})
    return out


def _diff(name, t, o):
    if len(t) != len(o):
        print(f"{name}: count mismatch torch={len(t)} onnx={len(o)}")
        return False
    # Sort both by center so we compare apples-to-apples regardless of
    # score-based ordering drift.
    t = sorted(t, key=lambda d: (d['center'][0], d['center'][1]))
    o = sorted(o, key=lambda d: (d['center'][0], d['center'][1]))
    max_score_diff = 0.0
    max_center_diff = 0
    max_area_diff = 0.0
    for td, od in zip(t, o):
        max_score_diff = max(max_score_diff, abs(td['score'] - od['score']))
        max_area_diff  = max(max_area_diff, abs(td['area'] - od['area']))
        max_center_diff = max(max_center_diff,
                              abs(td['center'][0] - od['center'][0]),
                              abs(td['center'][1] - od['center'][1]))
    ok = max_score_diff < 1e-4 and max_center_diff <= 1 and max_area_diff < 1e-2
    print(f"{name}: {'PASS' if ok else 'FAIL'}  "
          f"n={len(t)} | max|score_diff|={max_score_diff:.2e}"
          f"  max|center_diff|={max_center_diff}px"
          f"  max|area_diff|={max_area_diff:.2e}")
    return ok


if __name__ == '__main__':
    print("lowmag end-to-end ONNX vs torch ...")
    onnx_low = run_lowmag_onnx()
    torch_low = json.load(open(LOWMAG_TORCH_JSON))
    ok_low = _diff('lowmag', torch_low, onnx_low)

    print("medmag end-to-end ONNX vs torch ...")
    onnx_med = run_medmag_onnx()
    torch_med = json.load(open(MEDMAG_TORCH_JSON))
    ok_med = _diff('medmag', torch_med, onnx_med)

    # Persist the ONNX-path outputs so we can diff them separately if ever needed
    os.makedirs(os.path.join(ROOT, 'runs'), exist_ok=True)
    json.dump(onnx_low, open(os.path.join(ROOT, 'runs', 'lowmag_onnx.json'), 'w'), indent=2)
    json.dump(onnx_med, open(os.path.join(ROOT, 'runs', 'medmag_onnx.json'), 'w'), indent=2)

    sys.exit(0 if (ok_low and ok_med) else 1)
