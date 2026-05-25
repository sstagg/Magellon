#!/usr/bin/env python
"""Cross-check renders: ptolemy's own matplotlib viz vs. two PIL coord orderings."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from ptolemy.images import load_mrc, Exposure
import ptolemy.algorithms as algorithms
import ptolemy.models as models

MODE = sys.argv[1]        # "low" or "med"
MRC  = sys.argv[2]
OUT  = sys.argv[3]        # directory for debug outputs

os.makedirs(OUT, exist_ok=True)

img = load_mrc(MRC)
print("image shape:", img.shape)

ex = Exposure(img)
if MODE == "low":
    ex.make_mask(algorithms.PMM_Segmenter())
    ex.process_mask(algorithms.LowMag_Process_Mask())
    ex.get_crops(algorithms.LowMag_Process_Crops())
    m = models.LowMag_64x5_2ep()
    m.load_state_dict(torch.load('weights/211215_lowmag_64x5_defaultadam_tightw_e2.torchmodel', map_location='cpu'))
else:
    ex.make_mask(algorithms.UNet_Segmenter(64, 9, model_path='weights/211026_unet_9x64_ep6.torchmodel'))
    ex.process_mask(algorithms.MedMag_Process_Mask())
    ex.get_crops(algorithms.MedMag_Process_Crops())
    m = models.AveragePoolModel(4, 128)
    m.load_state_dict(torch.load('weights/211214_medmag_128x4_avgpool_e5.torchmodel', map_location='cpu'))
ex.score_crops(models.Wrapper(m), final=False)

print("first 3 boxes as_matrix_y (col0,col1):")
for b in ex.crops.boxes[:3]:
    print(b.as_matrix_y())
    print("  .y =", b.y, "  .x =", b.x)

fig, ax = plt.subplots(figsize=(10, 10))
ax.imshow(ex.image, cmap='Greys_r')
for box in ex.crops.boxes:
    m_y = box.as_matrix_y()
    ax.add_patch(matplotlib.patches.Polygon(m_y, facecolor='none', edgecolor='red', linewidth=1))
p1 = os.path.join(OUT, f"{MODE}_ptolemy_matrix_y.png")
plt.axis('off'); plt.savefig(p1, dpi=100, bbox_inches='tight'); plt.close()
print("saved", p1)

fig, ax = plt.subplots(figsize=(10, 10))
ax.imshow(ex.image, cmap='Greys_r')
for box in ex.crops.boxes:
    m_x = box.as_matrix_x()
    ax.add_patch(matplotlib.patches.Polygon(m_x, facecolor='none', edgecolor='lime', linewidth=1))
p2 = os.path.join(OUT, f"{MODE}_ptolemy_matrix_x.png")
plt.axis('off'); plt.savefig(p2, dpi=100, bbox_inches='tight'); plt.close()
print("saved", p2)
