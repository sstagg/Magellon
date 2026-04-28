#!/usr/bin/env python
"""
Topaz Particle Picking Script
Runs Topaz's pretrained CNN particle picker on a single MRC micrograph.

Usage:
    python pick_algorithm.py <path_to_mrc_file> [--model NAME] [--radius N]
                             [--threshold T] [--scale S]

Outputs JSON to stdout with detected particles (center, radius, score),
sorted by score descending. Coordinates are in the ORIGINAL image's pixel space.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile


def _find_topaz():
    """Locate the topaz CLI — prefer one in the active interpreter's Scripts/bin dir."""
    exe_dir = os.path.dirname(sys.executable)
    candidates_dirs = [
        exe_dir,  # Windows venv: python.exe lives in Scripts\
        os.path.join(exe_dir, 'Scripts' if os.name == 'nt' else 'bin'),  # Unix layout
    ]
    for d in candidates_dirs:
        for name in ('topaz.exe', 'topaz'):
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which('topaz')


def process_pick(mrc_path, model='resnet16', radius=14, threshold=-3.0, scale=8):
    """Run `topaz preprocess` + `topaz extract` and return parsed picks."""
    topaz_exe = _find_topaz()
    if topaz_exe is None:
        raise RuntimeError(
            "`topaz` CLI not found. Install with `pip install topaz-em` "
            "into the active Python environment."
        )

    mrc_path = os.path.abspath(mrc_path)
    if not os.path.exists(mrc_path):
        raise FileNotFoundError(f"MRC file not found: {mrc_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        preprocessed_dir = os.path.join(tmpdir, 'preprocessed')
        os.makedirs(preprocessed_dir, exist_ok=True)
        particles_txt = os.path.join(tmpdir, 'particles.txt')

        subprocess.run(
            [
                topaz_exe, 'preprocess',
                '--scale', str(scale),
                '--destdir', preprocessed_dir,
                mrc_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        preprocessed = [
            os.path.join(preprocessed_dir, f)
            for f in os.listdir(preprocessed_dir)
            if f.endswith('.mrc')
        ]
        if not preprocessed:
            raise RuntimeError("topaz preprocess produced no output MRC")

        subprocess.run(
            [
                topaz_exe, 'extract',
                '--model', model,
                '--radius', str(radius),
                '--threshold', str(threshold),
                '--up-scale', str(scale),
                '--output', particles_txt,
            ] + preprocessed,
            check=True,
            capture_output=True,
            text=True,
        )

        results = _parse_particles(particles_txt, radius * scale)

    results.sort(key=lambda r: -r['score'])
    return results


def _parse_particles(path, original_radius):
    results = []
    with open(path, 'r') as f:
        header = f.readline().strip().split('\t')
        try:
            x_idx = header.index('x_coord')
            y_idx = header.index('y_coord')
            score_idx = header.index('score')
        except ValueError as e:
            raise RuntimeError(f"Unexpected topaz extract header: {header}") from e

        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) <= max(x_idx, y_idx, score_idx):
                continue
            try:
                x = int(round(float(parts[x_idx])))
                y = int(round(float(parts[y_idx])))
                score = float(parts[score_idx])
            except ValueError:
                continue
            results.append({
                'center': [x, y],
                'radius': int(original_radius),
                'score': score,
            })
    return results


def main():
    parser = argparse.ArgumentParser(description="Topaz particle picker wrapper")
    parser.add_argument('mrc_path', help="Path to the input MRC micrograph")
    parser.add_argument('--model', default='resnet16',
                        help="Topaz pretrained model name or path to a .sav file")
    parser.add_argument('--radius', type=int, default=14,
                        help="NMS radius in preprocessed pixels (default 14)")
    parser.add_argument('--threshold', type=float, default=-3.0,
                        help="Log-likelihood threshold (default -3.0)")
    parser.add_argument('--scale', type=int, default=8,
                        help="Preprocess downsample factor (default 8)")
    args = parser.parse_args()

    try:
        results = process_pick(
            args.mrc_path,
            model=args.model,
            radius=args.radius,
            threshold=args.threshold,
            scale=args.scale,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"topaz failed: {e}\n")
        if e.stderr:
            sys.stderr.write(e.stderr)
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"Error processing image: {e}\n")
        sys.exit(1)

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
