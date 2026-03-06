#!/usr/bin/env python
"""
CLI for standalone RELION stack making from picked coordinates.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from .stack_maker import (
        CTFParams,
        ParticleStackConfig,
        build_and_write,
        load_particles_from_csv,
        load_particles_from_json,
        normalize_micrograph_path,
    )
except ImportError:
    from stack_maker import (
        CTFParams,
        ParticleStackConfig,
        build_and_write,
        load_particles_from_csv,
        load_particles_from_json,
        normalize_micrograph_path,
    )

try:
    import mrcfile
except Exception as exc:  # pragma: no cover - import errors are runtime checks
    mrcfile = None
    _mrc_import_error = exc
else:
    _mrc_import_error = None


def _require_mrcfile() -> None:
    if mrcfile is None:
        raise RuntimeError(
            "mrcfile is required for micrograph I/O. Install with: pip install mrcfile "
            f"(import error: {_mrc_import_error})"
        )


def _read_mrc(path: str) -> tuple[np.ndarray, Optional[float]]:
    _require_mrcfile()
    with mrcfile.open(path, permissive=True) as mrc:
        data = np.asarray(mrc.data, dtype=np.float32)
        apix = getattr(mrc.voxel_size, "x", None)
        if apix is None:
            apix = getattr(getattr(mrc, "voxel_size", None), "x", None)
        if apix is not None:
            try:
                apix = float(apix)
            except Exception:
                apix = None
        if apix is None:
            apix = getattr(getattr(mrc.header, "cella", None), "x", None)
        if apix is not None:
            try:
                apix = float(apix)
            except Exception:
                apix = None
    if data.ndim == 3:
        data = data[0]
    if data.ndim != 2:
        raise ValueError(f"Expected 2D MRC data in {path}, got shape {data.shape}")
    return data, apix


def _load_ctf_lookup(path: Optional[str]) -> Optional[Dict[str, CTFParams]]:
    if path is None:
        return None
    with open(path) as handle:
        raw = json.load(handle)
    if isinstance(raw, dict):
        result: Dict[str, CTFParams] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            result[str(key)] = CTFParams(
                defocus_u_angstrom=_to_float(value.get("defocus_u_angstrom"), "defocus_u_angstrom"),
                defocus_v_angstrom=_to_float(value.get("defocus_v_angstrom"), "defocus_v_angstrom"),
                defocus_angle_deg=_to_float(value.get("defocus_angle_deg"), "defocus_angle_deg"),
                voltage_kv=_to_float(value.get("voltage_kv"), "voltage_kv"),
                spherical_aberration_mm=_to_float(value.get("spherical_aberration_mm"), "spherical_aberration_mm"),
                phase_shift_deg=_to_float(value.get("phase_shift_deg"), "phase_shift_deg"),
                amplitude_contrast=_to_float(value.get("amplitude_contrast"), "amplitude_contrast"),
            )
        if not result:
            raise ValueError("ctf-json must contain micrograph keys mapped to objects")
        return result
    if isinstance(raw, list):
        result = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            key = item.get("micrograph_name") or item.get("micrograph") or item.get("image")
            if key is None:
                continue
            value = dict(item)
            value.pop("micrograph_name", None)
            value.pop("micrograph", None)
            value.pop("image", None)
            result[str(key)] = CTFParams(
                defocus_u_angstrom=_to_float(value.get("defocus_u_angstrom"), "defocus_u_angstrom"),
                defocus_v_angstrom=_to_float(value.get("defocus_v_angstrom"), "defocus_v_angstrom"),
                defocus_angle_deg=_to_float(value.get("defocus_angle_deg"), "defocus_angle_deg"),
                voltage_kv=_to_float(value.get("voltage_kv"), "voltage_kv"),
                spherical_aberration_mm=_to_float(value.get("spherical_aberration_mm"), "spherical_aberration_mm"),
                phase_shift_deg=_to_float(value.get("phase_shift_deg"), "phase_shift_deg"),
                amplitude_contrast=_to_float(value.get("amplitude_contrast"), "amplitude_contrast"),
            )
        if not result:
            raise ValueError("ctf-json list form requires micrograph_name entries")
        return result
    raise ValueError("ctf-json must be a dict or list")


def _load_particles(path: str, fmt: Optional[str] = None) -> List[Dict[str, Any]]:
    if fmt is None:
        lower = path.lower()
        if lower.endswith(".json"):
            fmt = "json"
        elif lower.endswith(".csv"):
            fmt = "csv"
        else:
            raise ValueError("Could not infer particle format. Use --particles-format.")
    if fmt not in {"json", "csv"}:
        raise ValueError("particles format must be json or csv")
    if fmt == "json":
        return load_particles_from_json(path)
    return load_particles_from_csv(path)


def _to_float(value: Any, name: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build particle stack from micrograph + coordinates")
    parser.add_argument("--micrograph", required=True, help="Input micrograph MRC")
    parser.add_argument("--particles", required=True, help="Picked particles JSON or CSV")
    parser.add_argument(
        "--particles-format",
        choices=["json", "csv"],
        default=None,
        help="Force particle file format",
    )
    parser.add_argument(
        "--box-size",
        type=int,
        required=True,
        help="Particle box size in pixels (must be even to match centered extraction convention)",
    )
    parser.add_argument("--edge-width", type=int, default=2, help="Edge width used for per-particle normalization")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        default=True,
        help="Allow partial boxes at image edges (pads zeros).",
    )
    parser.add_argument(
        "--no-allow-partial",
        dest="allow_partial",
        action="store_false",
        help="Require full box inside image bounds.",
    )
    parser.add_argument("--micrograph-apix", type=float, default=None, help="Micrograph pixel size (A/pix)")
    parser.add_argument("--micrograph-name", default=None, help="Override micrograph name in STAR metadata")
    parser.add_argument("--ctf-json", default=None, help="Optional micrograph->CTF JSON")
    parser.add_argument("--star-output", default="particle_stack.star", help="Output STAR path")
    parser.add_argument("--json-output", default="particle_stack.json", help="Output companion JSON path")
    parser.add_argument("--stack-output", default=None, help="Optional output MRCS stack path")
    parser.add_argument("--outdir", default=".", help="Output directory")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    micrograph_path = os.path.abspath(args.micrograph)
    particles_path = os.path.abspath(args.particles)
    outdir = Path(args.outdir)

    micrograph_data, apix_from_header = _read_mrc(micrograph_path)
    micrograph_name = args.micrograph_name or normalize_micrograph_path(micrograph_path)
    micrograph_pixel_size = args.micrograph_apix if args.micrograph_apix is not None else apix_from_header

    particles = _load_particles(particles_path, args.particles_format)
    ctf_lookup = _load_ctf_lookup(args.ctf_json) if args.ctf_json else None

    star_output = str((outdir / args.star_output).resolve())
    json_output = str((outdir / args.json_output).resolve())
    stack_output = str((outdir / args.stack_output).resolve()) if args.stack_output else None

    result = build_and_write(
        micrograph=micrograph_data,
        particles=particles,
        config=ParticleStackConfig(
            box_size=args.box_size,
            edge_width=args.edge_width,
            allow_partial=args.allow_partial,
            micrograph_pixel_size_angstrom=micrograph_pixel_size,
            image_name=micrograph_name,
            ctf_lookup=ctf_lookup,
        ),
        star_output=star_output,
        json_output=json_output,
        stack_output=stack_output,
    )
    print(
        "Wrote stack output: "
        f"{result['count']} particles, "
        f"star={result['star_output']}, "
        f"json={result['json_output']}, "
        f"stack={result['stack_output']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
