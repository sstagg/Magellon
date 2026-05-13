#!/usr/bin/env python
"""
MeasureIce-style ice thickness estimator (Beer-Lambert).

For each pixel:

    t(px) = -T_eff * ln(I(px) / I_0)

where I_0 is a vacuum-reference intensity and T_eff is the effective
mean-free-path. Both depend on microscope configuration; see README for
typical values.

Three I_0 strategies are supported:

  --i0-mode percentile   I_0 = np.percentile(image, --i0-percentile)
                         (default; works without prior knowledge)
  --i0-mode roi          I_0 = mean over (x,y,w,h) crop given by --i0-roi
  --i0-mode reference    I_0 = mean of a reference vacuum MRC given by
                         --i0-reference

Writes:
  <stem>_thickness.npy   (float32 H×W, in nm)
  <stem>_thickness.png   heatmap overlay
  <stem>_thickness.json  per-image summary stats
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Defaults — single-scalar T_eff approximations to MeasureIce's per-microscope
# LUTs. Override via --t-eff at the CLI.
# ---------------------------------------------------------------------------
DEFAULT_T_EFF_NM = 395.0   # 300 kV, ~100 µm objective aperture
T_EFF_PRESETS = {
    "200kV": 320.0,
    "300kV": 395.0,
}


def load_mrc(path: str) -> np.ndarray:
    import mrcfile  # lazy
    with mrcfile.open(path, permissive=True) as m:
        data = np.asarray(m.data, dtype=np.float32)
    if data.ndim == 3 and data.shape[0] == 1:
        data = data[0]
    if data.ndim != 2:
        raise ValueError(f"expected 2D MRC, got shape {data.shape} at {path}")
    return data


def resolve_t_eff(t_eff: float | None, preset: str | None) -> float:
    if t_eff is not None:
        return float(t_eff)
    if preset:
        if preset not in T_EFF_PRESETS:
            raise ValueError(f"unknown T_eff preset {preset!r}; "
                             f"options: {list(T_EFF_PRESETS)}")
        return T_EFF_PRESETS[preset]
    return DEFAULT_T_EFF_NM


def compute_i0(
    img: np.ndarray,
    mode: str,
    *,
    percentile: float = 99.0,
    roi: Tuple[int, int, int, int] | None = None,
    reference_path: str | None = None,
) -> Tuple[float, dict]:
    """Resolve the vacuum-reference intensity I_0.

    Returns ``(I_0, info)`` where ``info`` records how the value was
    obtained so the per-image JSON can flag low-confidence I_0s.
    """
    if mode == "percentile":
        i0 = float(np.percentile(img, percentile))
        return i0, {"i0_mode": "percentile", "i0_percentile": percentile}

    if mode == "roi":
        if roi is None:
            raise ValueError("--i0-mode roi requires --i0-roi x,y,w,h")
        x, y, w, h = roi
        crop = img[y:y + h, x:x + w]
        if crop.size == 0:
            raise ValueError(f"ROI {roi} is outside image of shape {img.shape}")
        i0 = float(crop.mean())
        return i0, {
            "i0_mode": "roi",
            "i0_roi": [x, y, w, h],
            "i0_roi_std": float(crop.std()),
        }

    if mode == "reference":
        if not reference_path:
            raise ValueError("--i0-mode reference requires --i0-reference PATH")
        ref = load_mrc(reference_path)
        i0 = float(ref.mean())
        return i0, {
            "i0_mode": "reference",
            "i0_reference": os.path.abspath(reference_path),
            "i0_reference_std": float(ref.std()),
        }

    raise ValueError(f"unknown --i0-mode {mode!r}")


def compute_thickness(
    img: np.ndarray,
    i0: float,
    t_eff_nm: float,
    *,
    clip_saturation_percentile: float = 99.9,
) -> Tuple[np.ndarray, dict]:
    """Pixel-wise Beer-Lambert thickness in nm.

    Notes
    -----
    * Saturated pixels (above the 99.9th-percentile cap) are clipped to
      that cap to avoid the log-of-near-zero spike that would push the
      pixel's thickness to a runaway negative.
    * Pixels with I > I_0 (brighter than vacuum) get a NEGATIVE thickness;
      we clip those to 0 because they're either a vacuum-overlap region
      or a sensor artefact, not physical thickness.
    * Pixels with I <= 0 are masked out (set to NaN); the summary stats
      ignore them.
    """
    sat_cap = float(np.percentile(img, clip_saturation_percentile))
    work = np.minimum(img, sat_cap)

    safe = np.where(work > 0, work, np.nan)
    ratio = safe / i0
    # log(ratio); negative thickness clipped to 0.
    t = -t_eff_nm * np.log(np.clip(ratio, 1e-6, 1.0))
    t = np.clip(t, 0.0, None)
    t = np.where(np.isfinite(t), t, 0.0).astype(np.float32)

    summary = {
        "saturation_cap": sat_cap,
        "i0": float(i0),
        "t_eff_nm": float(t_eff_nm),
        "mean_t_nm": float(np.nanmean(t)),
        "median_t_nm": float(np.nanmedian(t)),
        "p5_t_nm": float(np.nanpercentile(t, 5)),
        "p95_t_nm": float(np.nanpercentile(t, 95)),
        "thin_frac": float((t < 30).mean()),
        "thick_frac": float((t > 100).mean()),
    }
    return t, summary


def save_outputs(
    path: str,
    img: np.ndarray,
    t: np.ndarray,
    summary: dict,
    *,
    output_dir: str | None = None,
    write_png: bool = True,
):
    stem = os.path.splitext(os.path.basename(path))[0]
    out_dir = output_dir or os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)

    np.save(os.path.join(out_dir, f"{stem}_thickness.npy"), t)
    with open(os.path.join(out_dir, f"{stem}_thickness.json"), "w") as f:
        json.dump(summary, f, indent=2)

    if write_png:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        # left: raw image
        lo, hi = np.percentile(img, [1, 99])
        axes[0].imshow(img, cmap='gray', vmin=lo, vmax=hi)
        axes[0].set_title(f"{stem}\nintensity")
        axes[0].axis('off')
        # right: thickness heatmap
        finite = t[np.isfinite(t)]
        vmax = float(np.percentile(finite, 99)) if finite.size else 100.0
        im = axes[1].imshow(t, cmap='viridis', vmin=0.0, vmax=vmax)
        axes[1].set_title(f"thickness (nm)\nmean={summary['mean_t_nm']:.1f} "
                          f"median={summary['median_t_nm']:.1f}")
        axes[1].axis('off')
        fig.colorbar(im, ax=axes[1], fraction=0.046)
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"{stem}_thickness.png"),
                    dpi=120, bbox_inches='tight')
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mrc_path')
    parser.add_argument('--t-eff', type=float, default=None,
                        help=f"Effective mean free path in nm "
                             f"(default {DEFAULT_T_EFF_NM} = 300 kV preset).")
    parser.add_argument('--preset', choices=list(T_EFF_PRESETS),
                        help="Microscope preset (overrides --t-eff if set).")
    parser.add_argument('--i0-mode', choices=['percentile', 'roi', 'reference'],
                        default='percentile')
    parser.add_argument('--i0-percentile', type=float, default=99.0,
                        help="Percentile of image intensities used as I_0 "
                             "in --i0-mode percentile (default 99).")
    parser.add_argument('--i0-roi', type=str, default=None,
                        help="x,y,w,h of vacuum region for --i0-mode roi.")
    parser.add_argument('--i0-reference', type=str, default=None,
                        help="Path to vacuum reference MRC for --i0-mode reference.")
    parser.add_argument('--output-dir', type=str, default=None)
    parser.add_argument('--no-png', action='store_true', help="Skip PNG output")
    args = parser.parse_args()

    if not os.path.exists(args.mrc_path):
        sys.stderr.write(f"file not found: {args.mrc_path}\n")
        sys.exit(1)

    roi = None
    if args.i0_roi:
        try:
            roi = tuple(int(x) for x in args.i0_roi.split(","))
            if len(roi) != 4:
                raise ValueError
        except ValueError:
            sys.stderr.write("--i0-roi expects x,y,w,h\n")
            sys.exit(1)

    t_eff = resolve_t_eff(args.t_eff, args.preset)
    img = load_mrc(args.mrc_path)
    i0, i0_info = compute_i0(
        img, args.i0_mode,
        percentile=args.i0_percentile,
        roi=roi,
        reference_path=args.i0_reference,
    )
    t, summary = compute_thickness(img, i0, t_eff)
    summary.update(i0_info)
    summary["image"] = os.path.abspath(args.mrc_path)
    summary["image_shape"] = list(img.shape)

    save_outputs(args.mrc_path, img, t, summary,
                 output_dir=args.output_dir, write_png=not args.no_png)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
