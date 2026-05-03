"""Particle extraction (stack maker) — wires the algorithm to the SDK.

Single micrograph + particle coordinates → ``.mrcs`` stack + ``.star`` +
companion ``.json``. Pure-numpy compute path, no broker awareness.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mrcfile
import numpy as np

from plugin.algorithm import (
    ParticleStackConfig,
    build_and_write,
    load_particles_from_csv,
    load_particles_from_json,
)


def _load_micrograph(path: str) -> np.ndarray:
    """Read a .mrc / .mrcs micrograph as a 2D float32 array."""
    with mrcfile.open(path, permissive=True) as mrc:
        data = np.asarray(mrc.data, dtype=np.float32)
    if data.ndim == 3:
        data = data[0]
    if data.ndim != 2:
        raise ValueError(f"micrograph at {path} is {data.ndim}-D; expected 2-D")
    return data


def _load_particles(path: str) -> List[Dict[str, Any]]:
    """Auto-detect JSON / CSV by extension."""
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return load_particles_from_json(path)
    if ext == ".csv":
        return load_particles_from_csv(path)
    raise ValueError(f"unsupported particles file extension: {ext} ({path})")


def _resolve_output_paths(
    output_dir: Optional[str],
    micrograph_path: str,
) -> Tuple[str, str, str]:
    """Pick output ``.mrcs`` / ``.star`` / ``.json`` paths.

    If ``output_dir`` is set, write all three under that directory using
    the micrograph stem as the base. Otherwise write next to the
    micrograph. ``TaskOutputProcessor`` may relocate these to
    session-keyed paths post-projection (Phase 4 follow-up).
    """
    stem = Path(micrograph_path).stem
    base_dir = output_dir or os.path.dirname(os.path.abspath(micrograph_path))
    os.makedirs(base_dir, exist_ok=True)
    return (
        os.path.join(base_dir, f"{stem}_particles.mrcs"),
        os.path.join(base_dir, f"{stem}_particles.star"),
        os.path.join(base_dir, f"{stem}_particles.json"),
    )


def _maybe_load_ctf(ctf_path: Optional[str], micrograph_name: str) -> Optional[Dict[str, Any]]:
    """If a CTF JSON is provided, build a single-entry lookup keyed on
    the micrograph name (matching what build_and_write expects)."""
    if not ctf_path:
        return None
    with open(ctf_path) as handle:
        ctf = json.load(handle)
    if not isinstance(ctf, dict):
        raise ValueError(f"ctf JSON at {ctf_path} must be an object")
    return {micrograph_name: ctf}


def extract_particles(
    *,
    micrograph_path: str,
    particles_path: str,
    box_size: int,
    edge_width: int = 2,
    apix: Optional[float] = None,
    output_dir: Optional[str] = None,
    ctf_path: Optional[str] = None,
    allow_partial: bool = True,
) -> Dict[str, Any]:
    """End-to-end extraction. Returns a dict with output paths +
    particle count for the plugin's result factory to consume."""
    micrograph = _load_micrograph(micrograph_path)
    particles = _load_particles(particles_path)

    micrograph_name = os.path.basename(micrograph_path)
    mrcs_path, star_path, json_path = _resolve_output_paths(output_dir, micrograph_path)

    ctf_lookup = _maybe_load_ctf(ctf_path, micrograph_name)

    config = ParticleStackConfig(
        box_size=box_size,
        edge_width=edge_width,
        allow_partial=allow_partial,
        micrograph_pixel_size_angstrom=apix,
        image_name=micrograph_name,
        ctf_lookup=ctf_lookup,
    )

    summary = build_and_write(
        micrograph=micrograph,
        particles=particles,
        config=config,
        star_output=star_path,
        json_output=json_path,
        stack_output=mrcs_path,
    )

    return {
        "mrcs_path": mrcs_path,
        "star_path": star_path,
        "json_path": json_path,
        "particle_count": summary["count"],
        "micrograph_name": micrograph_name,
    }
