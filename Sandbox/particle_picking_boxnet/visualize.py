#!/usr/bin/env python
"""
Quick visualizer: overlays BoxNet picks (and optionally the particle mask)
on the source micrograph.

Usage:
    python visualize.py <path_to_mrc_file> [--picks picks.json] [--output overlay.png]
                        [--top N] [--radius R] [--mask-overlay]
                        [--scale S] [--weights PATH]
"""

import argparse
import json
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import mrcfile
import numpy as np


def load_mrc_image(path):
    with mrcfile.open(path, permissive=True) as m:
        data = m.data.astype(np.float32)
    if data.ndim == 3:
        data = data[0]
    lo, hi = np.percentile(data, [1, 99])
    return np.clip((data - lo) / max(hi - lo, 1e-6), 0, 1)


def main():
    parser = argparse.ArgumentParser(description="Overlay BoxNet picks on a micrograph")
    parser.add_argument('mrc_path')
    parser.add_argument('--picks', default=None, help="Picks JSON (if omitted, runs the picker)")
    parser.add_argument('--output', default=None, help="Output PNG")
    parser.add_argument('--top', type=int, default=None)
    parser.add_argument('--radius', type=int, default=None)
    parser.add_argument('--mask-overlay', action='store_true',
                        help="Overlay the particle-channel mask under the boxes")
    parser.add_argument('--scale', type=int, default=8,
                        help="Downsample for live picker call / mask overlay (default 8)")
    parser.add_argument('--weights', default=None)
    args = parser.parse_args()

    if args.picks:
        with open(args.picks) as f:
            picks = json.load(f)
    else:
        from pick_algorithm import process_pick
        picks = process_pick(args.mrc_path, weights=args.weights, scale=args.scale)

    if args.top is not None:
        picks = picks[:args.top]

    background = load_mrc_image(args.mrc_path)
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.imshow(background, cmap='gray', interpolation='nearest')

    if args.mask_overlay:
        from mask_algorithm import compute_mask
        masks = compute_mask(args.mrc_path, weights=args.weights, scale=args.scale)
        particle = masks[:, :, 1]
        # Upscale mask to original resolution via nearest-neighbour repeat
        upscaled = np.kron(particle, np.ones((args.scale, args.scale), dtype=np.float32))
        Hb, Wb = background.shape
        upscaled = upscaled[:Hb, :Wb]
        if upscaled.shape == background.shape:
            ax.imshow(upscaled, cmap='hot', alpha=0.35, interpolation='nearest')

    for p in picks:
        x, y = p['center']
        r = args.radius if args.radius is not None else p.get('radius', 50)
        circle = patches.Circle((x, y), r, linewidth=0.8, edgecolor='lime', facecolor='none')
        ax.add_patch(circle)

    ax.set_title(f"{os.path.basename(args.mrc_path)} — {len(picks)} picks")
    ax.axis('off')

    out_path = args.output or os.path.splitext(args.mrc_path)[0] + '_picks.png'
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main()
