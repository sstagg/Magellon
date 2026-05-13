#!/usr/bin/env python
"""
Torch vs ONNX numerical parity for the exported BoxNet model.

Strategy mirrors topaz's parity_check.py:
  1. Load an example micrograph + downsample to BoxNet's training scale.
  2. Run the torch reference through BoxnetPT -> torch_masks.
  3. Run the same input through the exported ONNX -> onnx_masks.
  4. Assert np.allclose(torch_masks, onnx_masks, atol=1e-4).

Both paths must apply identical pre-padding (multiple-of-256) and the same
per-image standardisation; both helpers live in boxnet_pt.
"""

import os
import sys
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import onnxruntime as ort
import torch

from boxnet_pt import BoxnetPT, flexible_forward, pad_to_unit_3d, unpad_batch

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
EXAMPLES = os.path.join(ROOT, "example_images")


def _default_pt():
    pts = [f for f in os.listdir(WEIGHTS) if f.lower().endswith(".pt")]
    return os.path.join(WEIGHTS, pts[0]) if len(pts) == 1 else None


def _default_onnx():
    onnxes = [f for f in os.listdir(WEIGHTS) if f.lower().endswith(".onnx")]
    return os.path.join(WEIGHTS, onnxes[0]) if len(onnxes) == 1 else None


def _first_mrc():
    if not os.path.isdir(EXAMPLES):
        return None
    mrcs = [f for f in os.listdir(EXAMPLES) if f.lower().endswith(".mrc")]
    return os.path.join(EXAMPLES, sorted(mrcs)[0]) if mrcs else None


def _load_and_prep(mrc_path, scale=8):
    """Read MRC, downsample, standardise per-image, pad to multiple of 256."""
    import mrcfile
    with mrcfile.open(mrc_path, permissive=True) as m:
        raw = np.asarray(m.data, dtype=np.float32)
    if raw.ndim == 3 and raw.shape[0] == 1:
        raw = raw[0]

    h, w = raw.shape
    new_h = (h // scale) * scale
    new_w = (w // scale) * scale
    cropped = raw[:new_h, :new_w]
    img = cropped.reshape(new_h // scale, scale, new_w // scale, scale).mean(axis=(1, 3))

    # Per-image standardisation
    img = (img - img.mean()) / (img.std() + 1e-8)

    H, W = img.shape
    padded = pad_to_unit_3d(img[np.newaxis, ...])  # (1, H_pad, W_pad)
    return img, padded, H, W


def main():
    pt = _default_pt()
    onnx = _default_onnx()
    mrc = _first_mrc()

    if pt is None or onnx is None or mrc is None:
        print("SKIP  parity needs weights/boxnet.pt, weights/boxnet.onnx, and "
              "at least one MRC in example_images/.")
        if pt is None: print("  - missing: weights/boxnet.pt")
        if onnx is None: print("  - missing: weights/boxnet.onnx (run export_onnx.py)")
        if mrc is None: print("  - missing: example_images/<file>.mrc")
        sys.exit(0)

    print(f"[inputs]")
    print(f"  pt   = {pt}")
    print(f"  onnx = {onnx}")
    print(f"  mrc  = {mrc}")

    _, padded, H, W = _load_and_prep(mrc)
    print(f"  padded input shape: {padded.shape}")

    # Torch reference
    model = torch.load(pt, weights_only=False)
    setattr(model, 'forward', flexible_forward.__get__(model, type(model)))
    model.eval()
    with torch.no_grad():
        x = torch.tensor(padded, dtype=torch.float32).unsqueeze(1)
        torch_out = model(x).cpu().numpy()
    torch_masks = unpad_batch(torch_out.reshape(*padded.shape, 3), H, W)

    # ONNX
    sess = ort.InferenceSession(onnx, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    onnx_raw = sess.run(None, {in_name: padded[:, np.newaxis].astype(np.float32)})[0]
    onnx_masks = unpad_batch(onnx_raw.reshape(*padded.shape, 3), H, W)

    diff = np.abs(torch_masks - onnx_masks)
    ok = np.allclose(torch_masks, onnx_masks, atol=1e-4)
    verdict = "PASS" if ok else "FAIL"
    print()
    print(f"[{verdict}]  shape={torch_masks.shape}  "
          f"max|diff|={diff.max():.3e}  median|diff|={np.median(diff):.3e}")
    print(f"  torch particle-mean = {torch_masks[..., 1].mean():.4f}")
    print(f"  onnx  particle-mean = {onnx_masks[..., 1].mean():.4f}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
