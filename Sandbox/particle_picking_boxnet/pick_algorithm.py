#!/usr/bin/env python
"""
BoxNet Particle Picking Script
Runs Warp's BoxNet v2 (3-class mask) on a single MRC micrograph and converts
the particle-channel mask to a list of pick centroids via local-maxima peak
detection.

Usage:
    python pick_algorithm.py <path_to_mrc_file> [--weights PATH] [--threshold T]
                             [--min-distance D] [--scale S] [--device D]

Outputs JSON to stdout in the same shape as the topaz / crYOLO sandboxes:

    [{"center":[x, y], "radius": pixels, "score": mask_prob}, ...]

Coordinates are in ORIGINAL image pixel space — peaks detected in the
downsampled inference frame are multiplied by `--scale` on the way out.
"""

import argparse
import json
import os
import sys

import numpy as np

# Lazy imports of torch / scipy / mrcfile happen inside process_pick so that
# `python pick_algorithm.py --help` works without the heavy stack installed.


def _default_weights():
    """Pick a *.pt from weights/ if exactly one is present."""
    weights_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weights')
    if not os.path.isdir(weights_dir):
        return None
    pts = [f for f in os.listdir(weights_dir) if f.lower().endswith('.pt')]
    return os.path.join(weights_dir, pts[0]) if len(pts) == 1 else None


def _resolve_device(name):
    import torch
    if name == 'cpu':
        return 'cpu'
    if name == 'cuda':
        if not torch.cuda.is_available():
            sys.stderr.write("--device cuda requested but CUDA not available; "
                             "falling back to CPU.\n")
            return 'cpu'
        return 'cuda'
    return 'cuda' if torch.cuda.is_available() else 'cpu'


def _load_mrc(path):
    """Read the MRC as float32; collapse a singleton z if present."""
    import mrcfile
    with mrcfile.open(path, permissive=True) as m:
        data = np.asarray(m.data, dtype=np.float32)
    if data.ndim == 3 and data.shape[0] == 1:
        data = data[0]
    if data.ndim != 2:
        raise RuntimeError(f"Expected 2D micrograph, got shape {data.shape}")
    return data


def _downsample(img, scale):
    """
    Block-mean downsample by an integer factor. Matches Warp's default — the
    BoxNet training was done at ~8 Å/pixel, so a typical 1 Å/pixel micrograph
    needs scale=8. For inputs already at the model's native resolution pass
    --scale 1.
    """
    if scale == 1:
        return img.astype(np.float32)
    h, w = img.shape
    new_h = (h // scale) * scale
    new_w = (w // scale) * scale
    cropped = img[:new_h, :new_w].astype(np.float32)
    return cropped.reshape(new_h // scale, scale, new_w // scale, scale).mean(axis=(1, 3))


def _peak_centroids(particle_mask, threshold, min_distance):
    """
    Pull a list of (x, y, score) peaks out of the particle-channel mask.

    Uses skimage.feature.peak_local_max — same semantics as topaz NMS at this
    level: enforce a minimum centre-to-centre spacing and a probability floor.
    """
    from skimage.feature import peak_local_max
    coords = peak_local_max(
        particle_mask,
        min_distance=max(1, int(min_distance)),
        threshold_abs=float(threshold),
        exclude_border=False,
    )  # returns (row, col) i.e. (y, x)
    scores = particle_mask[coords[:, 0], coords[:, 1]] if len(coords) else np.array([])
    return coords, scores


def process_pick(mrc_path, weights=None, threshold=0.5, min_distance=14,
                 scale=8, device='auto'):
    """Top-level entry: image path → list of pick dicts."""
    from boxnet_pt import BoxnetPT

    weights = weights or _default_weights()
    if weights is None:
        raise RuntimeError(
            "No weights specified and weights/ does not contain a single .pt "
            "model. Pass --weights /path/to/boxnet.pt."
        )

    mrc_path = os.path.abspath(mrc_path)
    if not os.path.exists(mrc_path):
        raise FileNotFoundError(f"MRC file not found: {mrc_path}")

    raw = _load_mrc(mrc_path)
    downsampled = _downsample(raw, scale)

    model = BoxnetPT(weights).to(_resolve_device(device))
    masks = model(downsampled)  # (H', W', 3)
    particle_mask = masks[:, :, 1]

    coords, scores = _peak_centroids(particle_mask, threshold, min_distance)

    # Estimate a per-pick radius by half the connected-component extent at
    # the peak — cheap proxy in lieu of a learned size head. For now we report
    # min_distance/2 in preprocessed pixels (scaled up); plugin compute can
    # override if a learned size becomes available.
    half_box = max(1, int(min_distance // 2)) * scale

    results = []
    for (yp, xp), s in zip(coords, scores):
        results.append({
            'center': [int(xp * scale), int(yp * scale)],
            'radius': int(half_box),
            'score': float(s),
        })

    results.sort(key=lambda r: -r['score'])
    return results


def main():
    parser = argparse.ArgumentParser(description="BoxNet particle picker wrapper")
    parser.add_argument('mrc_path', help="Path to the input MRC micrograph")
    parser.add_argument('--weights', default=None,
                        help="Path to boxnet.pt (auto-picked from weights/ if "
                             "exactly one .pt is present)")
    parser.add_argument('--threshold', type=float, default=0.5,
                        help="Particle-channel probability cutoff in [0,1] (default 0.5)")
    parser.add_argument('--min-distance', type=int, default=14,
                        help="Minimum centre-to-centre distance in preprocessed pixels "
                             "(default 14)")
    parser.add_argument('--scale', type=int, default=8,
                        help="Downsample factor on the way in (default 8)")
    parser.add_argument('--device', choices=['cuda', 'cpu', 'auto'], default='auto',
                        help="Inference device (default auto)")
    args = parser.parse_args()

    try:
        results = process_pick(
            args.mrc_path,
            weights=args.weights,
            threshold=args.threshold,
            min_distance=args.min_distance,
            scale=args.scale,
            device=args.device,
        )
    except Exception as e:
        sys.stderr.write(f"Error processing image: {e}\n")
        sys.exit(1)

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
