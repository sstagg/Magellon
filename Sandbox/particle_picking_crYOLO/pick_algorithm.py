#!/usr/bin/env python
"""
crYOLO Particle Picking Script
Runs SPHIRE-crYOLO's general pretrained model on a single MRC micrograph.

Usage:
    python pick_algorithm.py <path_to_mrc_file> [--weights PATH] [--threshold T]
                             [--gpu G] [--filament]

Outputs JSON to stdout with detected particles (center, radius, score) sorted
by score descending. Coordinates are in the ORIGINAL image's pixel space —
crYOLO writes original-coordinate STAR/CBOX files directly, so no upscaling
math is needed here.

Strategy mirrors the topaz wrapper: shell out to the crYOLO CLI in a temp
directory, then parse the output STAR file. Once an ONNX path is verified
this script can flip to in-process inference.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile


def _find_cryolo():
    """Locate `cryolo_predict.py` (crYOLO 1.x CLI entry) in the active env."""
    exe_dir = os.path.dirname(sys.executable)
    candidates_dirs = [
        exe_dir,
        os.path.join(exe_dir, 'Scripts' if os.name == 'nt' else 'bin'),
    ]
    for d in candidates_dirs:
        for name in ('cryolo_predict.py', 'cryolo_predict.exe', 'cryolo_predict'):
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which('cryolo_predict.py') or shutil.which('cryolo_predict')


def _default_weights():
    """Pick a *.h5 from weights/ if exactly one is present."""
    weights_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weights')
    if not os.path.isdir(weights_dir):
        return None
    h5s = [f for f in os.listdir(weights_dir) if f.lower().endswith('.h5')]
    return os.path.join(weights_dir, h5s[0]) if len(h5s) == 1 else None


def process_pick(mrc_path, weights=None, threshold=0.3, gpu=0, filament=False):
    """Run `cryolo_predict.py` and return parsed picks."""
    cryolo_exe = _find_cryolo()
    if cryolo_exe is None:
        raise RuntimeError(
            "`cryolo_predict.py` not found. Install crYOLO into the active "
            "Python environment (see crYOLO docs for the right TF version)."
        )

    weights = weights or _default_weights()
    if weights is None:
        raise RuntimeError(
            "No weights specified and weights/ does not contain a single .h5 "
            "general model. Pass --weights /path/to/gmodel_phosnet_*.h5."
        )

    mrc_path = os.path.abspath(mrc_path)
    if not os.path.exists(mrc_path):
        raise FileNotFoundError(f"MRC file not found: {mrc_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # crYOLO expects a directory of inputs; symlink (or copy on Windows)
        # the single MRC into a staging directory.
        input_dir = os.path.join(tmpdir, 'input')
        output_dir = os.path.join(tmpdir, 'output')
        os.makedirs(input_dir, exist_ok=True)

        staged = os.path.join(input_dir, os.path.basename(mrc_path))
        try:
            os.symlink(mrc_path, staged)
        except (OSError, NotImplementedError):
            shutil.copy2(mrc_path, staged)

        # Minimal config: most fields have working defaults for the general
        # model; box size is optional during prediction (crYOLO estimates it).
        # See https://cryolo.readthedocs.io/en/latest/tutorials/tutorial_overview.html
        config_path = os.path.join(tmpdir, 'config.json')
        _write_config(config_path)

        cmd = [
            cryolo_exe,
            '-c', config_path,
            '-w', weights,
            '-i', input_dir,
            '-o', output_dir,
            '-t', str(threshold),
            '-g', str(gpu),
        ]
        if filament:
            cmd.append('--filament')

        subprocess.run(cmd, check=True, capture_output=True, text=True)

        results = _parse_cbox_or_star(output_dir, os.path.basename(mrc_path))

    results.sort(key=lambda r: -r['score'])
    return results


def _write_config(path):
    """Emit a minimal crYOLO config — relies on the general model's defaults."""
    cfg = {
        "model": {
            "architecture": "PhosaurusNet",
            "input_size": 1024,
            "max_box_per_image": 1000,
            "norm": "STANDARD",
            "filter": [
                0.1,
                "filtered_tmp/"
            ],
        },
        "other": {
            "log_path": "logs/"
        }
    }
    with open(path, 'w') as f:
        json.dump(cfg, f)


def _parse_cbox_or_star(output_dir, micrograph_name):
    """
    crYOLO writes per-micrograph CBOX (preferred — has score + est. box size),
    STAR, and EMAN .box files. We prefer CBOX since it carries the per-particle
    confidence and the auto-estimated box size; fall back to STAR if absent.
    """
    stem = os.path.splitext(micrograph_name)[0]

    cbox_path = os.path.join(output_dir, 'CBOX', f'{stem}.cbox')
    if os.path.exists(cbox_path):
        return _parse_cbox(cbox_path)

    star_path = os.path.join(output_dir, 'STAR', f'{stem}.star')
    if os.path.exists(star_path):
        return _parse_star(star_path)

    raise RuntimeError(
        f"No CBOX or STAR produced for {micrograph_name} under {output_dir}"
    )


def _parse_cbox(path):
    """
    CBOX format (crYOLO 1.7+) is a STAR-style table. Columns of interest:
        _CoordinateX  _CoordinateY  _Width  _Height  _Confidence  _EstWidth (opt)
    Coordinates are the lower-left corner of the box in original image pixels;
    we convert to center coordinates.
    """
    return _parse_star_like(path, prefer_est_width=True)


def _parse_star(path):
    """
    crYOLO's STAR output uses:
        _rlnCoordinateX  _rlnCoordinateY  _rlnAutopickFigureOfMerit
    Coordinates are particle centers; STAR lacks per-particle width so we
    return a placeholder radius (caller can override via plugin config).
    """
    return _parse_star_like(path, prefer_est_width=False)


def _parse_star_like(path, prefer_est_width):
    """Tolerant parser for both CBOX and STAR — locates header columns by name."""
    columns = {}
    rows = []
    in_loop = False
    parsing_header = False
    seen_data = False

    with open(path) as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if s.startswith('data_'):
                seen_data = True
                in_loop = False
                parsing_header = False
                continue
            if not seen_data:
                continue
            if s.startswith('loop_'):
                in_loop = True
                parsing_header = True
                columns = {}
                continue
            if parsing_header and s.startswith('_'):
                col = s.split()[0]
                columns[col] = len(columns)
                continue
            if in_loop and not s.startswith('_'):
                parsing_header = False
                parts = s.split()
                if len(parts) >= len(columns):
                    rows.append(parts)

    def col(*names):
        for n in names:
            if n in columns:
                return columns[n]
        return None

    x_idx = col('_CoordinateX', '_rlnCoordinateX')
    y_idx = col('_CoordinateY', '_rlnCoordinateY')
    w_idx = col('_Width')
    h_idx = col('_Height')
    estw_idx = col('_EstWidth') if prefer_est_width else None
    score_idx = col('_Confidence', '_rlnAutopickFigureOfMerit')

    if x_idx is None or y_idx is None:
        raise RuntimeError(f"Could not find coordinate columns in {path}; "
                           f"have columns: {list(columns)}")

    results = []
    for parts in rows:
        try:
            x = float(parts[x_idx])
            y = float(parts[y_idx])
        except (ValueError, IndexError):
            continue

        # CBOX: lower-left corner. STAR: centre. Detect via presence of width.
        if w_idx is not None and h_idx is not None:
            try:
                w = float(parts[w_idx])
                h = float(parts[h_idx])
            except (ValueError, IndexError):
                w = h = 0.0
            cx = int(round(x + w / 2.0))
            cy = int(round(y + h / 2.0))
            radius = int(round(max(w, h) / 2.0))
            if estw_idx is not None:
                try:
                    radius = int(round(float(parts[estw_idx]) / 2.0))
                except (ValueError, IndexError):
                    pass
        else:
            cx = int(round(x))
            cy = int(round(y))
            radius = 0  # STAR doesn't carry width; caller can override

        score = 1.0
        if score_idx is not None:
            try:
                score = float(parts[score_idx])
            except (ValueError, IndexError):
                pass

        results.append({
            'center': [cx, cy],
            'radius': radius,
            'score': score,
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="crYOLO particle picker wrapper")
    parser.add_argument('mrc_path', help="Path to the input MRC micrograph")
    parser.add_argument('--weights', default=None,
                        help="Path to the crYOLO .h5 general model (auto-picked "
                             "from weights/ if exactly one .h5 is present)")
    parser.add_argument('--threshold', type=float, default=0.3,
                        help="Confidence threshold in [0,1] (default 0.3)")
    parser.add_argument('--gpu', type=int, default=0,
                        help="GPU index (-1 for CPU; default 0)")
    parser.add_argument('--filament', action='store_true',
                        help="Filament-mode picking (off by default)")
    args = parser.parse_args()

    try:
        results = process_pick(
            args.mrc_path,
            weights=args.weights,
            threshold=args.threshold,
            gpu=args.gpu,
            filament=args.filament,
        )
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"cryolo_predict failed: {e}\n")
        if e.stderr:
            sys.stderr.write(e.stderr)
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"Error processing image: {e}\n")
        sys.exit(1)

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
