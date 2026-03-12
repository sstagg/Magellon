"""Command line interface for projection generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List
from math import isfinite
import numpy as np

from .backend import geometry
from .backend import io as mrc_io
from .backend.projection import iter_projections
from .gui import launch_gui
from scipy.ndimage import zoom


def _read_angle_file(path: str) -> List[tuple[float, float, float]]:
    text = Path(path).read_text().strip()
    if not text:
        raise ValueError(f"Angle file '{path}' is empty.")

    data = None
    try:
        loaded = json.loads(text)
        if isinstance(loaded, list):
            data = loaded
        elif isinstance(loaded, dict):
            data = [loaded]
    except json.JSONDecodeError:
        data = None

    if data is not None:
        return _parse_angle_records(data)

    parsed = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.replace(",", " ").split() if part.strip()]
        if len(parts) < 3:
            continue
        parsed.append((float(parts[0]), float(parts[1]), float(parts[2])))
    if not parsed:
        raise ValueError(f"Could not parse angles from '{path}'.")
    return parsed


def _parse_angle_records(data) -> List[tuple[float, float, float]]:
    angles = []
    for entry in data:
        if isinstance(entry, dict):
            try:
                rot = float(entry["rot"])
                tilt = float(entry["tilt"])
                psi = float(entry["psi"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "JSON angle file entries must include rot, tilt, psi keys."
                ) from exc
            angles.append((rot, tilt, psi))
            continue

        if not isinstance(entry, (list, tuple)):
            raise ValueError("Angle entry must be list/tuple or mapping.")
        if len(entry) != 3:
            raise ValueError("Angle entries must contain exactly three values.")
        angles.append((float(entry[0]), float(entry[1]), float(entry[2])))
    return angles


def _positive_scale(value: str) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("scale must be a positive number.") from exc
    if not isfinite(scale) or scale <= 0.0:
        raise argparse.ArgumentTypeError("scale must be a positive number.")
    return scale


def _apply_load_scale(
    volume: np.ndarray,
    voxel_size: tuple[float, float, float],
    scale: float,
) -> tuple[np.ndarray, tuple[float, float, float]]:
    if scale == 1.0:
        return volume, voxel_size

    scaled = zoom(volume, zoom=(scale, scale, scale), order=1)
    scaled_voxel = tuple(float(v) / scale for v in voxel_size)
    return scaled.astype(np.float32, copy=False), scaled_voxel


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cryo-projector",
        description="Generate projections from cryo-EM MRC volumes.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gui = sub.add_parser("gui", help="Launch interactive projection GUI.")
    gui.add_argument("--input", required=True, help="Input 3D MRC volume.")
    gui.add_argument(
        "--scale",
        type=_positive_scale,
        default=1.0,
        help="Optional spatial load scale for speed (default: 1.0, no scaling).",
    )
    gui.add_argument(
        "--output-default-dir",
        help="Default directory for GUI 'save current projection' prompts.",
        default=None,
    )
    gui.set_defaults(func=_run_gui)

    project = sub.add_parser(
        "project",
        help="Render projections in CLI and save as an MRC stack.",
    )
    project.add_argument("--input", required=True, help="Input 3D MRC volume.")
    project.add_argument(
        "--output",
        default="projections.mrc",
        help="Output MRC file for projection stack.",
    )
    project.add_argument(
        "--euler",
        action="append",
        nargs=3,
        type=float,
        metavar=("ROT", "TILT", "PSI"),
        help="Repeatable explicit Euler triplet.",
    )
    project.add_argument(
        "--euler-file",
        help="JSON or plain-text file with one Euler triplet per line.",
    )
    project.add_argument(
        "--sample-n",
        type=int,
        help="Generate N evenly sampled projection directions.",
    )
    project.add_argument(
        "--backend",
        choices=("real", "fft-reference"),
        default="real",
        help="Projection backend: real (default), fft-reference.",
    )
    project.add_argument(
        "--scale",
        type=_positive_scale,
        default=1.0,
        help="Optional spatial load scale for speed (default: 1.0, no scaling).",
    )
    project.set_defaults(func=_run_project)

    return parser


def _run_gui(args: argparse.Namespace) -> int:
    return launch_gui(args.input, load_scale=args.scale, default_output_dir=args.output_default_dir)


def _run_project(args: argparse.Namespace) -> int:
    explicit_eulers = []
    if args.euler:
        explicit_eulers.extend(args.euler)

    if args.euler_file:
        explicit_eulers.extend(_read_angle_file(args.euler_file))

    eulers = geometry.as_angle_triplets(explicit_eulers)
    if not eulers:
        if args.sample_n is None:
            raise SystemExit(
                "--sample-n is required when no --euler / --euler-file is supplied."
            )
        eulers = geometry.generate_even_eulers(args.sample_n)

    if args.sample_n is not None and args.sample_n < 1:
        raise SystemExit("--sample-n must be a positive integer.")
    if eulers and args.sample_n:
        # Preserve explicit angles; ignore sample if user also provided angles.
        pass

    volume, meta = mrc_io.read_mrc(args.input)
    loaded_volume, loaded_voxel = _apply_load_scale(volume, meta.voxel_size, args.scale)

    projections = iter_projections(
        loaded_volume,
        eulers,
        interpolation=1,
        backend=args.backend,
    )
    first = next(projections)
    with mrc_io.open_projection_stack(
        args.output,
        projection_count=len(eulers),
        projection_shape=first.shape,
        voxel_size=loaded_voxel,
    ) as mrc:
        mrc.data[0] = first
        for index, projection in enumerate(projections, start=1):
            mrc.data[index] = projection
    return 0


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
