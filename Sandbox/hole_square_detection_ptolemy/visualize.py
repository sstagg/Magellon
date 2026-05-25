#!/usr/bin/env python
"""
Draw ptolemy detections on top of an image.

Inputs:
  --image    An MRC file (rendered via scale_image, like CoreService's
             MrcImageService) OR a PNG/TIFF/JPG already at the target size.
  --json     Detections JSON produced by lowmag_algorithm.py or medmag_algorithm.py.
  --out      Output PNG path.

Notes:
  Detection coordinates come from ptolemy in its own `(axis0, axis1)` order.
  Empirically, those values are what `matplotlib.patches.Polygon` consumes
  directly (i.e. (plot_x, plot_y)) — that's how ptolemy's own viz_boxes
  renders them. PIL's draw.polygon also takes (x, y), so we pass them through
  without swapping.

Usage:
  python visualize.py --image example_images/low_mag/20may08a_16760340.mrc \
                      --json  runs/lowmag_20may08a.json \
                      --out   runs/lowmag_20may08a.png
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ---------- MRC -> scaled PIL image (matches CoreService MrcImageService) ----

def _down_sample(img, height):
    m, n = img.shape[-2:]
    ds_factor = m / height
    width = round(n / ds_factor / 2) * 2
    F = np.fft.rfft2(img)
    A = F[..., 0:height // 2, 0:width // 2 + 1]
    B = F[..., -height // 2:, 0:width // 2 + 1]
    F = np.concatenate([A, B], axis=0)
    return np.fft.irfft2(F, s=(height, width))


def _scale_image(img, height, lowpercent=1, highpercent=99):
    new = _down_sample(img, height)
    vmin, vmax = np.percentile(new, (lowpercent, highpercent))
    new = np.clip(new, vmin, vmax)
    new = (new - new.min()) / ((new.max() - new.min()) + 1e-7) * 255
    return Image.fromarray(new).convert('L')


def load_image(path, height):
    """Return (PIL image in RGB, original_shape) given MRC or raster input."""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.mrc', '.mrcs'):
        import mrcfile
        with mrcfile.open(path, permissive=True) as mrc:
            arr = mrc.data.reshape(mrc.data.shape[-2], mrc.data.shape[-1])
        orig_shape = arr.shape
        return _scale_image(arr, height).convert('RGB'), orig_shape

    im = Image.open(path).convert('RGB')
    # For pre-rendered rasters the "original" detection frame is assumed to be
    # the same as the raster's own pixel grid (no coord rescaling).
    return im, (im.size[1], im.size[0])


# ---------- drawing ----------------------------------------------------------

def _color_ramp(score, smin, smax):
    t = 0.0 if smax == smin else (score - smin) / (smax - smin)
    r = int(255 * (1 - t))
    g = int(255 * t)
    return (r, g, 0)


_LABEL_FIELDS = ('rank', 'score', 'brightness', 'area')


def _format_label(rank, det, fields):
    parts = []
    for f in fields:
        if f == 'rank':
            parts.append(f"#{rank}")
        elif f == 'score' and 'score' in det:
            parts.append(f"s={det['score']:.2f}")
        elif f == 'brightness' and 'brightness' in det:
            parts.append(f"b={det['brightness']:.0f}")
        elif f == 'area' and 'area' in det:
            parts.append(f"a={det['area']:.0f}")
    return ' '.join(parts)


def draw_detections(im, dets, orig_shape, line_width=2, label_fields=('score',),
                    score_min=None):
    h_out, w_out = im.size[1], im.size[0]
    h_orig, w_orig = orig_shape
    s0 = h_out / h_orig
    s1 = w_out / w_orig

    ranked = list(enumerate(dets, start=1))
    if score_min is not None:
        ranked = [(r, d) for r, d in ranked if d['score'] >= score_min]
    if not ranked:
        return im

    scores = [d['score'] for _, d in ranked]
    smin, smax = min(scores), max(scores)

    draw = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    for rank, d in ranked:
        poly = [(v[0] * s0, v[1] * s1) for v in d['vertices']]
        cx = d['center'][0] * s0
        cy = d['center'][1] * s1
        col = _color_ramp(d['score'], smin, smax)

        draw.polygon(poly, outline=col, width=line_width)
        r = max(2, line_width)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)

        label = _format_label(rank, d, label_fields)
        if label:
            draw.text((cx + 5, cy + 5), label, fill=col, font=font)
    return im


# ---------- CLI --------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Overlay ptolemy detections on an image.")
    ap.add_argument('--image', required=True, help='MRC / PNG / TIFF / JPG input.')
    ap.add_argument('--json',  required=True, dest='json_path', help='Detections JSON.')
    ap.add_argument('--out',   required=True, help='Output PNG path.')
    ap.add_argument('--height', type=int, default=1024,
                    help='Target height when rendering from MRC (ignored for rasters).')
    ap.add_argument('--line-width', type=int, default=2)
    ap.add_argument('--no-labels', action='store_true', help='Suppress all text labels.')
    ap.add_argument('--label-fields', default='score',
                    help=('Comma-separated subset of: ' + ','.join(_LABEL_FIELDS)
                          + '. Default: score. Use "all" for everything available.'))
    ap.add_argument('--score-min', type=float, default=None,
                    help='Only draw detections with score >= this value.')
    args = ap.parse_args()

    im, orig_shape = load_image(args.image, args.height)
    print(f"image: {args.image}   input-frame shape: {orig_shape}   canvas: {im.size[1]}x{im.size[0]}")

    with open(args.json_path) as f:
        dets = json.load(f)
    print(f"detections in JSON: {len(dets)}"
          + (f", drawing score >= {args.score_min}" if args.score_min is not None else ""))

    if args.no_labels:
        fields = ()
    elif args.label_fields.strip().lower() == 'all':
        fields = _LABEL_FIELDS
    else:
        fields = tuple(f.strip() for f in args.label_fields.split(',') if f.strip())
        unknown = [f for f in fields if f not in _LABEL_FIELDS]
        if unknown:
            ap.error(f"unknown --label-fields: {unknown}. choose from {_LABEL_FIELDS}")

    im = draw_detections(im, dets, orig_shape,
                         line_width=args.line_width,
                         label_fields=fields,
                         score_min=args.score_min)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    im.save(args.out)
    print(f"saved: {args.out}")


if __name__ == '__main__':
    main()
