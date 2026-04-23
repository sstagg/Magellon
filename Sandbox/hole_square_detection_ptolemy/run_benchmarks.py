#!/usr/bin/env python
"""
Run benchmark timing over low-mag and med-mag example MRC files.

This script executes `lowmag_algorithm.py` for files under `low_mag_examples/`
and `medmag_algorithm.py` for files under `med_mag_examples/`.

It writes each algorithm JSON output into `benchmark_outputs/low_mag/` and
`benchmark_outputs/med_mag/`, and stores timing metrics in
`benchmark_outputs/benchmark_summary.json` and `benchmark_outputs/benchmark_summary.csv`.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_LOW_DIR = Path('low_mag_examples')
DEFAULT_MED_DIR = Path('med_mag_examples')
DEFAULT_OUTPUT_DIR = Path('benchmark_outputs')

SCRIPT_DIR = Path(__file__).resolve().parent


def discover_examples(example_dir: Path):
    return sorted([p for p in example_dir.iterdir() if p.is_file() and p.suffix.lower() == '.mrc'])


def run_process(script: Path, mrc_path: Path, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(script), str(mrc_path)]
    start = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True)
    elapsed = time.perf_counter() - start

    if process.returncode != 0:
        output_path.write_text(json.dumps({'error': process.stderr.strip()}, indent=2))
        return elapsed, False, process.stderr.strip()

    output_text = process.stdout.strip()
    if not output_text:
        output_path.write_text(json.dumps({'error': 'No output from algorithm'}, indent=2))
        return elapsed, False, 'No output from algorithm'

    output_path.write_text(output_text)
    return elapsed, True, None


def write_summary_json(summary: dict, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, indent=2))


def write_summary_csv(summary: dict, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for category in summary['categories']:
        for item in category['examples']:
            rows.append({
                'category': category['name'],
                'example_file': item['input_path'],
                'output_file': item['output_path'],
                'duration_seconds': item['duration_seconds'],
                'success': item['success'],
                'error': item.get('error', '')
            })

    with destination.open('w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['category', 'example_file', 'output_file', 'duration_seconds', 'success', 'error'])
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description='Benchmark low-mag and med-mag Ptolemy examples.')
    parser.add_argument('--low-dir', default=str(DEFAULT_LOW_DIR), help='Low-mag examples directory')
    parser.add_argument('--med-dir', default=str(DEFAULT_MED_DIR), help='Med-mag examples directory')
    parser.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR), help='Benchmark output directory')
    args = parser.parse_args()

    low_dir = Path(args.low_dir)
    med_dir = Path(args.med_dir)
    output_dir = Path(args.output_dir)

    low_script = SCRIPT_DIR / 'lowmag_algorithm.py'
    med_script = SCRIPT_DIR / 'medmag_algorithm.py'

    if not low_script.exists() or not med_script.exists():
        print('Error: Required algorithm scripts were not found in the current directory.', file=sys.stderr)
        sys.exit(1)

    low_examples = discover_examples(low_dir)
    med_examples = discover_examples(med_dir)

    summary = {
        'started_at': time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime()),
        'low_mag_dir': str(low_dir.resolve()),
        'med_mag_dir': str(med_dir.resolve()),
        'output_dir': str(output_dir.resolve()),
        'categories': [],
        'total_duration_seconds': None,
        'finished_at': None,
    }

    overall_start = time.perf_counter()

    categories = [
        {'name': 'low_mag', 'examples_dir': low_dir, 'script': low_script, 'output_subdir': output_dir / 'low_mag', 'examples': low_examples},
        {'name': 'med_mag', 'examples_dir': med_dir, 'script': med_script, 'output_subdir': output_dir / 'med_mag', 'examples': med_examples},
    ]

    for category in categories:
        results = []
        print(f'Running {category["name"]} benchmarks ({len(category["examples"])} files) ...')
        for mrc_path in category['examples']:
            print(f'  Processing {mrc_path.name}')
            output_path = category['output_subdir'] / f'{mrc_path.stem}.json'
            duration, success, error = run_process(category['script'], mrc_path, output_path)
            results.append({
                'input_path': str(mrc_path.resolve()),
                'output_path': str(output_path.resolve()),
                'duration_seconds': round(duration, 4),
                'success': success,
                'error': error,
            })
        summary['categories'].append({'name': category['name'], 'examples': results})

    overall_end = time.perf_counter()
    summary['total_duration_seconds'] = round(overall_end - overall_start, 4)
    summary['finished_at'] = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime())

    write_summary_json(summary, output_dir / 'benchmark_summary.json')
    write_summary_csv(summary, output_dir / 'benchmark_summary.csv')

    print(f'Benchmark complete. Summary written to {output_dir / "benchmark_summary.json"}')
    print(f'Total runtime: {summary["total_duration_seconds"]} seconds')


if __name__ == '__main__':
    main()
