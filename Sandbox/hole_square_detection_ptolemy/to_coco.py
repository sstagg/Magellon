#!/usr/bin/env python
"""
Export ptolemy detections (MRC + JSON) as a COCO-format training dataset.

For each --add <image> <json> <category> triple, the script:
  1. Renders the image (MRC via FFT-downsample + 1-99% clip, or a raster
     passed through) into <out-dir>/images/<name>.png.
  2. Scales every detection polygon into the rendered PNG's pixel frame.
  3. Emits one COCO annotation per detection, with both an axis-aligned bbox
     and the rotated polygon in `segmentation`. The ptolemy `score` and
     `brightness` (low-mag only) are preserved as extra fields.

Example:
  python to_coco.py \
    --add example_images/low_mag/20may08a_16760340.mrc runs/lowmag_20may08a.json square \
    --add example_images/med_mag/21feb25a_23139789.mrc runs/medmag_21feb25a.json hole \
    --out-dir coco/ --height 1024

Writes coco/images/*.png and coco/annotations.json.

The output follows the COCO Object Detection schema
(https://cocodataset.org/#format-data) and is consumable by anything that
reads a COCO JSON: Detectron2, MMDetection, YOLOX, Ultralytics, fiftyone, etc.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from PIL import Image

# Reuse the renderer from visualize.py so MRC -> PNG stays byte-identical.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from visualize import load_image


def _polygon_area(xs, ys):
    n = len(xs)
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += xs[i] * ys[j] - xs[j] * ys[i]
    return abs(s) * 0.5


def _bbox_xywh(xs, ys):
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return [x0, y0, x1 - x0, y1 - y0]


def _detections_to_annotations(dets, orig_shape, canvas_size, image_id,
                               category_id, starting_ann_id, score_min=None):
    h_out, w_out = canvas_size[1], canvas_size[0]
    h_orig, w_orig = orig_shape
    s0 = h_out / h_orig
    s1 = w_out / w_orig

    anns = []
    aid = starting_ann_id
    for rank, d in enumerate(dets, start=1):
        if score_min is not None and d['score'] < score_min:
            continue
        xs = [v[0] * s0 for v in d['vertices']]
        ys = [v[1] * s1 for v in d['vertices']]
        seg = []
        for x, y in zip(xs, ys):
            seg.extend([x, y])

        ann = {
            'id': aid,
            'image_id': image_id,
            'category_id': category_id,
            'bbox': _bbox_xywh(xs, ys),
            'area': _polygon_area(xs, ys),
            'segmentation': [seg],
            'iscrowd': 0,
            'score': float(d['score']),
            'rank': rank,
        }
        if 'brightness' in d:
            ann['brightness'] = float(d['brightness'])
        anns.append(ann)
        aid += 1
    return anns, aid


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--add', action='append', nargs=3, metavar=('IMAGE', 'JSON', 'CATEGORY'),
                    required=True, help='Add a (image, detections-json, category-name) triple. Repeatable.')
    ap.add_argument('--out-dir', required=True, help='Output directory (will contain images/ and annotations.json).')
    ap.add_argument('--height', type=int, default=1024,
                    help='Target height for MRC rendering. Rasters pass through at native size.')
    ap.add_argument('--score-min', type=float, default=None,
                    help='Skip detections below this score.')
    ap.add_argument('--dataset-name', default='ptolemy-exports',
                    help='Name stamped into COCO "info.description".')
    args = ap.parse_args()

    images_dir = os.path.join(args.out_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    categories_by_name = {}
    coco = {
        'info': {
            'description': args.dataset_name,
            'date_created': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'generator': 'to_coco.py (ptolemy detections -> COCO)',
        },
        'licenses': [{'id': 1, 'name': 'CC BY-NC 4.0',
                      'url': 'https://creativecommons.org/licenses/by-nc/4.0/'}],
        'images': [],
        'annotations': [],
        'categories': [],
    }

    image_id = 1
    ann_id = 1
    skipped = 0

    for image_path, json_path, category_name in args.add:
        if category_name not in categories_by_name:
            cid = len(categories_by_name) + 1
            categories_by_name[category_name] = cid
            coco['categories'].append({
                'id': cid, 'name': category_name, 'supercategory': 'ptolemy',
            })
        category_id = categories_by_name[category_name]

        im, orig_shape = load_image(image_path, args.height)
        stem = os.path.splitext(os.path.basename(image_path))[0]
        png_name = f"{stem}.png"
        png_path = os.path.join(images_dir, png_name)
        im.save(png_path)

        coco['images'].append({
            'id': image_id,
            'file_name': png_name,
            'height': im.size[1],
            'width': im.size[0],
            'license': 1,
            'date_captured': '',
            'source_file': os.path.abspath(image_path),
        })

        with open(json_path) as f:
            dets = json.load(f)
        n_before = len(dets)
        anns, ann_id = _detections_to_annotations(
            dets, orig_shape, im.size, image_id, category_id, ann_id,
            score_min=args.score_min)
        coco['annotations'].extend(anns)
        skipped += n_before - len(anns)

        print(f"[{category_name}] {image_path} -> {png_path}  "
              f"({len(anns)} annotations kept, {n_before - len(anns)} below threshold)")
        image_id += 1

    out_json = os.path.join(args.out_dir, 'annotations.json')
    with open(out_json, 'w') as f:
        json.dump(coco, f, indent=2)

    print()
    print(f"wrote: {out_json}")
    print(f"  images      : {len(coco['images'])}")
    print(f"  annotations : {len(coco['annotations'])}  (skipped {skipped} below score-min)")
    print(f"  categories  : {[c['name'] for c in coco['categories']]}")


if __name__ == '__main__':
    main()
