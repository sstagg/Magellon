"""Regenerate torch reference JSONs with .eval() forced (correct inference mode)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch

from ptolemy.images import load_mrc, Exposure
import ptolemy.algorithms as algorithms
import ptolemy.models as models

ROOT = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(ROOT, 'weights')


def _run_lowmag():
    img = load_mrc(os.path.join(ROOT, 'example_images', 'low_mag', '20may08a_16760340.mrc'))
    ex = Exposure(img)
    ex.make_mask(algorithms.PMM_Segmenter())
    ex.process_mask(algorithms.LowMag_Process_Mask())
    ex.get_crops(algorithms.LowMag_Process_Crops())

    m = models.LowMag_64x5_2ep()
    m.load_state_dict(torch.load(os.path.join(W, '211215_lowmag_64x5_defaultadam_tightw_e2.torchmodel'), map_location='cpu'))
    m.eval()  # <-- CORRECT
    ex.score_crops(models.Wrapper(m), final=False)

    out = []
    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    intens   = ex.mean_intensities
    scores   = ex.crops.scores
    for i in np.argsort(scores)[::-1]:
        out.append({'vertices': vertices[i], 'center': centers[i],
                    'area': float(areas[i]),
                    'brightness': float(intens[i]),
                    'score': float(scores[i])})
    return out


def _run_medmag():
    img = load_mrc(os.path.join(ROOT, 'example_images', 'med_mag', '21feb25a_23139789.mrc'))
    ex = Exposure(img)

    seg = algorithms.UNet_Segmenter(64, 9, model_path=os.path.join(W, '211026_unet_9x64_ep6.torchmodel'))
    seg.model.model.eval()  # <-- CORRECT (Wrapper -> .model is the nn.Module)
    ex.make_mask(seg)
    ex.process_mask(algorithms.MedMag_Process_Mask())
    ex.get_crops(algorithms.MedMag_Process_Crops())

    m = models.AveragePoolModel(4, 128)
    m.load_state_dict(torch.load(os.path.join(W, '211214_medmag_128x4_avgpool_e5.torchmodel'), map_location='cpu'))
    m.eval()  # <-- CORRECT
    ex.score_crops(models.Wrapper(m), final=False)

    out = []
    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    scores   = ex.crops.scores
    for i in np.argsort(scores)[::-1]:
        out.append({'vertices': vertices[i], 'center': centers[i],
                    'area': float(areas[i]), 'score': float(scores[i])})
    return out


if __name__ == '__main__':
    low = _run_lowmag()
    json.dump(low, open(os.path.join(ROOT, 'runs', 'lowmag_torch_eval.json'), 'w'), indent=2)
    print(f"wrote runs/lowmag_torch_eval.json ({len(low)} detections)")

    med = _run_medmag()
    json.dump(med, open(os.path.join(ROOT, 'runs', 'medmag_torch_eval.json'), 'w'), indent=2)
    print(f"wrote runs/medmag_torch_eval.json ({len(med)} detections)")
