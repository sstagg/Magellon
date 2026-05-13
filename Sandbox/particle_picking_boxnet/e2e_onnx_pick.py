#!/usr/bin/env python
"""
End-to-end ONNX particle picking — replaces the torch BoxnetPT path with
onnxruntime, then runs the same numpy peak-detection on the particle channel.

If this matches the torch path's picks count and top-N coords for the test
image, the ONNX plugin path is faithful and we can drop torch from the
runtime image (shaving the GPU torch wheel and CUDA libs).

Pipeline (mirrors pick_algorithm):
  1. Read MRC, downsample by --scale, standardise per-image.
  2. Pad to multiple of 256 (pad_to_unit_3d).
  3. Forward through ONNX -> raw softmax (B*H*W, 3).
  4. Reshape + unpad -> (H, W, 3) mask volume.
  5. peak_local_max on the particle channel -> picks.
  6. Compare to picks.json (canonical, produced by pick_algorithm.process_pick).
"""

import argparse
import json
import os
import sys

import numpy as np
import onnxruntime as ort

from boxnet_pt import pad_to_unit_3d, unpad_batch

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
EXAMPLES = os.path.join(ROOT, "example_images")


def _load_mrc(path):
    import mrcfile
    with mrcfile.open(path, permissive=True) as m:
        data = np.asarray(m.data, dtype=np.float32)
    if data.ndim == 3 and data.shape[0] == 1:
        data = data[0]
    return data


def _downsample(img, scale):
    if scale == 1:
        return img.astype(np.float32)
    h, w = img.shape
    new_h = (h // scale) * scale
    new_w = (w // scale) * scale
    cropped = img[:new_h, :new_w].astype(np.float32)
    return cropped.reshape(new_h // scale, scale, new_w // scale, scale).mean(axis=(1, 3))


def onnx_pick(mrc, onnx_path, threshold, min_distance, scale):
    raw = _load_mrc(mrc)
    img = _downsample(raw, scale)
    img = (img - img.mean()) / (img.std() + 1e-8)
    H, W = img.shape

    padded = pad_to_unit_3d(img[np.newaxis, ...])
    print(f"preprocessed: img={img.shape}, padded={padded.shape}, "
          f"range=[{img.min():.3f}, {img.max():.3f}]")

    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    raw_out = sess.run(None, {in_name: padded[:, np.newaxis].astype(np.float32)})[0]
    masks_padded = raw_out.reshape(*padded.shape, 3)
    masks = unpad_batch(masks_padded, H, W)[0]  # (H, W, 3)

    particle = masks[:, :, 1]
    print(f"particle mask: shape={particle.shape}  "
          f"range=[{particle.min():.3f}, {particle.max():.3f}]")

    from skimage.feature import peak_local_max
    coords = peak_local_max(
        particle,
        min_distance=max(1, int(min_distance)),
        threshold_abs=float(threshold),
        exclude_border=False,
    )
    scores = particle[coords[:, 0], coords[:, 1]] if len(coords) else np.array([])
    print(f"peaks: {len(coords)}")

    half_box = max(1, int(min_distance // 2)) * scale
    order = np.argsort(scores)[::-1]
    return [
        {"center": [int(coords[i, 1] * scale), int(coords[i, 0] * scale)],
         "radius": int(half_box),
         "score": float(scores[i])}
        for i in order
    ]


def compare_to_ground_truth(onnx_picks, gt_path):
    with open(gt_path) as f:
        gt = json.load(f)

    print()
    print(f"ground truth picks (picks.json): {len(gt)}")
    print(f"ONNX picks                     : {len(onnx_picks)}")

    print()
    print(f"{'idx':>4}  {'gt center':>15}  {'gt score':>10}    "
          f"{'onnx center':>15}  {'onnx score':>10}")
    for i in range(min(10, len(gt), len(onnx_picks))):
        g = gt[i]; o = onnx_picks[i]
        print(f"{i:>4}  {str(g['center']):>15}  {g['score']:>10.4f}    "
              f"{str(o['center']):>15}  {o['score']:>10.4f}")

    gt_set = {(p["center"][0], p["center"][1]) for p in gt}
    on_set = {(p["center"][0], p["center"][1]) for p in onnx_picks}
    print()
    print(f"exact-pixel coordinate matches : {len(gt_set & on_set)} / {len(gt_set)}")
    print(f"only in ground truth           : {len(gt_set - on_set)}")
    print(f"only in ONNX path              : {len(on_set - gt_set)}")


def main():
    parser = argparse.ArgumentParser(description="End-to-end ONNX BoxNet pick + GT compare")
    parser.add_argument('--mrc', default=None)
    parser.add_argument('--onnx', default=None)
    parser.add_argument('--gt', default=None, help="picks.json from pick_algorithm")
    parser.add_argument('--threshold', type=float, default=0.5)
    parser.add_argument('--min-distance', type=int, default=14)
    parser.add_argument('--scale', type=int, default=8)
    args = parser.parse_args()

    onnx_path = args.onnx
    if onnx_path is None:
        cands = [f for f in os.listdir(WEIGHTS) if f.lower().endswith('.onnx')]
        if len(cands) == 1:
            onnx_path = os.path.join(WEIGHTS, cands[0])
        else:
            sys.stderr.write("Need --onnx; weights/ does not contain a single .onnx\n")
            sys.exit(1)

    mrc_path = args.mrc
    if mrc_path is None:
        mrcs = [f for f in os.listdir(EXAMPLES) if f.lower().endswith('.mrc')]
        if not mrcs:
            sys.stderr.write("Need --mrc; example_images/ has no .mrc files\n")
            sys.exit(1)
        mrc_path = os.path.join(EXAMPLES, sorted(mrcs)[0])

    picks = onnx_pick(mrc_path, onnx_path, args.threshold, args.min_distance, args.scale)
    out_json = os.path.splitext(mrc_path)[0] + '_picks_onnx.json'
    with open(out_json, 'w') as f:
        json.dump(picks, f, indent=2)
    print(f"wrote {out_json}")

    if args.gt and os.path.exists(args.gt):
        compare_to_ground_truth(picks, args.gt)


if __name__ == "__main__":
    main()
