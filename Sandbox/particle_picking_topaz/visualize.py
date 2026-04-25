#!/usr/bin/env python
"""
Quick visualizer: overlays Topaz picks on the source micrograph.

By default, renders on a DENOISED version of the micrograph (via `topaz denoise`)
so particles are visible to the eye — matching the tutorial/paper figures. The
raw averaged micrograph is very noisy and particles are nearly invisible without
this step.

Usage:
    python visualize.py <path_to_mrc_file> [--picks picks.json] [--output overlay.png]
                        [--top N] [--radius R] [--view denoise|raw]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import mrcfile
import numpy as np


def _find_topaz():
    exe_dir = os.path.dirname(sys.executable)
    for d in (exe_dir, os.path.join(exe_dir, 'Scripts' if os.name == 'nt' else 'bin')):
        for name in ('topaz.exe', 'topaz'):
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which('topaz')


def load_mrc_image(path):
    with mrcfile.open(path, permissive=True) as m:
        data = m.data.astype(np.float32)
    if data.ndim == 3:
        data = data[0]
    lo, hi = np.percentile(data, [1, 99])
    data = np.clip((data - lo) / max(hi - lo, 1e-6), 0, 1)
    return data


def denoise_for_view(mrc_path, cache_path):
    """Run `topaz denoise` into a cache path. Skips if already denoised."""
    if os.path.exists(cache_path):
        return cache_path
    topaz_exe = _find_topaz()
    if topaz_exe is None:
        raise RuntimeError("topaz CLI not found; install topaz-em.")
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [topaz_exe, 'denoise', '--patch-size', '1024',
             '--output', tmpdir, mrc_path],
            check=True, capture_output=True, text=True,
        )
        produced = [f for f in os.listdir(tmpdir) if f.endswith('.mrc')]
        if not produced:
            raise RuntimeError("topaz denoise produced no MRC")
        shutil.move(os.path.join(tmpdir, produced[0]), cache_path)
    return cache_path


def main():
    parser = argparse.ArgumentParser(description="Overlay Topaz picks on a micrograph")
    parser.add_argument('mrc_path')
    parser.add_argument('--picks', default=None, help="Picks JSON (if omitted, runs the picker)")
    parser.add_argument('--output', default=None, help="Output PNG")
    parser.add_argument('--top', type=int, default=None, help="Show only top-N picks")
    parser.add_argument('--radius', type=int, default=None, help="Override circle radius in px")
    parser.add_argument('--view', choices=['denoise', 'raw'], default='denoise',
                        help="Background image to overlay on (default: denoise)")
    args = parser.parse_args()

    if args.picks:
        with open(args.picks) as f:
            picks = json.load(f)
    else:
        from pick_algorithm import process_pick
        picks = process_pick(args.mrc_path)

    if args.top is not None:
        picks = picks[:args.top]

    if args.view == 'denoise':
        stem = os.path.splitext(args.mrc_path)[0]
        denoised_path = stem + '_denoised.mrc'
        print(f"Denoising {os.path.basename(args.mrc_path)} for visualization...", file=sys.stderr)
        denoise_for_view(args.mrc_path, denoised_path)
        background = load_mrc_image(denoised_path)
    else:
        background = load_mrc_image(args.mrc_path)

    fig, ax = plt.subplots(figsize=(12, 12))
    ax.imshow(background, cmap='gray', interpolation='nearest')
    for p in picks:
        x, y = p['center']
        r = args.radius if args.radius is not None else p.get('radius', 50)
        circle = patches.Circle((x, y), r, linewidth=0.8, edgecolor='lime', facecolor='none')
        ax.add_patch(circle)
    ax.set_title(f"{os.path.basename(args.mrc_path)} — {len(picks)} picks [{args.view}]")
    ax.axis('off')

    out_path = args.output or os.path.splitext(args.mrc_path)[0] + '_picks.png'
    fig.savefig(out_path, dpi=150, bbox_inches='tight')
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main()
