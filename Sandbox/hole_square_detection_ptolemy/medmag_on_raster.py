#!/usr/bin/env python
"""
Run ptolemy's medmag pipeline on a raster image (JPG/PNG/TIFF), not MRC.

Loads the image as a grayscale float32 array, feeds it to Exposure, and
emits the same JSON schema as medmag_algorithm.py (vertices, center, area,
score — one per detected hole, sorted by score desc).

Usage: python medmag_on_raster.py <path_to_raster>
"""
import json
import os
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ptolemy.images import Exposure
import ptolemy.algorithms as algorithms
import ptolemy.models as models


def load_raster(path):
    im = Image.open(path).convert('L')
    return np.asarray(im).astype(np.float32)


def run_medmag(img):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    seg_w = os.path.join(script_dir, 'weights', '211026_unet_9x64_ep6.torchmodel')
    cls_w = os.path.join(script_dir, 'weights', '211214_medmag_128x4_avgpool_e5.torchmodel')

    ex = Exposure(img)
    ex.make_mask(algorithms.UNet_Segmenter(64, 9, model_path=seg_w))
    ex.process_mask(algorithms.MedMag_Process_Mask())
    ex.get_crops(algorithms.MedMag_Process_Crops())

    m = models.AveragePoolModel(4, 128)
    m.load_state_dict(torch.load(cls_w, map_location='cpu'))
    ex.score_crops(models.Wrapper(m), final=False)

    vertices = [b.as_matrix_y().tolist() for b in ex.crops.boxes]
    areas    = [b.area() for b in ex.crops.boxes]
    centers  = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    scores   = ex.crops.scores
    order    = np.argsort(scores)[::-1]

    return [{
        'vertices': vertices[i],
        'center':   centers[i],
        'area':     float(areas[i]),
        'score':    float(scores[i]),
    } for i in order]


def main():
    if len(sys.argv) != 2:
        print("Usage: medmag_on_raster.py <image>", file=sys.stderr)
        sys.exit(1)
    img = load_raster(sys.argv[1])
    print(json.dumps(run_medmag(img), indent=2))


if __name__ == '__main__':
    main()
