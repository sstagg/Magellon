#!/usr/bin/env python
"""
Topaz-Denoise Script
Denoises a single cryo-EM MRC micrograph using Topaz-Denoise's pretrained U-Net.

Usage:
    python denoise_algorithm.py <path_to_mrc_file> [--output OUT.mrc]
                                [--model unet] [--patch-size N]

Writes the denoised MRC to disk and prints a JSON summary to stdout.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

import mrcfile
import numpy as np


def _find_topaz():
    exe_dir = os.path.dirname(sys.executable)
    candidates_dirs = [
        exe_dir,
        os.path.join(exe_dir, 'Scripts' if os.name == 'nt' else 'bin'),
    ]
    for d in candidates_dirs:
        for name in ('topaz.exe', 'topaz'):
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which('topaz')


def process_denoise(mrc_path, output_path, model='unet', patch_size=1024):
    topaz_exe = _find_topaz()
    if topaz_exe is None:
        raise RuntimeError(
            "`topaz` CLI not found. Install with `pip install topaz-em` "
            "into the active Python environment."
        )

    mrc_path = os.path.abspath(mrc_path)
    output_path = os.path.abspath(output_path)
    if not os.path.exists(mrc_path):
        raise FileNotFoundError(f"MRC file not found: {mrc_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [
                topaz_exe, 'denoise',
                '--model', model,
                '--patch-size', str(patch_size),
                '--output', tmpdir,
                mrc_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        produced = [f for f in os.listdir(tmpdir) if f.endswith('.mrc')]
        if not produced:
            raise RuntimeError("topaz denoise produced no output MRC")
        src = os.path.join(tmpdir, produced[0])
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        shutil.move(src, output_path)

    with mrcfile.open(output_path, permissive=True) as m:
        data = m.data
        summary = {
            'input': mrc_path,
            'output': output_path,
            'model': model,
            'shape': list(data.shape),
            'dtype': str(data.dtype),
            'min': float(np.min(data)),
            'max': float(np.max(data)),
            'mean': float(np.mean(data)),
            'std': float(np.std(data)),
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Topaz-Denoise wrapper")
    parser.add_argument('mrc_path', help="Path to the input MRC micrograph")
    parser.add_argument('--output', default=None,
                        help="Path to write the denoised MRC (default: <input>_denoised.mrc)")
    parser.add_argument('--model', default='unet',
                        help="Topaz-Denoise pretrained model (default unet)")
    parser.add_argument('--patch-size', type=int, default=1024,
                        help="Tile size in pixels (default 1024)")
    args = parser.parse_args()

    output = args.output or os.path.splitext(args.mrc_path)[0] + '_denoised.mrc'

    try:
        summary = process_denoise(
            args.mrc_path,
            output,
            model=args.model,
            patch_size=args.patch_size,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"topaz failed: {e}\n")
        if e.stderr:
            sys.stderr.write(e.stderr)
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"Error denoising image: {e}\n")
        sys.exit(1)

    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
