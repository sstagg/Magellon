#!/usr/bin/env python
"""Run benchmark timing for micrograph evaluation examples.

Iterates every image inside input_examples/<category>/ one by one,
scores each with micrograph_eval.py, and writes per-image .txt score
files plus JSON and CSV summaries into benchmark_outputs/.
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_EXAMPLE_DIR = Path('input_examples')
DEFAULT_OUTPUT_DIR = Path('benchmark_outputs')
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}


def discover_inputs(example_dir: Path):
    """Yield (category_name, image_path) for every image under example_dir."""
    for category in sorted(example_dir.iterdir()):
        if not category.is_dir():
            continue
        images = sorted(p for p in category.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
        for img in images:
            yield category.name, img


def run_one(script: Path, image_path: Path, txt_output: Path):
    """Run the evaluator on a single image, save score to txt, return result dict."""
    command = [sys.executable, str(script), '--inputfile', str(image_path)]

    start = time.perf_counter()
    proc = subprocess.run(command, capture_output=True, text=True)
    duration = time.perf_counter() - start

    # stdout contains status lines followed by the score on the last line
    score = None
    if proc.returncode == 0:
        for line in reversed(proc.stdout.splitlines()):
            try:
                score = float(line.strip())
                break
            except ValueError:
                continue

    # Save score to .txt file
    txt_output.parent.mkdir(parents=True, exist_ok=True)
    with txt_output.open('w', encoding='utf-8') as f:
        if score is not None:
            f.write(f"{score}\n")
        else:
            f.write(f"ERROR\n{proc.stderr.strip() or proc.stdout.strip()}\n")

    return {
        'category': image_path.parent.name,
        'input_path': str(image_path.resolve()),
        'score_txt': str(txt_output.resolve()),
        'duration_seconds': duration,
        'returncode': proc.returncode,
        'stdout': proc.stdout.strip(),
        'stderr': proc.stderr.strip(),
        'success': proc.returncode == 0,
        'score': score,
        'error': None if proc.returncode == 0 else proc.stderr.strip() or proc.stdout.strip(),
    }


def write_summary_json(results: list, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({'examples': results}, indent=2))


def write_summary_csv(results: list, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ['category', 'input_file', 'score', 'duration_seconds', 'success', 'score_txt', 'error']
    with output_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                'category':        r['category'],
                'input_file':      r['input_path'],
                'score':           r['score'] if r['score'] is not None else '',
                'duration_seconds': r['duration_seconds'],
                'success':         r['success'],
                'score_txt':       r['score_txt'],
                'error':           r['error'] or '',
            })


def parse_args():
    parser = argparse.ArgumentParser(
        description='Benchmark micrograph evaluation on input_examples.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--example-dir', type=Path, default=DEFAULT_EXAMPLE_DIR,
                        help='Root directory with category subdirectories containing images')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR,
                        help='Directory for per-image .txt scores and summary files')
    parser.add_argument('--cli-script', type=Path, default=Path('micrograph_eval.py'),
                        help='Path to the micrograph evaluator CLI script')
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.example_dir.exists():
        print(f'Error: example directory not found: {args.example_dir}', file=sys.stderr)
        sys.exit(1)
    if not args.cli_script.exists():
        print(f'Error: CLI script not found: {args.cli_script}', file=sys.stderr)
        sys.exit(1)

    pairs = list(discover_inputs(args.example_dir))
    if not pairs:
        print(f'No image files found under {args.example_dir}', file=sys.stderr)
        sys.exit(1)

    results = []
    for category, image_path in pairs:
        txt_out = args.output_dir / category / f'{image_path.stem}_score.txt'
        print(f'Evaluating [{category}] {image_path.name} ...')
        result = run_one(args.cli_script, image_path, txt_out)
        results.append(result)
        if result['success'] and result['score'] is not None:
            print(f'  score = {result["score"]:.4f}  ({result["duration_seconds"]:.3f}s)  -> {txt_out}')
        elif result['success']:
            print(f'  completed but score could not be parsed  ({result["duration_seconds"]:.3f}s)')
        else:
            print(f'  FAILED: {result["error"]}')

    write_summary_json(results, args.output_dir / 'benchmark_summary.json')
    write_summary_csv(results,  args.output_dir / 'benchmark_summary.csv')

    print(f'\nBenchmark complete.')
    print(f'  Per-image scores : {args.output_dir}/<category>/<image>_score.txt')
    print(f'  JSON summary     : {args.output_dir / "benchmark_summary.json"}')
    print(f'  CSV summary      : {args.output_dir / "benchmark_summary.csv"}')


if __name__ == '__main__':
    main()
