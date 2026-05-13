#!/usr/bin/env python
"""
Batch ice-thickness analyser.

Runs measure_thickness on every .mrc in an input directory, accumulates
per-image summary stats, and writes:

  summary.csv     one row per image
  quality.txt     overall I_0 stability + distribution sanity checks

The "quality" notes are the headline outputs — they answer:

  * Is I_0 stable across the dataset? (sigma/mean ratio should be < ~10%
    for uniformly illuminated images; bigger spreads suggest beam drift
    or saturated frames messing up the percentile fallback.)
  * Is the thickness distribution physically plausible? (median ice
    thickness should fall in 20-150 nm for usable cryo grids; anything
    consistently > 300 nm or < 10 nm hints at I_0 miscalibration.)
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import numpy as np

from measure_thickness import (
    DEFAULT_APERTURE_MRAD,
    DEFAULT_LUT_PATH,
    compute_i0,
    compute_thickness,
    load_lut,
    load_mrc,
    resolve_t_eff,
    save_outputs,
)

SKIP_PATTERNS = ("diagnostic_",)
# MeasureIce's published valid range is roughly hole-preview to overview mag.
# Atlas (>500 A/px) has no vacuum reference; high-mag exposures (<5 A/px) are
# entirely inside ice with no vacuum in the frame either.
DEFAULT_MIN_APIX = 5.0
DEFAULT_MAX_APIX = 500.0


def _read_pixel_size_A(path: str) -> float | None:
    """Return MRC voxel size in Angstroms, or None if unset."""
    import mrcfile
    with mrcfile.open(path, permissive=True, header_only=True) as m:
        vx = float(m.voxel_size.x)
    return vx if vx > 0 else None


def iter_mrcs(input_dir: str):
    for name in sorted(os.listdir(input_dir)):
        if not name.lower().endswith('.mrc'):
            continue
        if any(name.startswith(p) for p in SKIP_PATTERNS):
            continue
        yield os.path.join(input_dir, name)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input_dir')
    parser.add_argument('--output-dir', default='analysis_outputs')
    parser.add_argument('--lut', type=str, default=DEFAULT_LUT_PATH,
                        help="Path to MeasureIce HDF5 LUT. Pass '' to use scalar.")
    parser.add_argument('--aperture-mrad', type=float, default=DEFAULT_APERTURE_MRAD)
    parser.add_argument('--t-eff', type=float, default=None,
                        help="Scalar T_eff (only used if --lut '' is passed).")
    parser.add_argument('--preset', choices=['200kV', '300kV'], default='300kV')
    parser.add_argument('--i0-mode', choices=['percentile', 'roi', 'reference'],
                        default='percentile')
    parser.add_argument('--i0-percentile', type=float, default=99.9)
    parser.add_argument('--saturation-percentile', type=float, default=99.99)
    parser.add_argument('--i0-roi', type=str, default=None)
    parser.add_argument('--i0-reference', type=str, default=None)
    parser.add_argument('--min-apix', type=float, default=DEFAULT_MIN_APIX,
                        help=f"Skip MRCs with pixel size < this (A/px). "
                             f"Default {DEFAULT_MIN_APIX} skips single-particle "
                             f"exposures where there is no vacuum in frame.")
    parser.add_argument('--max-apix', type=float, default=DEFAULT_MAX_APIX,
                        help=f"Skip MRCs with pixel size > this (A/px). "
                             f"Default {DEFAULT_MAX_APIX} skips atlas-scale frames.")
    parser.add_argument('--limit', type=int, default=None,
                        help="Process only the first N MRCs (debug helper).")
    parser.add_argument('--no-png', action='store_true',
                        help="Skip per-image PNG output (much faster on large batches).")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        sys.stderr.write(f"input dir not found: {args.input_dir}\n")
        sys.exit(1)

    roi = None
    if args.i0_roi:
        roi = tuple(int(x) for x in args.i0_roi.split(","))

    use_lut = bool(args.lut) and os.path.exists(args.lut)
    if args.lut and not os.path.exists(args.lut):
        sys.stderr.write(f"WARN: LUT not found at {args.lut!r}; "
                         f"falling back to scalar T_eff.\n")
    if use_lut:
        lut_interp, lut_info = load_lut(args.lut, args.aperture_mrad)
        t_eff = None
        calibration_desc = (f"LUT={os.path.basename(args.lut)} @ "
                            f"{lut_info['lut_aperture_mrad']} mrad "
                            f"(lambda={lut_info['lut_lambda_nm']:.0f} nm)")
    else:
        lut_interp, lut_info = None, {}
        t_eff = resolve_t_eff(args.t_eff, args.preset)
        calibration_desc = f"scalar T_eff={t_eff} nm"

    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    t0 = time.perf_counter()
    all_files = list(iter_mrcs(args.input_dir))
    # Pixel-size gate
    in_regime, skipped = [], []
    for p in all_files:
        apix = _read_pixel_size_A(p)
        if apix is None or args.min_apix <= apix <= args.max_apix:
            in_regime.append((p, apix))
        else:
            skipped.append((p, apix))
    files = in_regime
    if args.limit:
        files = files[:args.limit]

    print(f"Found {len(all_files)} MRC(s); kept {len(files)} in regime "
          f"({args.min_apix}-{args.max_apix} A/px), skipped {len(skipped)}.")
    print(f"Calibration: {calibration_desc}, I0_mode={args.i0_mode}")
    print(f"Per-image PNGs: {'OFF' if args.no_png else 'ON'}")
    print()

    for idx, (path, apix) in enumerate(files, 1):
        try:
            img = load_mrc(path)
            i0, i0_info = compute_i0(
                img, args.i0_mode,
                percentile=args.i0_percentile,
                roi=roi,
                reference_path=args.i0_reference,
            )
            if lut_interp is not None:
                t, summary = compute_thickness(
                    img, i0, lut_interp=lut_interp,
                    clip_saturation_percentile=args.saturation_percentile,
                )
                summary.update(lut_info)
            else:
                t, summary = compute_thickness(
                    img, i0, t_eff_nm=t_eff,
                    clip_saturation_percentile=args.saturation_percentile,
                )
            summary.update(i0_info)
            summary['image'] = os.path.basename(path)
            summary['image_shape'] = list(img.shape)
            summary['pixel_size_A'] = apix

            save_outputs(path, img, t, summary,
                         output_dir=out_dir, write_png=not args.no_png)
            rows.append(summary)
            print(f"[{idx:>3}/{len(files)}] {os.path.basename(path):<40s}  "
                  f"apix={apix:6.1f}A  I0={i0:8.1f}  "
                  f"mean_t={summary['mean_t_nm']:6.1f}nm  "
                  f"med_t={summary['median_t_nm']:6.1f}nm")
        except Exception as e:
            sys.stderr.write(f"[{idx}/{len(files)}] {os.path.basename(path)} FAILED: {e}\n")
            rows.append({'image': os.path.basename(path), 'error': str(e)})

    elapsed = time.perf_counter() - t0
    print()
    print(f"Done. {len(rows)} processed in {elapsed:.1f}s "
          f"({elapsed/max(1, len(rows)):.2f}s/image)")

    # --- Persist CSV ---
    columns = ['image', 'pixel_size_A', 'method', 'lut_aperture_mrad',
               'lut_lambda_nm', 't_eff_nm', 'i0', 'i0_mode', 'i0_percentile',
               'mean_t_nm', 'median_t_nm', 'p5_t_nm', 'p95_t_nm',
               'thin_frac', 'thick_frac', 'saturation_cap', 'image_shape',
               'error']
    csv_path = os.path.join(out_dir, 'summary.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    # --- Quality notes ---
    ok = [r for r in rows if 'error' not in r]
    if not ok:
        print("All images failed — no quality summary.")
        return

    i0s = np.array([r['i0'] for r in ok], dtype=np.float64)
    meds = np.array([r['median_t_nm'] for r in ok], dtype=np.float64)
    means = np.array([r['mean_t_nm'] for r in ok], dtype=np.float64)
    thin = np.array([r['thin_frac'] for r in ok], dtype=np.float64)
    thick = np.array([r['thick_frac'] for r in ok], dtype=np.float64)

    notes = []
    notes.append(f"Images processed       : {len(ok)} / {len(rows)}")
    notes.append(f"Elapsed                : {elapsed:.1f}s")
    notes.append("")
    notes.append("--- I_0 stability ---")
    notes.append(f"  I_0 mean / median    : {i0s.mean():.2f} / {np.median(i0s):.2f}")
    notes.append(f"  I_0 sigma (CV)       : {i0s.std():.2f}  "
                 f"({100*i0s.std()/max(i0s.mean(), 1e-6):.1f}% of mean)")
    cv = i0s.std() / max(i0s.mean(), 1e-6)
    if cv < 0.05:
        notes.append("  -> EXCELLENT: I_0 within 5% across the whole dataset.")
    elif cv < 0.15:
        notes.append("  -> OK: I_0 varies <15%; thickness comparisons within this dataset are valid.")
    else:
        notes.append("  -> WARN: I_0 varies >15% — beam drift, saturation, "
                     "or percentile fallback failing. Use ROI/reference mode.")

    notes.append("")
    notes.append("--- Thickness distribution ---")
    notes.append(f"  median(median_t_nm)  : {np.median(meds):.1f} nm")
    notes.append(f"  median(mean_t_nm)    : {np.median(means):.1f} nm")
    notes.append(f"  thin_frac median     : {np.median(thin)*100:.1f}%  (pixels < 30 nm)")
    notes.append(f"  thick_frac median    : {np.median(thick)*100:.1f}%  (pixels > 100 nm)")
    if 20.0 <= np.median(meds) <= 200.0:
        notes.append("  -> Median thickness in physically-plausible range (20-200 nm).")
    elif np.median(meds) < 20.0:
        notes.append("  -> WARN: median thickness < 20 nm — I_0 likely BELOW true vacuum.")
    else:
        notes.append("  -> WARN: median thickness > 200 nm — I_0 likely ABOVE true vacuum, "
                     "or the dataset really is over-iced (no good targets).")

    notes.append("")
    notes.append("--- Outliers (top 5 thickest) ---")
    order = np.argsort(meds)[::-1]
    for k in order[:5]:
        r = ok[k]
        notes.append(f"  {r['image']:<40s}  mean_t={r['mean_t_nm']:7.1f}nm  I0={r['i0']:7.2f}")

    notes.append("")
    notes.append("--- Outliers (top 5 thinnest) ---")
    for k in order[-5:]:
        r = ok[k]
        notes.append(f"  {r['image']:<40s}  mean_t={r['mean_t_nm']:7.1f}nm  I0={r['i0']:7.2f}")

    quality_path = os.path.join(out_dir, 'quality.txt')
    with open(quality_path, 'w') as f:
        f.write('\n'.join(notes) + '\n')

    print()
    print('\n'.join(notes))
    print()
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {quality_path}")


if __name__ == "__main__":
    main()
