#!/usr/bin/env python
"""
BoxNet 3-channel mask producer.

Same forward pass as pick_algorithm.py, but emits the raw mask volume
instead of running centroid detection. Output is one of:

  - `.npz` with three (H, W) arrays in [0, 1]: background, particle, dirt
  - `.mrc` 3-channel (Z=3) — convenient for downstream tools that already
    speak MRC (e.g. plugin pipelines that want to write the mask alongside
    the micrograph and reuse it)

Usage:
    python mask_algorithm.py <path_to_mrc_file> [--weights PATH] [--scale S]
                             [--device D] [--output mask.npz|mask.mrc]

The mask file is the building block for a future MICROGRAPH_QC plugin —
the Cianfrocco-lab `eval_micrograph` tool takes the particle channel's
radial power spectrum and feeds it to a 1D-CNN to produce a single
P(good) per micrograph. With this script that pipeline becomes a two-step
shell sequence (mask -> score) rather than a re-implementation.
"""

import argparse
import os
import sys

import numpy as np


def _default_weights():
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
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    return 'cuda' if torch.cuda.is_available() else 'cpu'


def _load_mrc(path):
    import mrcfile
    with mrcfile.open(path, permissive=True) as m:
        data = np.asarray(m.data, dtype=np.float32)
    if data.ndim == 3 and data.shape[0] == 1:
        data = data[0]
    if data.ndim != 2:
        raise RuntimeError(f"Expected 2D micrograph, got shape {data.shape}")
    return data


def _downsample(img, scale):
    if scale == 1:
        return img.astype(np.float32)
    h, w = img.shape
    new_h = (h // scale) * scale
    new_w = (w // scale) * scale
    cropped = img[:new_h, :new_w].astype(np.float32)
    return cropped.reshape(new_h // scale, scale, new_w // scale, scale).mean(axis=(1, 3))


def compute_mask(mrc_path, weights=None, scale=8, device='auto'):
    """Return (H, W, 3) BoxNet mask: background / particle / dirt."""
    from boxnet_pt import BoxnetPT

    weights = weights or _default_weights()
    if weights is None:
        raise RuntimeError("No weights specified and weights/ has no single .pt.")

    raw = _load_mrc(mrc_path)
    downsampled = _downsample(raw, scale)

    model = BoxnetPT(weights).to(_resolve_device(device))
    return model(downsampled)


def _write_npz(masks, output):
    np.savez_compressed(
        output,
        background=masks[:, :, 0].astype(np.float32),
        particle=masks[:, :, 1].astype(np.float32),
        dirt=masks[:, :, 2].astype(np.float32),
    )


def _write_mrc(masks, output):
    import mrcfile
    # (H, W, 3) -> (3, H, W) so MRC sees three "slices" along Z
    stacked = np.ascontiguousarray(np.transpose(masks, (2, 0, 1)).astype(np.float32))
    with mrcfile.new(output, overwrite=True) as m:
        m.set_data(stacked)


def main():
    parser = argparse.ArgumentParser(description="BoxNet 3-channel mask producer")
    parser.add_argument('mrc_path')
    parser.add_argument('--weights', default=None)
    parser.add_argument('--scale', type=int, default=8)
    parser.add_argument('--device', choices=['cuda', 'cpu', 'auto'], default='auto')
    parser.add_argument('--output', default=None,
                        help="Output path; extension picks the writer (.npz | .mrc). "
                             "Default: <input>_boxnet_mask.npz")
    args = parser.parse_args()

    output = args.output or (os.path.splitext(args.mrc_path)[0] + '_boxnet_mask.npz')

    try:
        masks = compute_mask(args.mrc_path, weights=args.weights,
                             scale=args.scale, device=args.device)
    except Exception as e:
        sys.stderr.write(f"Error processing image: {e}\n")
        sys.exit(1)

    if output.lower().endswith('.mrc'):
        _write_mrc(masks, output)
    else:
        _write_npz(masks, output)

    print(
        f"Wrote {output}  shape={masks.shape}  "
        f"background_mean={masks[:, :, 0].mean():.4f}  "
        f"particle_mean={masks[:, :, 1].mean():.4f}  "
        f"dirt_mean={masks[:, :, 2].mean():.4f}"
    )


if __name__ == '__main__':
    main()
