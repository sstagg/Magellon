"""Particle stack maker — vendored from Sandbox/magellon_stack_maker.

Given a micrograph and particle coordinates, this module extracts boxed
particles, computes edge-based per-particle normalization, pads edge
boxes, and emits RELION-ready outputs (.mrcs + .star + .json).

Vendored 2026-05-03 (Phase 5). Two known integration bugs called out in
``Sandbox/MAGELLON_PARTICLE_PIPELINE.md`` are fixed in this copy:

  1. ``_format_image_token`` now emits ``000001@stack.mrcs`` (RELION
     convention; what the CAN classifier parses) instead of the original
     ``stack.mrcs@000001``.
  2. ``write_relion_star`` writes ``_rlnImagePixelSize`` instead of
     ``_rlnPixelSize`` so the classifier's STAR reader finds it.

If the Sandbox crate moves to a published package, replace this file
with an import — keep the bus contract (ParticleExtractionInput /
ParticleExtractionOutput) stable.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class CTFParams:
    """Optional CTF metadata attached to particles."""

    defocus_u_angstrom: Optional[float] = None
    defocus_v_angstrom: Optional[float] = None
    defocus_angle_deg: Optional[float] = None
    voltage_kv: Optional[float] = None
    spherical_aberration_mm: Optional[float] = None
    phase_shift_deg: Optional[float] = None
    amplitude_contrast: Optional[float] = None


@dataclass(frozen=True)
class ParticleCoordinate:
    x: float
    y: float
    score: Optional[float] = None
    angle: Optional[float] = None
    class_number: Optional[int] = None


@dataclass(frozen=True)
class ParticleStackConfig:
    box_size: int
    edge_width: int = 2
    allow_partial: bool = True
    micrograph_pixel_size_angstrom: Optional[float] = None
    image_name: Optional[str] = None
    ctf_lookup: Optional[Dict[str, CTFParams]] = None


@dataclass
class ParticleStackRow:
    index: int
    micrograph_name: str
    x: float
    y: float
    score: float = 0.0
    angle: float = 0.0
    class_number: int = 1
    edge_mean: float = 0.0
    edge_std: float = 0.0
    ctf: Optional[CTFParams] = None
    extracted_box: Optional[np.ndarray] = None


def _to_int(value: Any, name: str) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if ivalue <= 0:
        raise ValueError(f"{name} must be > 0")
    return ivalue


def _to_float(value: Any, name: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number, got {value!r}") from exc


def _half_box(box_size: int) -> int:
    if box_size < 1:
        raise ValueError("box_size must be >= 1")
    if box_size % 2 != 0:
        raise ValueError("box_size must be even (centered extraction convention)")
    return int(math.floor((box_size - 1) / 2))


def _normalize_edge_stats(box: np.ndarray, edge_width: int) -> Tuple[float, float]:
    if edge_width <= 0:
        edge_pixels = box.reshape(-1)
    elif box.shape[0] < 2 * edge_width + 1 or box.shape[1] < 2 * edge_width + 1:
        edge_pixels = box.reshape(-1)
    else:
        top = box[:edge_width, :]
        bottom = box[-edge_width:, :]
        left = box[edge_width:-edge_width, :edge_width] if box.shape[1] > 2 * edge_width else np.empty((0, 0))
        right = box[edge_width:-edge_width, -edge_width:] if box.shape[1] > 2 * edge_width else np.empty((0, 0))
        edge_pixels = np.concatenate(
            [top.reshape(-1), bottom.reshape(-1), left.reshape(-1), right.reshape(-1)]
        )
    if edge_pixels.size == 0:
        edge_pixels = box.reshape(-1)
    valid = edge_pixels[np.isfinite(edge_pixels)]
    if valid.size == 0:
        return 0.0, 1.0
    mean = float(np.mean(valid))
    std = float(np.std(valid))
    if not np.isfinite(std) or std <= 0.0:
        std = 1.0
    return mean, std


def _extract_box(image: np.ndarray, x: float, y: float, box_size: int, allow_partial: bool) -> np.ndarray:
    if box_size <= 0:
        raise ValueError("box_size must be > 0")
    if image.ndim != 2:
        raise ValueError("micrograph must be a 2D array")

    cx = int(round(float(x)))
    cy = int(round(float(y)))
    radius = _half_box(box_size)

    x0 = cx - radius
    y0 = cy - radius
    x1 = x0 + box_size
    y1 = y0 + box_size

    h, w = image.shape
    if allow_partial:
        x0_clip = max(0, x0)
        y0_clip = max(0, y0)
        x1_clip = min(w, x1)
        y1_clip = min(h, y1)
        if x0_clip >= x1_clip or y0_clip >= y1_clip:
            raise ValueError(f"Coordinate ({x:.2f}, {y:.2f}) is completely outside image bounds")
        return image[y0_clip:y1_clip, x0_clip:x1_clip]

    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        raise ValueError(
            f"Coordinate ({x:.2f},{y:.2f}) requires box size {box_size} that exceeds image boundary"
        )
    return image[y0:y1, x0:x1]


def _pad_to_square(box: np.ndarray, target_shape: int) -> np.ndarray:
    if box.ndim != 2:
        raise ValueError("box must be 2D")
    h, w = box.shape
    if h == target_shape and w == target_shape:
        return box
    return _pad_to_square_with_falloff(box, target_shape=target_shape)


def _pad_to_square_with_falloff(box: np.ndarray, target_shape: int) -> np.ndarray:
    """Soft-pad partial boxes by blending toward a mean background."""
    if target_shape < 1:
        raise ValueError("target_shape must be >=1")
    h, w = box.shape
    if h > target_shape or w > target_shape:
        raise ValueError("box cannot be larger than target shape")
    if h == target_shape and w == target_shape:
        return box

    finite = np.isfinite(box)
    fill = float(np.mean(box[finite])) if finite.any() else 0.0

    pad_top = max(0, (target_shape - h) // 2)
    pad_left = max(0, (target_shape - w) // 2)
    pad_bottom = max(0, target_shape - h - pad_top)
    pad_right = max(0, target_shape - w - pad_left)

    y0 = pad_top
    x0 = pad_left
    y1 = y0 + h
    x1 = x0 + w

    out = np.full((target_shape, target_shape), fill, dtype=np.float32)
    out[y0:y1, x0:x1] = box.astype(np.float32)

    rows = np.arange(target_shape, dtype=np.float32)[:, None]
    cols = np.arange(target_shape, dtype=np.float32)[None, :]
    top_dist = np.maximum(rows - y0, 0.0)
    bottom_dist = np.maximum((y1 - 1) - rows, 0.0)
    left_dist = np.maximum(cols - x0, 0.0)
    right_dist = np.maximum((x1 - 1) - cols, 0.0)

    inside = (rows >= y0) & (rows < y1) & (cols >= x0) & (cols < x1)
    if inside.all():
        return out

    max_steps = max(pad_top, pad_bottom, pad_left, pad_right)
    fade_width = max(min(max_steps, 4), 1)
    edge_distance = np.minimum(np.minimum(top_dist, bottom_dist), np.minimum(left_dist, right_dist))
    fade = np.clip((edge_distance + 1.0) / float(fade_width + 1), 0.0, 1.0)

    taper_region = inside & (edge_distance <= fade_width)
    out[taper_region] = ((1.0 - fade[taper_region]) * out[taper_region] + fade[taper_region] * fill).astype(np.float32)
    return out.astype(np.float32)


def _normalize_box(box: np.ndarray, edge_width: int) -> Tuple[np.ndarray, float, float]:
    mean, std = _normalize_edge_stats(box, edge_width=edge_width)
    normalized = (box.astype(np.float32) - mean) / std
    return normalized, mean, std


def _as_particle_coords(source: Sequence[Dict[str, Any]]) -> List[ParticleCoordinate]:
    particles: List[ParticleCoordinate] = []
    for item in source:
        if not isinstance(item, dict):
            raise ValueError("particle items must be dictionaries")
        if "x" not in item or "y" not in item:
            if "x_coordinate" in item and "y_coordinate" in item:
                item = dict(item)
                item["x"] = item["x_coordinate"]
                item["y"] = item["y_coordinate"]
            else:
                raise ValueError("particle item missing required x/y fields")
        x = _to_float(item["x"], "x")
        y = _to_float(item["y"], "y")
        if x is None or y is None:
            raise ValueError("x and y must be numeric")
        particles.append(
            ParticleCoordinate(
                x=x,
                y=y,
                score=item.get("score"),
                angle=item.get("angle") if item.get("angle") is not None else item.get("angle_deg"),
                class_number=item.get("class_number", 1),
            )
        )
    return particles


def _ctf_from_lookup(maybe_map: Optional[Dict[str, Any]], micrograph_name: str) -> Optional[CTFParams]:
    if not maybe_map:
        return None
    raw = maybe_map.get(micrograph_name)
    if raw is None:
        return None
    if isinstance(raw, CTFParams):
        return raw
    if not isinstance(raw, dict):
        raise ValueError(f"ctf lookup for {micrograph_name!r} must map to dict")
    return CTFParams(
        defocus_u_angstrom=_to_float(raw.get("defocus_u_angstrom"), "defocus_u_angstrom"),
        defocus_v_angstrom=_to_float(raw.get("defocus_v_angstrom"), "defocus_v_angstrom"),
        defocus_angle_deg=_to_float(raw.get("defocus_angle_deg"), "defocus_angle_deg"),
        voltage_kv=_to_float(raw.get("voltage_kv"), "voltage_kv"),
        spherical_aberration_mm=_to_float(raw.get("spherical_aberration_mm"), "spherical_aberration_mm"),
        phase_shift_deg=_to_float(raw.get("phase_shift_deg"), "phase_shift_deg"),
        amplitude_contrast=_to_float(raw.get("amplitude_contrast"), "amplitude_contrast"),
    )


def build_particle_records(
    micrograph: np.ndarray,
    coordinates: Sequence[ParticleCoordinate],
    config: ParticleStackConfig,
) -> List[ParticleStackRow]:
    if micrograph.ndim != 2:
        raise ValueError("micrograph must be a 2D array")
    box = _to_int(config.box_size, "box_size")
    edge_width = _to_int(config.edge_width, "edge_width")
    micrograph_name = config.image_name or "micrograph.mrc"
    rows: List[ParticleStackRow] = []

    for idx, coord in enumerate(coordinates, start=1):
        raw_box = _extract_box(
            image=micrograph,
            x=coord.x,
            y=coord.y,
            box_size=box,
            allow_partial=config.allow_partial,
        )
        normalized, edge_mean, edge_std = _normalize_box(raw_box, edge_width=edge_width)
        if raw_box.shape[0] != box or raw_box.shape[1] != box:
            normalized = _pad_to_square(normalized, box)

        rows.append(
            ParticleStackRow(
                index=idx,
                micrograph_name=micrograph_name,
                x=float(coord.x),
                y=float(coord.y),
                score=float(coord.score) if coord.score is not None else 0.0,
                angle=float(coord.angle) if coord.angle is not None else 0.0,
                class_number=int(coord.class_number) if coord.class_number is not None else 1,
                edge_mean=edge_mean,
                edge_std=edge_std,
                ctf=_ctf_from_lookup(config.ctf_lookup, micrograph_name),
                extracted_box=normalized.astype(np.float32),
            )
        )
    return rows


def create_particle_stack(particles: Sequence[ParticleStackRow], output_path: str) -> None:
    if len(particles) == 0:
        raise ValueError("No particles to write")
    try:
        import mrcfile
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "mrcfile is required for writing .mrcs stacks. Install with: pip install mrcfile"
        ) from exc

    stack = np.stack(
        [p.extracted_box for p in particles if p.extracted_box is not None], axis=0
    ).astype(np.float32)
    if stack.shape[0] == 0:
        raise ValueError("No extracted boxes available for writing stack")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with mrcfile.new(output.as_posix(), overwrite=True) as mrc:
        mrc.set_data(stack)


def _format_image_token(stack_path: Optional[str], index: int) -> str:
    """RELION ``_rlnImageName`` token: ``NNNNNN@stack.mrcs``.

    Phase 5 fix: reversed token order from the original Sandbox copy.
    The CAN classifier's ``_resolve_image_path`` parses ``NNNNNN@stack``
    — the previous order broke downstream consumption.
    """
    if stack_path is None:
        return f"{index:06d}"
    return f"{index:06d}@{Path(stack_path).name}"


def _fmt_or_missing(value: Optional[float], default: str) -> str:
    if value is None or not np.isfinite(value):
        return default
    return f"{float(value):.6f}"


def write_relion_star(
    rows: Sequence[ParticleStackRow],
    output_path: str,
    stack_path: Optional[str] = None,
    micrograph_pixel_size_angstrom: Optional[float] = None,
) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    include_ctf = any(r.ctf for r in rows)

    columns = [
        "_rlnImageName #1",
        "_rlnMicrographName #2",
        "_rlnCoordinateX #3",
        "_rlnCoordinateY #4",
        "_rlnClassNumber #5",
        "_rlnAutopickFigureOfMerit #6",
        "_rlnAngleRot #7",
    ]
    if include_ctf:
        columns.extend(
            [
                "_rlnDefocusU #8",
                "_rlnDefocusV #9",
                "_rlnDefocusAngle #10",
                "_rlnVoltage #11",
                "_rlnSphericalAberration #12",
                "_rlnPhaseShift #13",
                "_rlnAmplitudeContrast #14",
            ]
        )
    if micrograph_pixel_size_angstrom is not None:
        # Phase 5 fix: use ``_rlnImagePixelSize`` (what the classifier
        # reads) instead of the original ``_rlnPixelSize``.
        columns.append("_rlnImagePixelSize #15")

    with output.open("w") as handle:
        handle.write("data_particles\n\n")
        handle.write("loop_\n")
        for column in columns:
            handle.write(f"{column}\n")

        for row in rows:
            image_token = _format_image_token(stack_path, row.index)
            values: List[str] = [
                image_token,
                row.micrograph_name,
                f"{row.x:.6f}",
                f"{row.y:.6f}",
                str(row.class_number),
                f"{row.score:.6f}",
                f"{row.angle:.6f}",
            ]
            if include_ctf:
                ctf = row.ctf
                if ctf is None:
                    values.extend(["-1", "-1", "-1", "-1", "-1", "-1", "-1"])
                else:
                    values.extend(
                        [
                            _fmt_or_missing(ctf.defocus_u_angstrom, "0"),
                            _fmt_or_missing(ctf.defocus_v_angstrom, "0"),
                            _fmt_or_missing(ctf.defocus_angle_deg, "0"),
                            _fmt_or_missing(ctf.voltage_kv, "300"),
                            _fmt_or_missing(ctf.spherical_aberration_mm, "2.7"),
                            _fmt_or_missing(ctf.phase_shift_deg, "0"),
                            _fmt_or_missing(ctf.amplitude_contrast, "0.07"),
                        ]
                    )
            if micrograph_pixel_size_angstrom is not None:
                values.append(f"{micrograph_pixel_size_angstrom:.6f}")
            handle.write(" ".join(values) + "\n")


def write_json_output(rows: Sequence[ParticleStackRow], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    items: List[Dict[str, Any]] = []
    for row in rows:
        item: Dict[str, Any] = {
            "index": row.index,
            "micrograph_name": row.micrograph_name,
            "x": row.x,
            "y": row.y,
            "score": row.score,
            "angle": row.angle,
            "class_number": row.class_number,
            "edge_mean": row.edge_mean,
            "edge_std": row.edge_std,
        }
        if row.ctf is not None:
            item["ctf"] = {
                "defocus_u_angstrom": row.ctf.defocus_u_angstrom,
                "defocus_v_angstrom": row.ctf.defocus_v_angstrom,
                "defocus_angle_deg": row.ctf.defocus_angle_deg,
                "voltage_kv": row.ctf.voltage_kv,
                "spherical_aberration_mm": row.ctf.spherical_aberration_mm,
                "phase_shift_deg": row.ctf.phase_shift_deg,
                "amplitude_contrast": row.ctf.amplitude_contrast,
            }
        items.append(item)

    with output.open("w") as handle:
        json.dump(items, handle, indent=2)


def load_particles_from_json(path: str) -> List[Dict[str, Any]]:
    with Path(path).open() as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("particle JSON must be a list")
    return data


def load_particles_from_csv(path: str) -> List[Dict[str, Any]]:
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def build_and_write(
    micrograph: np.ndarray,
    particles: Sequence[Dict[str, Any]],
    config: ParticleStackConfig,
    star_output: str,
    json_output: str,
    stack_output: Optional[str] = None,
) -> Dict[str, Any]:
    """End-to-end API: build rows and write outputs."""
    coords = _as_particle_coords(particles)
    if not coords:
        rows: List[ParticleStackRow] = []
        write_relion_star(
            rows,
            star_output,
            stack_path=stack_output,
            micrograph_pixel_size_angstrom=config.micrograph_pixel_size_angstrom,
        )
        write_json_output(rows, json_output)
        return {
            "count": 0,
            "rows": rows,
            "stack_output": None,
            "star_output": star_output,
            "json_output": json_output,
        }

    rows = build_particle_records(micrograph=micrograph, coordinates=coords, config=config)
    if stack_output is not None:
        create_particle_stack(rows, stack_output)
    write_relion_star(
        rows=rows,
        output_path=star_output,
        stack_path=stack_output,
        micrograph_pixel_size_angstrom=config.micrograph_pixel_size_angstrom,
    )
    write_json_output(rows=rows, output_path=json_output)

    return {
        "count": len(rows),
        "rows": rows,
        "stack_output": stack_output,
        "star_output": star_output,
        "json_output": json_output,
    }
