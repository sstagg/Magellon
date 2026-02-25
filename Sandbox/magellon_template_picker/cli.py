#!/usr/bin/env python
"""
CLI for standalone Magellon template picking.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from PIL import Image
from PIL import ImageDraw

try:
    # Package mode (python -m magellon_template_picker from parent dir)
    from .picker import pick_particles
except ImportError:
    # Standalone mode (python cli.py from project root)
    from picker import pick_particles

try:
    import mrcfile
except Exception as exc:  # pragma: no cover - import error path
    mrcfile = None
    _mrc_import_error = exc
else:
    _mrc_import_error = None


def _require_mrcfile() -> None:
    if mrcfile is None:
        raise RuntimeError(
            "mrcfile is required for CLI I/O. Install with: pip install mrcfile "
            f"(import error: {_mrc_import_error})"
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


def _write_png(path: str, array: np.ndarray) -> None:
    data = np.asarray(array, dtype=np.float32)
    lo, hi = _display_limits(data)
    if hi <= lo:
        img = np.zeros(data.shape, dtype=np.uint8)
    else:
        clipped = np.clip(data, lo, hi)
        scaled = (clipped - lo) / (hi - lo)
        img = (scaled * 255.0).astype(np.uint8)
    Image.fromarray(img, mode="L").save(path, format="PNG")


def _normalized_uint8(array: np.ndarray) -> np.ndarray:
    data = np.asarray(array, dtype=np.float32)
    lo, hi = _display_limits(data)
    if hi <= lo:
        return np.zeros(data.shape, dtype=np.uint8)
    clipped = np.clip(data, lo, hi)
    scaled = (clipped - lo) / (hi - lo)
    return (scaled * 255.0).astype(np.uint8)


def _display_limits(array: np.ndarray) -> Tuple[float, float]:
    finite = np.isfinite(array)
    if not finite.any():
        return 0.0, 0.0
    valid = array[finite]
    lo = float(np.percentile(valid, 1.0))
    hi = float(np.percentile(valid, 99.0))
    if hi <= lo:
        lo = float(valid.min())
        hi = float(valid.max())
    return lo, hi


def _write_map_with_scale_bar_png(
    path: str,
    array: np.ndarray,
    threshold: float | None = None,
    label: str = "CC",
) -> None:
    data = np.asarray(array, dtype=np.float32)
    lo, hi = _display_limits(data)
    base = _normalized_uint8(data)
    map_image = Image.fromarray(base, mode="L").convert("RGB")

    bar_height = 52
    width = map_image.width
    canvas = Image.new("RGB", (width, map_image.height + bar_height), color=(0, 0, 0))
    canvas.paste(map_image, (0, 0))
    draw = ImageDraw.Draw(canvas)

    bar_y0 = map_image.height + 10
    bar_y1 = bar_y0 + 12
    if width > 1:
        for x in range(width):
            value = int(round((x / float(width - 1)) * 255.0))
            draw.line((x, bar_y0, x, bar_y1), fill=(value, value, value), width=1)

    text_y = bar_y1 + 4
    draw.text((0, text_y), f"{label} min {lo:.3f}", fill=(255, 255, 255))
    max_text = f"max {hi:.3f}"
    draw.text((max(0, width - (len(max_text) * 7)), text_y), max_text, fill=(255, 255, 255))

    if threshold is not None and hi > lo:
        frac = (float(threshold) - lo) / (hi - lo)
        frac = min(1.0, max(0.0, frac))
        xthr = int(round(frac * (width - 1)))
        draw.line((xthr, bar_y0 - 3, xthr, bar_y1 + 3), fill=(255, 80, 80), width=1)
        draw.text((max(0, xthr - 30), max(0, bar_y0 - 18)), f"thr {threshold:.3f}", fill=(255, 80, 80))

    canvas.save(path, format="PNG")


def _write_particle_overlay_png(
    path: str,
    base_image: np.ndarray,
    particles: Iterable[dict],
    radius_pixels: float | None = None,
) -> None:
    palette = [
        (255, 64, 64),
        (61, 242, 61),
        (61, 61, 242),
        (242, 242, 61),
        (61, 242, 242),
        (242, 61, 242),
        (242, 151, 61),
        (61, 242, 151),
        (151, 61, 242),
        (151, 242, 61),
        (61, 151, 242),
        (242, 61, 151),
    ]
    base = _normalized_uint8(base_image)
    image = Image.fromarray(base, mode="L").convert("RGB")
    draw = ImageDraw.Draw(image)
    for particle in particles:
        x = int(particle["x"])
        y = int(particle["y"])
        template_index = int(particle.get("template_index", 1))
        color = palette[(template_index - 1) % len(palette)]
        size = 8
        draw.line((x - size, y, x + size, y), fill=color, width=2)
        draw.line((x, y - size, x, y + size), fill=color, width=2)
        if radius_pixels is not None and radius_pixels > 0:
            r = float(radius_pixels)
            draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=1)
    image.save(path, format="PNG")


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


def _write_particles_csv(path: str, particles: Iterable[dict]) -> None:
    fields = ["x", "y", "score", "stddev", "area", "roundness", "template_index", "angle", "label"]
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for p in particles:
            writer.writerow({k: p.get(k) for k in fields})


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone template picker for cryo-EM")
    parser.add_argument("--image", required=True, help="Input micrograph MRC path")
    parser.add_argument(
        "--template",
        action="append",
        required=True,
        dest="templates",
        help="Template MRC path or glob; repeat for multiple entries",
    )
    parser.add_argument("--image-apix", type=float, required=True, help="Input image pixel size (A/pix)")
    parser.add_argument(
        "--template-apix",
        type=float,
        required=True,
        help="Template pixel size (A/pix), shared by all templates",
    )
    parser.add_argument(
        "--invert-templates",
        action="store_true",
        help="Invert template contrast (multiply by -1 before scaling/filtering)",
    )
    parser.add_argument(
        "--bin",
        type=int,
        default=1,
        help="Image binning factor (power of two only: 1,2,4,8,...)",
    )
    parser.add_argument("--diameter", type=float, required=True, help="Particle diameter (A)")
    parser.add_argument("--threshold", type=float, default=0.4, help="Score threshold")
    parser.add_argument("--max-threshold", type=float, default=None, help="Optional upper score filter")
    parser.add_argument("--max-peaks", type=int, default=500, help="Maximum number of final particles")
    parser.add_argument(
        "--overlap-multiplier",
        type=float,
        default=1.0,
        help="Minimum separation = overlap_multiplier * particle_radius_pixels",
    )
    parser.add_argument(
        "--max-blob-size-multiplier",
        type=float,
        default=1.0,
        help="Blob area cap multiplier relative to particle area",
    )
    parser.add_argument("--min-blob-roundness", type=float, default=0.0, help="Minimum blob roundness")
    parser.add_argument(
        "--peak-position",
        choices=["maximum", "center"],
        default="maximum",
        help="How to assign blob coordinates",
    )
    parser.add_argument(
        "--angle-range",
        action="append",
        default=[],
        help="Template angle range start,end,step; repeat per template or provide once for all",
    )
    parser.add_argument(
        "--lowpass-resolution",
        type=float,
        default=None,
        help="Low-pass target resolution in Angstrom; applied to binned image and scaled templates",
    )
    parser.add_argument("--outdir", default="picker_output", help="Output directory")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    template_paths = _expand_templates(args.templates)
    if not template_paths:
        raise RuntimeError("No templates found")

    os.makedirs(args.outdir, exist_ok=True)

    image = _read_mrc(args.image)
    templates = [_read_mrc(path) for path in template_paths]

    if len(args.angle_range) == 0:
        angle_ranges = [(0.0, 360.0, 10.0)] * len(processed_templates)
    elif len(args.angle_range) == 1 and len(processed_templates) > 1:
        angle_ranges = [_parse_angle_range(args.angle_range[0])] * len(processed_templates)
    elif len(args.angle_range) == len(processed_templates):
        angle_ranges = [_parse_angle_range(x) for x in args.angle_range]
    else:
        raise RuntimeError("angle-range must be supplied once or once-per-template")

    result = pick_particles(
        image=image,
        templates=templates,
        params={
            "diameter_angstrom": args.diameter,
            "image_pixel_size_angstrom": args.image_apix,
            "template_pixel_size_angstrom": args.template_apix,
            "bin": args.bin,
            "invert_templates": args.invert_templates,
            "lowpass_resolution_angstrom": args.lowpass_resolution,
            "threshold": args.threshold,
            "max_threshold": args.max_threshold,
            "max_peaks": args.max_peaks,
            "overlap_multiplier": args.overlap_multiplier,
            "max_blob_size_multiplier": args.max_blob_size_multiplier,
            "min_blob_roundness": args.min_blob_roundness,
            "peak_position": args.peak_position,
            "angle_ranges": angle_ranges,
        },
    )
    filtered_image = np.asarray(result["preprocessed_image"], dtype=np.float32)
    target_apix = float(result["target_pixel_size_angstrom"])
    radius_pixels = float(result["radius_pixels"])

    _write_particles_csv(os.path.join(args.outdir, "particles.csv"), result["particles"])
    with open(os.path.join(args.outdir, "particles.json"), "w") as handle:
        json.dump(result["particles"], handle, indent=2)

    _write_png(os.path.join(args.outdir, "input_binned_filtered.png"), filtered_image)
    _write_particle_overlay_png(
        os.path.join(args.outdir, "input_with_template_plus_overlay.png"),
        filtered_image,
        result["particles"],
        radius_pixels=radius_pixels,
    )
    _write_map_with_scale_bar_png(
        os.path.join(args.outdir, "merged_score_map.png"),
        result["merged_score_map"],
        threshold=args.threshold,
        label="Merged CC",
    )

    correlation_maps = []
    for item in result["template_results"]:
        idx = int(item["template_index"])
        corr_name = f"template_{idx:03d}.correlation_map.png"
        _write_map_with_scale_bar_png(
            os.path.join(args.outdir, corr_name),
            item["score_map"],
            threshold=args.threshold,
            label=f"Template {idx} CC",
        )
        correlation_maps.append(corr_name)

    summary = {
        "output_dir": os.path.abspath(args.outdir),
        "num_templates": len(templates),
        "num_particles": len(result["particles"]),
        "target_pixel_size_angstrom": target_apix,
        "input_image_binning": float(args.bin),
        "lowpass_resolution_angstrom": args.lowpass_resolution,
        "invert_templates": bool(args.invert_templates),
        "num_correlation_maps": len(correlation_maps),
        "correlation_maps": correlation_maps,
    }
    with open(os.path.join(args.outdir, "run_summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
