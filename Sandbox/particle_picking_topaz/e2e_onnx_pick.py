#!/usr/bin/env python
"""
End-to-end ONNX particle picking — replaces `topaz extract` with
onnxruntime + numpy NMS, then compares the picks to the canonical
picks.json (which was produced by `topaz extract` via the original
torch path).

If this matches the original picks count and top-N coords, the ONNX
plugin path is faithful to upstream and we can drop the topaz CLI from
the runtime.

Pipeline (mirrors topaz score_images + extract_particles):
  1. topaz preprocess (downsample 8x + GMM normalize) — vendored later;
     for now use the topaz CLI to produce a reference preprocessed MRC.
  2. Forward through ONNX detector -> score_map (numpy)
  3. NMS at radius=14, threshold=-3
  4. Multiply coords by 8 (up_scale) -> original-image space
  5. Compare to picks.json
"""
import json
import os
import subprocess
import sys
import tempfile
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import onnxruntime as ort

import mrcfile
from topaz.algorithms import non_maximum_suppression

ROOT = os.path.dirname(os.path.abspath(__file__))
WEIGHTS = os.path.join(ROOT, "weights")
TEST_MRC = os.path.join(ROOT, "example_images", "14sep05c_00024sq_00003hl_00002es_c.mrc")
GROUND_TRUTH = os.path.join(ROOT, "example_images", "picks.json")

SCALE = 8
RADIUS = 14
THRESHOLD = -3.0
MODEL_ONNX = "topaz_resnet16_u64.onnx"


def topaz_exe():
    return os.path.join(os.path.dirname(sys.executable), "topaz.exe")


def preprocess_mrc():
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(
            [topaz_exe(), "preprocess", "--scale", str(SCALE),
             "--destdir", td, TEST_MRC],
            check=True, capture_output=True, text=True,
        )
        produced = next(f for f in os.listdir(td) if f.endswith(".mrc"))
        with mrcfile.open(os.path.join(td, produced), permissive=True) as m:
            return np.asarray(m.data, dtype=np.float32).copy()


def onnx_pick():
    img = preprocess_mrc()
    print(f"preprocessed image: {img.shape}, range [{img.min():.3f}, {img.max():.3f}]")

    sess = ort.InferenceSession(os.path.join(WEIGHTS, MODEL_ONNX),
                                providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    score_map = sess.run(None, {in_name: img[np.newaxis, np.newaxis]})[0][0, 0]
    print(f"score map: {score_map.shape}, range [{score_map.min():.3f}, {score_map.max():.3f}]")

    scores, coords = non_maximum_suppression(score_map, r=RADIUS, threshold=THRESHOLD)
    print(f"NMS picks (preprocessed space): {len(scores)}")

    # Upscale coords to original-image pixel space (matches `topaz extract`'s
    # `coords*scale` step where scale = up_scale/down_scale = SCALE).
    coords_full = (coords * SCALE).astype(int)

    # Sort by score desc, mirror picks.json shape
    order = np.argsort(scores)[::-1]
    return [
        {"center": [int(coords_full[i, 0]), int(coords_full[i, 1])],
         "radius": RADIUS * SCALE,
         "score": float(scores[i])}
        for i in order
    ]


def compare_to_ground_truth(onnx_picks):
    with open(GROUND_TRUTH) as f:
        gt = json.load(f)

    print()
    print(f"ground truth picks (picks.json): {len(gt)}")
    print(f"ONNX picks                     : {len(onnx_picks)}")

    # Top-10 score side-by-side
    print()
    print(f"{'idx':>4}  {'gt center':>15}  {'gt score':>10}    {'onnx center':>15}  {'onnx score':>10}")
    for i in range(min(10, len(gt), len(onnx_picks))):
        g = gt[i]; o = onnx_picks[i]
        print(f"{i:>4}  {str(g['center']):>15}  {g['score']:>10.4f}    "
              f"{str(o['center']):>15}  {o['score']:>10.4f}")

    # Match by center proximity within 1 pixel (preprocessing step has
    # rounding so identical-down-to-the-pixel matches across platforms
    # aren't guaranteed, but we expect the vast majority to coincide).
    gt_set = {(p["center"][0], p["center"][1]) for p in gt}
    onnx_set = {(p["center"][0], p["center"][1]) for p in onnx_picks}
    common = gt_set & onnx_set
    print()
    print(f"exact-pixel coordinate matches : {len(common)} / {len(gt_set)}")
    print(f"only in ground truth           : {len(gt_set - onnx_set)}")
    print(f"only in ONNX path              : {len(onnx_set - gt_set)}")

    # Score-distribution sanity
    gt_scores = sorted([p["score"] for p in gt], reverse=True)
    on_scores = sorted([p["score"] for p in onnx_picks], reverse=True)
    print()
    print(f"max score      gt={gt_scores[0]:.4f}     onnx={on_scores[0]:.4f}")
    print(f"score >= 2     gt={sum(s >= 2 for s in gt_scores)}  onnx={sum(s >= 2 for s in on_scores)}")
    print(f"score >= 0     gt={sum(s >= 0 for s in gt_scores)}  onnx={sum(s >= 0 for s in on_scores)}")


if __name__ == "__main__":
    picks = onnx_pick()
    out = os.path.join(ROOT, "example_images", "picks_onnx.json")
    with open(out, "w") as f:
        json.dump(picks, f, indent=2)
    print(f"wrote {out}")
    compare_to_ground_truth(picks)
