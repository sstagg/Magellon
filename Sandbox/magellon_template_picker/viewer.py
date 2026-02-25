#!/usr/bin/env python
"""
Interactive threshold viewer for Magellon template picker.
"""

from __future__ import annotations

import argparse
import glob
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
from matplotlib.patches import Circle

try:
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider
except Exception as exc:  # pragma: no cover - GUI import error path
    plt = None
    Slider = None
    _mpl_import_error = exc
else:
    _mpl_import_error = None

try:
    import mrcfile
except Exception as exc:  # pragma: no cover - import error path
    mrcfile = None
    _mrc_import_error = exc
else:
    _mrc_import_error = None

try:
    from .picker import pick_particles
    from .picker import _extract_particles_from_map
    from .picker import _remove_border_particles
    from .picker import _merge_particles
except ImportError:
    from picker import pick_particles
    from picker import _extract_particles_from_map
    from picker import _remove_border_particles
    from picker import _merge_particles


def _require_mrcfile() -> None:
    if mrcfile is None:
        raise RuntimeError(
            "mrcfile is required. Install with: pip install mrcfile "
            f"(import error: {_mrc_import_error})"
        )


def _require_matplotlib() -> None:
    if plt is None or Slider is None:
        raise RuntimeError(
            "matplotlib is required for interactive viewer. Install with: pip install matplotlib "
            f"(import error: {_mpl_import_error})"
        )


def _read_mrc(path: str) -> np.ndarray:
    _require_mrcfile()
    with mrcfile.open(path, permissive=True) as mrc:
        data = np.asarray(mrc.data, dtype=np.float32)
    if data.ndim == 3:
        data = data[0]
    if data.ndim != 2:
        raise ValueError(f"Expected 2D MRC data in {path}, got shape {data.shape}")
    return data


def _parse_angle_range(text: str) -> Tuple[float, float, float]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise ValueError(f"Invalid angle range '{text}', expected start,end,step")
    start, end, step = map(float, parts)
    if step <= 0:
        raise ValueError("angle step must be > 0")
    return start, end, step


def _expand_templates(patterns: Sequence[str]) -> List[str]:
    paths: List[str] = []
    for pattern in patterns:
        matched = sorted(glob.glob(pattern))
        if matched:
            paths.extend(matched)
        else:
            paths.append(pattern)
    unique = []
    seen = set()
    for path in paths:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _normalized_float(array: np.ndarray) -> np.ndarray:
    data = np.asarray(array, dtype=np.float32)
    finite = np.isfinite(data)
    if not finite.any():
        return np.zeros(data.shape, dtype=np.float32)
    valid = data[finite]
    lo = float(np.percentile(valid, 1.0))
    hi = float(np.percentile(valid, 99.0))
    if hi <= lo:
        lo = float(valid.min())
        hi = float(valid.max())
    if hi <= lo:
        return np.zeros(data.shape, dtype=np.float32)
    clipped = np.clip(data, lo, hi)
    return (clipped - lo) / (hi - lo)


def _threshold_particles(
    base_result: Dict[str, Any],
    threshold: float,
    radius_pixels: float,
    max_peaks: int,
    overlap_multiplier: float,
    max_blob_size_multiplier: float,
    min_blob_roundness: float,
    peak_position: str,
    image_shape: Tuple[int, int],
) -> List[Dict[str, Any]]:
    particles_all: List[Dict[str, Any]] = []
    for item in base_result["template_results"]:
        template_index = int(item["template_index"])
        particles = _extract_particles_from_map(
            score_map=item["score_map"],
            angle_map=item["angle_map"],
            template_index=template_index,
            threshold=float(threshold),
            radius_pixels=radius_pixels,
            max_peaks=max_peaks,
            overlap_multiplier=overlap_multiplier,
            max_blob_size_multiplier=max_blob_size_multiplier,
            min_blob_roundness=min_blob_roundness,
            peak_position=peak_position,
        )
        particles = _remove_border_particles(
            particles=particles,
            diameter_pixels=radius_pixels * 2.0,
            image_width=image_shape[1],
            image_height=image_shape[0],
        )
        particles_all.extend(particles)
    return _merge_particles(
        particles=particles_all,
        radius_pixels=radius_pixels,
        overlap_multiplier=overlap_multiplier,
        max_peaks=max_peaks,
        max_threshold=None,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive CC threshold viewer")
    parser.add_argument("--image", required=True, help="Input micrograph MRC path")
    parser.add_argument(
        "--template",
        action="append",
        required=True,
        dest="templates",
        help="Template MRC path or glob; repeat for multiple entries",
    )
    parser.add_argument("--image-apix", type=float, required=True, help="Input image pixel size (A/pix)")
    parser.add_argument("--template-apix", type=float, required=True, help="Template pixel size (A/pix)")
    parser.add_argument("--invert-templates", action="store_true", help="Invert template contrast")
    parser.add_argument("--bin", type=int, default=1, help="Power-of-two image binning factor")
    parser.add_argument("--diameter", type=float, required=True, help="Particle diameter (A)")
    parser.add_argument("--initial-threshold", type=float, default=0.35, help="Initial CC threshold")
    parser.add_argument("--max-peaks", type=int, default=500, help="Maximum number of final particles")
    parser.add_argument("--overlap-multiplier", type=float, default=1.0, help="Peak overlap multiplier")
    parser.add_argument("--max-blob-size-multiplier", type=float, default=1.0, help="Blob size multiplier")
    parser.add_argument("--min-blob-roundness", type=float, default=0.0, help="Minimum blob roundness")
    parser.add_argument("--peak-position", choices=["maximum", "center"], default="maximum")
    parser.add_argument("--angle-range", action="append", default=[], help="start,end,step")
    parser.add_argument("--lowpass-resolution", type=float, default=None, help="Low-pass resolution (A)")
    parser.add_argument("--threshold-min", type=float, default=None, help="Slider minimum")
    parser.add_argument("--threshold-max", type=float, default=None, help="Slider maximum")
    return parser


def main() -> int:
    _require_mrcfile()
    _require_matplotlib()

    args = _build_parser().parse_args()

    template_paths = _expand_templates(args.templates)
    if not template_paths:
        raise RuntimeError("No templates found")

    image = _read_mrc(args.image)
    templates = [_read_mrc(path) for path in template_paths]

    if len(args.angle_range) == 0:
        angle_ranges = [(0.0, 360.0, 10.0)] * len(templates)
    elif len(args.angle_range) == 1 and len(templates) > 1:
        angle_ranges = [_parse_angle_range(args.angle_range[0])] * len(templates)
    elif len(args.angle_range) == len(templates):
        angle_ranges = [_parse_angle_range(x) for x in args.angle_range]
    else:
        raise RuntimeError("angle-range must be supplied once or once-per-template")

    base = pick_particles(
        image=image,
        templates=templates,
        params={
            "diameter_angstrom": args.diameter,
            "image_pixel_size_angstrom": args.image_apix,
            "template_pixel_size_angstrom": args.template_apix,
            "bin": args.bin,
            "invert_templates": args.invert_templates,
            "lowpass_resolution_angstrom": args.lowpass_resolution,
            "threshold": args.initial_threshold,
            "max_peaks": args.max_peaks,
            "overlap_multiplier": args.overlap_multiplier,
            "max_blob_size_multiplier": args.max_blob_size_multiplier,
            "min_blob_roundness": args.min_blob_roundness,
            "peak_position": args.peak_position,
            "angle_ranges": angle_ranges,
        },
    )
    filtered_image = np.asarray(base["preprocessed_image"], dtype=np.float32)
    target_apix = float(base["target_pixel_size_angstrom"])

    merged_map = np.asarray(base["merged_score_map"], dtype=np.float32)
    finite = np.isfinite(merged_map)
    valid = merged_map[finite] if finite.any() else np.array([0.0], dtype=np.float32)
    auto_min = float(np.percentile(valid, 0.5))
    auto_max = float(np.percentile(valid, 99.5))
    if auto_max <= auto_min:
        auto_min = float(valid.min())
        auto_max = float(valid.max())
    slider_min = args.threshold_min if args.threshold_min is not None else auto_min
    slider_max = args.threshold_max if args.threshold_max is not None else auto_max
    if slider_max <= slider_min:
        slider_max = slider_min + 1e-3
    initial_threshold = min(max(float(args.initial_threshold), slider_min), slider_max)

    radius_pixels = float(base["radius_pixels"])
    current_particles = _threshold_particles(
        base_result=base,
        threshold=initial_threshold,
        radius_pixels=radius_pixels,
        max_peaks=args.max_peaks,
        overlap_multiplier=args.overlap_multiplier,
        max_blob_size_multiplier=args.max_blob_size_multiplier,
        min_blob_roundness=args.min_blob_roundness,
        peak_position=args.peak_position,
        image_shape=filtered_image.shape,
    )

    fig, (ax_img, ax_cc) = plt.subplots(1, 2, figsize=(14, 7))
    plt.subplots_adjust(bottom=0.18)

    ax_img.imshow(_normalized_float(filtered_image), cmap="gray", origin="upper")
    ax_img.set_title("Filtered Image + Picks")
    ax_img.set_axis_off()

    cc_im = ax_cc.imshow(merged_map, cmap="inferno", origin="upper")
    ax_cc.set_title("Merged Correlation Map")
    ax_cc.set_axis_off()
    cbar = fig.colorbar(cc_im, ax=ax_cc, fraction=0.046, pad=0.04)
    cbar.set_label("CC value")
    threshold_line = cbar.ax.axhline(initial_threshold, color="cyan", linewidth=1.5)

    scatter = ax_img.scatter([], [], marker="+", s=180, linewidths=2.0, c="red")
    circle_artists: List[Circle] = []

    status_text = fig.text(0.02, 0.02, "", fontsize=11)
    slider_ax = fig.add_axes([0.17, 0.08, 0.68, 0.035])
    slider = Slider(
        ax=slider_ax,
        label="CC threshold",
        valmin=slider_min,
        valmax=slider_max,
        valinit=initial_threshold,
        valstep=(slider_max - slider_min) / 500.0,
    )

    def _set_scatter(particles: Iterable[Dict[str, Any]], threshold: float) -> None:
        nonlocal circle_artists
        plist = list(particles)

        for artist in circle_artists:
            artist.remove()
        circle_artists = []

        if plist:
            coords = np.array([[p["x"], p["y"]] for p in plist], dtype=np.float32)
            scatter.set_offsets(coords)
            scatter.set_color("red")
            for p in plist:
                circ = Circle(
                    (float(p["x"]), float(p["y"])),
                    radius=radius_pixels,
                    fill=False,
                    edgecolor="red",
                    linewidth=1.0,
                    alpha=0.9,
                )
                ax_img.add_patch(circ)
                circle_artists.append(circ)
        else:
            scatter.set_offsets(np.empty((0, 2)))
            scatter.set_color("red")
        status_text.set_text(
            f"Threshold: {threshold:.3f} | Picks: {len(plist)} | Templates: {len(template_paths)} | target_apix: {target_apix:.3f} A/pix"
        )
        threshold_line.set_ydata([threshold, threshold])
        fig.canvas.draw_idle()

    _set_scatter(current_particles, initial_threshold)

    def _on_slider_change(value: float) -> None:
        particles = _threshold_particles(
            base_result=base,
            threshold=float(value),
            radius_pixels=radius_pixels,
            max_peaks=args.max_peaks,
            overlap_multiplier=args.overlap_multiplier,
            max_blob_size_multiplier=args.max_blob_size_multiplier,
            min_blob_roundness=args.min_blob_roundness,
            peak_position=args.peak_position,
            image_shape=filtered_image.shape,
        )
        _set_scatter(particles, float(value))

    slider.on_changed(_on_slider_change)
    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
