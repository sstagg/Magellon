#!/usr/bin/env python
"""Run benchmark timing for standalone hole finder examples.

This script executes the standalone hole finder CLI over one or more example
MRC files and records per-example output plus a summary report.
"""

import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_EXAMPLE_DIR = Path('.')
DEFAULT_OUTPUT_DIR = Path('benchmark_outputs')
DEFAULT_TEMPLATE = Path('origTemplate1.mrc')
DEFAULT_METHODS = ['template']


def discover_examples(example_dir: Path):
    """Discover example subdirectories inside the example root."""
    return sorted([p for p in example_dir.iterdir() if p.is_dir()])


def discover_example_inputs(example_dir: Path):
    """Discover input MRC files for a single example directory."""
    input_dir = example_dir / 'inputfile'
    if input_dir.exists() and input_dir.is_dir():
        return sorted(input_dir.glob('*.mrc'))

    return sorted(example_dir.glob('*.mrc'))


def discover_example_templates(example_dir: Path):
    """Discover template MRC files for a single example directory."""
    template_dir = example_dir / 'templates'
    if template_dir.exists() and template_dir.is_dir():
        return sorted(template_dir.glob('*.mrc'))

    return []


def run_process(script: Path, method: str, template: Path, mrc_path: Path, output_path: Path, extra_args=None):
    """Run the hole finder CLI for a single example and return timing/results."""
    if extra_args is None:
        extra_args = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(script), method, str(mrc_path), '--template', str(template), '--output', str(output_path)]
    command.extend(extra_args)

    start = time.perf_counter()
    result = subprocess.run(command, capture_output=True, text=True)
    duration = time.perf_counter() - start

    return {
        'method': method,
        'input_path': str(mrc_path.resolve()),
        'output_path': str(output_path.resolve()),
        'duration_seconds': duration,
        'returncode': result.returncode,
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'success': result.returncode == 0,
        'error': None if result.returncode == 0 else result.stderr.strip() or result.stdout.strip(),
    }


def write_summary_json(summary: dict, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2))


def write_summary_csv(summary: dict, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        'method',
        'example_name',
        'example_file',
        'template_file',
        'output_file',
        'duration_seconds',
        'success',
        'error',
    ]

    with output_path.open('w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for category in summary.get('methods', []):
            for item in category.get('examples', []):
                writer.writerow({
                    'method': category['name'],
                    'example_name': item.get('example_name', ''),
                    'example_file': item['input_path'],
                    'template_file': item.get('template_path', ''),
                    'output_file': item['output_path'],
                    'duration_seconds': item['duration_seconds'],
                    'success': item['success'],
                    'error': item.get('error', ''),
                })


def parse_args():
    parser = argparse.ArgumentParser(
        description='Benchmark standalone hole finder examples.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument('--example-dir', type=Path, default=DEFAULT_EXAMPLE_DIR,
                        help='Root directory containing example subdirectories')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR,
                        help='Directory for benchmark outputs and summary files')
    parser.add_argument('--template', type=Path, default=DEFAULT_TEMPLATE,
                        help='Fallback hole template MRC file when example-specific template is absent')
    parser.add_argument('--methods', nargs='+', choices=['template', 'edge'], default=DEFAULT_METHODS,
                        help='Hole finder methods to benchmark')
    parser.add_argument('--cli-script', type=Path, default=Path('standalone_hole_finder_cli.py'),
                        help='Path to the standalone hole finder CLI script')
    parser.add_argument('--extra-args', nargs=argparse.REMAINDER,
                        help='Additional arguments to pass to the CLI after --')

    return parser.parse_args()


def main():
    args = parse_args()

    example_dir = args.example_dir
    output_dir = args.output_dir
    template_path = args.template
    cli_script = args.cli_script
    methods = args.methods
    extra_args = args.extra_args or []

    if not example_dir.exists():
        print(f'Error: example directory not found: {example_dir}', file=sys.stderr)
        sys.exit(1)

    if not cli_script.exists():
        print(f'Error: CLI script not found: {cli_script}', file=sys.stderr)
        sys.exit(1)

    if not template_path.exists():
        print(f'Error: fallback template file not found: {template_path}', file=sys.stderr)
        sys.exit(1)

    examples = discover_examples(example_dir)
    if not examples:
        print(f'No example subdirectories found in {example_dir}', file=sys.stderr)
        sys.exit(1)

    summary = {
        'benchmark_directory': str(output_dir.resolve()),
        'fallback_template': str(template_path.resolve()),
        'methods': [],
    }

    for method in methods:
        method_results = []
        method_output_dir = output_dir / method
        method_output_dir.mkdir(parents=True, exist_ok=True)

        for example_dir in examples:
            example_name = example_dir.name
            input_paths = discover_example_inputs(example_dir)
            template_paths = discover_example_templates(example_dir) or [template_path]

            if not input_paths:
                print(f'No input files found for example {example_name}, skipping', file=sys.stderr)
                continue

            if not template_paths:
                print(f'No templates found for example {example_name} and no fallback template provided, skipping', file=sys.stderr)
                continue

            for input_path in input_paths:
                for template_file in template_paths:
                    output_path = method_output_dir / example_name / f'{input_path.stem}__{template_file.stem}.json'
                    print(f'Benchmarking {method} on {example_name}/{input_path.name} using template {template_file.name} ...')
                    result = run_process(cli_script, method, template_file, input_path, output_path, extra_args=extra_args)
                    result['example_name'] = example_name
                    result['template_path'] = str(template_file.resolve())
                    method_results.append(result)
                    if result['success']:
                        print(f'  completed in {result["duration_seconds"]:.3f}s')
                    else:
                        print(f'  failed: {result["error"]}')

        summary['methods'].append({
            'name': method,
            'examples': method_results,
        })

    write_summary_json(summary, output_dir / 'benchmark_summary.json')
    write_summary_csv(summary, output_dir / 'benchmark_summary.csv')

    print(f'Benchmark complete. Outputs written to {output_dir.resolve()}')
    print(f'  JSON summary: {output_dir / "benchmark_summary.json"}')
    print(f'  CSV summary:  {output_dir / "benchmark_summary.csv"}')


if __name__ == '__main__':
    main()
