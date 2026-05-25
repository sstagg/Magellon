"""Capture the actual cropset input to the classifier in both torch and onnx
runs, and diff the per-crop outputs directly."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch
from onnx_wrapper import OnnxWrapper
from ptolemy.images import load_mrc, Exposure
import ptolemy.algorithms as algorithms
import ptolemy.models as models

ROOT = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(ROOT, 'weights')

# ----- lowmag -----
img = load_mrc(os.path.join(ROOT, 'example_images', 'low_mag', '20may08a_16760340.mrc'))
ex = Exposure(img)
ex.make_mask(algorithms.PMM_Segmenter())
ex.process_mask(algorithms.LowMag_Process_Mask())
ex.get_crops(algorithms.LowMag_Process_Crops())

batch = np.stack(ex.crops.crops, axis=0)[:, np.newaxis].astype(np.float32)
print(f"lowmag batch: {batch.shape}  range [{batch.min():.3f}, {batch.max():.3f}]  mean={batch.mean():.3f}")

tm = models.LowMag_64x5_2ep()
tm.load_state_dict(torch.load(os.path.join(W, '211215_lowmag_64x5_defaultadam_tightw_e2.torchmodel'), map_location='cpu'))
tm.eval()
with torch.no_grad():
    t_out = tm(torch.from_numpy(batch)).cpu().numpy().flatten()

ow = OnnxWrapper(os.path.join(W, 'lowmag.onnx'))
o_out = ow.forward_batch(batch)

print(f"  torch[:5] = {t_out[:5]}")
print(f"  onnx [:5] = {o_out[:5]}")
print(f"  max|diff| = {np.max(np.abs(t_out - o_out)):.2e}  median|diff| = {np.median(np.abs(t_out - o_out)):.2e}")
print()

# ----- medmag -----
img = load_mrc(os.path.join(ROOT, 'example_images', 'med_mag', '21feb25a_23139789.mrc'))
ex = Exposure(img)
seg = algorithms.UNet_Segmenter(64, 9, model_path=os.path.join(W, '211026_unet_9x64_ep6.torchmodel'))
ex.make_mask(seg)
ex.process_mask(algorithms.MedMag_Process_Mask())
ex.get_crops(algorithms.MedMag_Process_Crops())

# MedMag crops are a list of 2D arrays — possibly different shapes
shapes = {c.shape for c in ex.crops.crops}
print(f"medmag crops: {len(ex.crops.crops)} crops, shapes={shapes}")
batch = np.stack(ex.crops.crops, axis=0)[:, np.newaxis].astype(np.float32)
print(f"  batch: {batch.shape}  range [{batch.min():.3f}, {batch.max():.3f}]  mean={batch.mean():.3f}")

tm = models.AveragePoolModel(4, 128)
tm.load_state_dict(torch.load(os.path.join(W, '211214_medmag_128x4_avgpool_e5.torchmodel'), map_location='cpu'))
tm.eval()
with torch.no_grad():
    t_out = tm(torch.from_numpy(batch)).cpu().numpy().flatten()

ow = OnnxWrapper(os.path.join(W, 'avgpool.onnx'))
o_out = ow.forward_batch(batch)

print(f"  torch[:5] = {t_out[:5]}")
print(f"  onnx [:5] = {o_out[:5]}")
print(f"  max|diff| = {np.max(np.abs(t_out - o_out)):.2e}  median|diff| = {np.median(np.abs(t_out - o_out)):.2e}")
