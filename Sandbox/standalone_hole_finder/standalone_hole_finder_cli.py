#!/usr/bin/env python
"""
Standalone Hole Finder - Command Line Interface
Processes MRC images to detect holes using edge-based or template correlation methods.

Usage:
    python standalone_hole_finder_cli.py <method> <image_path> [options]

Methods:
    edge     - Edge-based hole finder (requires template file)
    template - Direct template correlation hole finder (requires template file)

Examples:
    # Edge-based hole finder
    python standalone_hole_finder_cli.py edge image.mrc --template hole_template.mrc

    # Template correlation hole finder
    python standalone_hole_finder_cli.py template image.mrc --template hole_template.mrc

Output: JSON results printed to stdout
"""

import argparse
import json
import sys
from pathlib import Path

# Add current directory to the import path so package modules can be imported directly.
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))

from mrc_io import read_mrc
from pipeline import run_edge_hole_finder, run_template_hole_finder


def convert_holes_to_dict(holes):
    """Convert hole objects to dictionaries for JSON serialization."""
    if holes is None:
        return None

    result = []
    for hole in holes:
        hole_dict = {
            'center': hole.center,
            'stats': hole.stats,
        }
        result.append(hole_dict)
    return result


def convert_blobs_to_dict(blobs):
    """Convert blob objects to dictionaries for JSON serialization."""
    if blobs is None:
        return None

    result = []
    for blob in blobs:
        blob_dict = {
            'center': blob.center,
            'size': blob.size,
            'mean': blob.mean,
            'stddev': blob.stddev,
            'roundness': blob.roundness,
            'maximum_position': blob.maximum_position,
            'label_index': blob.label_index,
        }
        result.append(blob_dict)
    return result


def convert_lattice_to_dict(lattice):
    """Convert lattice object to dictionary for JSON serialization."""
    if lattice is None:
        return None

    points = None
    if hasattr(lattice, 'points'):
        pts = lattice.points
        if hasattr(pts, 'tolist'):
            points = pts.tolist()
        else:
            points = list(pts)
    elif isinstance(lattice, (list, tuple)):
        points = list(lattice)

    spacing = getattr(lattice, 'spacing', None)
    angle = getattr(lattice, 'angle', None)
    return {
        'spacing': spacing,
        'angle': angle,
        'points': points,
    }


def process_results(results):
    """Convert pipeline results to JSON-serializable format."""
    return {
        'holes': convert_holes_to_dict(results.get('holes')),
        'good_holes': convert_holes_to_dict(results.get('good_holes')),
        'convolved_holes': convert_holes_to_dict(results.get('convolved_holes')),
        'sampled_holes': convert_holes_to_dict(results.get('sampled_holes')),
        'blobs': convert_blobs_to_dict(results.get('blobs')),
        'lattice': convert_lattice_to_dict(results.get('lattice')),
        'correlation_stats': {
            'correlation_shape': results.get('correlation').shape if results.get('correlation') is not None else None,
            'threshold_mask_shape': results.get('threshold_mask').shape if results.get('threshold_mask') is not None else None,
        },
        'hole_count': len(results.get('holes')) if results.get('holes') else 0,
        'good_hole_count': len(results.get('good_holes')) if results.get('good_holes') else 0,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Standalone Hole Finder - Detect holes in MRC images',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('method', choices=['edge', 'template'],
                       help='Hole finding method')
    parser.add_argument('image_path', nargs='?', help='Path to input MRC image file (or use --input)')
    parser.add_argument('--input', dest='input_path',
                       help='Path to input MRC image file')
    parser.add_argument('--output',
                       help='Path to output JSON file (default: print to stdout)')

    # Template options
    parser.add_argument('--template', required=True,
                       help='Path to hole template MRC file')
    parser.add_argument('--template-diameter', type=float, default=40.0,
                       help='Template diameter in pixels (default: 40.0)')

    # Common processing options
    parser.add_argument('--lattice-spacing', type=float, default=100.0,
                       help='Expected lattice spacing in pixels (default: 100.0)')
    parser.add_argument('--lattice-tolerance', type=float, default=0.1,
                       help='Lattice fitting tolerance (default: 0.1)')

    # Edge-based specific options
    parser.add_argument('--edge-lpsig', type=float, default=3.0,
                       help='Edge detection low-pass sigma (default: 3.0)')
    parser.add_argument('--edge-thresh', type=float, default=10.0,
                       help='Edge detection threshold (default: 10.0)')

    # Correlation options
    parser.add_argument('--correlation-type', choices=['cross', 'phase'], default='cross',
                       help='Correlation type (default: cross)')
    parser.add_argument('--correlation-filter-sigma', type=float, default=2.0,
                       help='Correlation filter sigma (default: 2.0)')

    # Thresholding options
    parser.add_argument('--threshold-value', type=float, default=3.5,
                       help='Threshold value (default: 3.5)')
    parser.add_argument('--threshold-method', default='Threshold = mean + A * stdev',
                       help='Threshold method (default: "Threshold = mean + A * stdev")')

    # Blob detection options
    parser.add_argument('--border', type=int, default=20,
                       help='Border exclusion in pixels (default: 20)')
    parser.add_argument('--max-blobs', type=int, default=100,
                       help='Maximum number of blobs to detect (default: 100)')
    parser.add_argument('--max-blob-size', type=int, default=5000,
                       help='Maximum blob size (default: 5000)')
    parser.add_argument('--min-blob-size', type=int, default=30,
                       help='Minimum blob size (default: 30)')
    parser.add_argument('--min-blob-roundness', type=float, default=0.1,
                       help='Minimum blob roundness (default: 0.1)')

    # Statistics options
    parser.add_argument('--stats-radius', type=int, default=20,
                       help='Statistics calculation radius (default: 20)')

    # Ice filtering options
    parser.add_argument('--ice-i0', type=float,
                       help='Ice filtering I0 parameter (optional)')
    parser.add_argument('--ice-tmin', type=float, default=0.0,
                       help='Ice filtering T min (default: 0.0)')
    parser.add_argument('--ice-tmax', type=float, default=0.1,
                       help='Ice filtering T max (default: 0.1)')

    args = parser.parse_args()

    # Validate inputs
    image_arg = args.image_path or args.input_path
    if not image_arg:
        print("Error: Input image is required. Use positional image_path or --input.", file=sys.stderr)
        sys.exit(1)

    image_path = Path(image_arg)
    template_path = Path(args.template)

    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    if not template_path.exists():
        print(f"Error: Template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Load image
    try:
        image = read_mrc(str(image_path))
        print(f"Loaded image: {image.shape}", file=sys.stderr)
    except Exception as e:
        print(f"Error loading image: {e}", file=sys.stderr)
        sys.exit(1)

    # Run appropriate method
    try:
        if args.method == 'edge':
            print("Running edge-based hole finder...", file=sys.stderr)
            results = run_edge_hole_finder(
                image=image,
                template_filename=str(template_path),
                template_diameter=args.template_diameter,
                lattice_spacing=args.lattice_spacing,
                lattice_tolerance=args.lattice_tolerance,
                edge_lpsig=args.edge_lpsig,
                edge_thresh=args.edge_thresh,
                correlation_type=args.correlation_type,
                correlation_filter_sigma=args.correlation_filter_sigma,
                threshold_value=args.threshold_value,
                threshold_method=args.threshold_method,
                border=args.border,
                max_blobs=args.max_blobs,
                max_blob_size=args.max_blob_size,
                min_blob_size=args.min_blob_size,
                min_blob_roundness=args.min_blob_roundness,
                stats_radius=args.stats_radius,
                ice_i0=args.ice_i0,
                ice_tmin=args.ice_tmin,
                ice_tmax=args.ice_tmax,
            )
        else:  # template
            print("Running template correlation hole finder...", file=sys.stderr)
            results = run_template_hole_finder(
                image=image,
                template_filename=str(template_path),
                template_diameter=args.template_diameter,
                lattice_spacing=args.lattice_spacing,
                lattice_tolerance=args.lattice_tolerance,
                correlation_type=args.correlation_type,
                correlation_filter_sigma=args.correlation_filter_sigma,
                threshold_value=args.threshold_value,
                threshold_method=args.threshold_method,
                border=args.border,
                max_blobs=args.max_blobs,
                max_blob_size=args.max_blob_size,
                min_blob_size=args.min_blob_size,
                min_blob_roundness=args.min_blob_roundness,
                stats_radius=args.stats_radius,
                ice_i0=args.ice_i0,
                ice_tmin=args.ice_tmin,
                ice_tmax=args.ice_tmax,
            )

        # Process and output results
        processed_results = process_results(results)
        output_json = json.dumps(processed_results, indent=2)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_json)
            print(f"Results written to {output_path}", file=sys.stderr)
        else:
            print(output_json)

    except Exception as e:
        print(f"Error processing image: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()