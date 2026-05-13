#!/usr/bin/env python
"""
Batch benchmark: runs pick_algorithm.py against every MRC in example_images/
and writes per-image JSON + a summary CSV/JSON.

Usage:
    python run_benchmarks.py [--weights PATH] [--threshold 0.3] [--gpu 0]
                             [--input-dir example_images]
                             [--output-dir benchmark_outputs]
"""

import argparse
import csv
import json
import os
import sys
import time

from pick_algorithm import process_pick


def main():
    parser = argparse.ArgumentParser(description="Batch-benchmark crYOLO picking")
    parser.add_argument('--input-dir', default='example_images')
    parser.add_argument('--output-dir', default='benchmark_outputs')
    parser.add_argument('--weights', default=None)
    parser.add_argument('--threshold', type=float, default=0.3)
    parser.add_argument('--gpu', type=int, default=0)
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_dir = os.path.join(script_dir, args.input_dir) \
        if not os.path.isabs(args.input_dir) else args.input_dir
    output_dir = os.path.join(script_dir, args.output_dir) \
        if not os.path.isabs(args.output_dir) else args.output_dir
    picks_dir = os.path.join(output_dir, 'picks')
    os.makedirs(picks_dir, exist_ok=True)

    if not os.path.isdir(input_dir):
        sys.stderr.write(f"Input dir not found: {input_dir}\n")
        sys.exit(1)

    mrc_files = sorted(
        f for f in os.listdir(input_dir)
        if f.lower().endswith('.mrc')
    )
    if not mrc_files:
        sys.stderr.write(f"No .mrc files in {input_dir}\n")
        sys.exit(1)

    summary = []
    total_start = time.perf_counter()

    for name in mrc_files:
        mrc_path = os.path.join(input_dir, name)
        stem = os.path.splitext(name)[0]
        out_json = os.path.join(picks_dir, f"{stem}.json")

        start = time.perf_counter()
        error = None
        picks = []
        try:
            picks = process_pick(
                mrc_path,
                weights=args.weights,
                threshold=args.threshold,
                gpu=args.gpu,
            )
            with open(out_json, 'w') as f:
                json.dump(picks, f, indent=2)
        except Exception as e:
            error = str(e)
            sys.stderr.write(f"[{name}] FAILED: {e}\n")

        elapsed = time.perf_counter() - start
        summary.append({
            'image': name,
            'picks': len(picks),
            'elapsed_seconds': round(elapsed, 3),
            'error': error,
        })
        print(f"[{name}] picks={len(picks)} time={elapsed:.2f}s")

    total_elapsed = time.perf_counter() - total_start

    summary_obj = {
        'weights': args.weights,
        'threshold': args.threshold,
        'gpu': args.gpu,
        'total_seconds': round(total_elapsed, 3),
        'results': summary,
    }
    with open(os.path.join(output_dir, 'benchmark_summary.json'), 'w') as f:
        json.dump(summary_obj, f, indent=2)

    with open(os.path.join(output_dir, 'benchmark_summary.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['image', 'picks', 'elapsed_seconds', 'error'])
        for row in summary:
            writer.writerow([row['image'], row['picks'], row['elapsed_seconds'], row['error'] or ''])

    print(f"\nTotal: {total_elapsed:.2f}s over {len(mrc_files)} images")
    print(f"Wrote: {output_dir}/benchmark_summary.json / .csv")


if __name__ == '__main__':
    main()
