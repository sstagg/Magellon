#!/usr/bin/env python
"""
Stage eval_micrograph's PNG fixtures into this sandbox as MRCs.

The Cianfrocco-lab eval_micrograph repo ships three labelled fixtures
(great.png / bad1.png / empty_avg.jpg) intended as known-good / known-bad
references for the BoxNet feature pipeline. Our `pick_algorithm.py` takes
MRC, so this script reads the PNGs/JPEG, converts to grayscale float32,
and writes 2-D MRCs alongside.

By default it looks for the fixtures at:
    %USERPROFILE%/Downloads/eval_micrograph/eval_micrograph/

Pass --source to override.

Resulting files land in example_images/ next to the topaz test MRC.
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import mrcfile
except ImportError:
    sys.stderr.write("mrcfile is required; pip install mrcfile\n")
    sys.exit(1)


FIXTURES = ['great.png', 'bad1.png', 'empty_avg.jpg']


def _default_source():
    return Path(os.path.expanduser("~/Downloads/eval_micrograph/eval_micrograph"))


def convert_one(src_path: Path, dest_dir: Path) -> Path:
    img = Image.open(src_path).convert('L')
    arr = np.array(img, dtype=np.float32)
    out_path = dest_dir / (src_path.stem + ".mrc")
    with mrcfile.new(out_path, overwrite=True) as m:
        m.set_data(arr)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Convert eval_micrograph PNGs to MRC")
    parser.add_argument('--source', default=None,
                        help="Path to the eval_micrograph fixture directory "
                             "(default: ~/Downloads/eval_micrograph/eval_micrograph)")
    parser.add_argument('--dest', default=None,
                        help="Destination dir (default: ./example_images)")
    args = parser.parse_args()

    source = Path(args.source) if args.source else _default_source()
    dest = Path(args.dest) if args.dest else Path(__file__).parent / 'example_images'
    dest.mkdir(parents=True, exist_ok=True)

    if not source.is_dir():
        sys.stderr.write(f"Source dir not found: {source}\n")
        sys.exit(1)

    written = 0
    for name in FIXTURES:
        src = source / name
        if not src.exists():
            sys.stderr.write(f"  skip (missing): {src}\n")
            continue
        out = convert_one(src, dest)
        with mrcfile.open(out, permissive=True) as m:
            data = m.data
            print(f"  wrote {out.name}  shape={data.shape}  "
                  f"range=[{data.min():.1f}, {data.max():.1f}]")
        written += 1

    print(f"\nConverted {written}/{len(FIXTURES)} fixtures into {dest}")


if __name__ == '__main__':
    main()
