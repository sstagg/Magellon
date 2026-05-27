"""Particle extraction (stack maker) — wires the algorithm to the SDK.

Single micrograph + particle coordinates → ``.mrcs`` stack + ``.star`` +
companion ``.json``. Pure-numpy compute path, no broker awareness.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import mrcfile
import numpy as np

from plugin.algorithm import (
    ParticleStackConfig,
    _as_particle_coords,
    create_particle_stack,
    build_and_write,
    build_particle_records,
    load_particles_from_csv,
    load_particles_from_json,
    write_json_output,
    write_relion_star,
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


def _resolve_output_paths_for_stem(
    output_dir: Optional[str],
    base_path: str,
    stem: str,
) -> Tuple[str, str, str]:
    base_dir = output_dir or os.path.dirname(os.path.abspath(base_path))
    os.makedirs(base_dir, exist_ok=True)
    return (
        os.path.join(base_dir, f"{stem}.mrcs"),
        os.path.join(base_dir, f"{stem}.star"),
        os.path.join(base_dir, f"{stem}.json"),
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


def _load_batch_manifest(path: str) -> List[Dict[str, Any]]:
    with open(path) as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        items = data.get("items") or data.get("micrographs") or data.get("inputs")
    else:
        items = data
    if not isinstance(items, list) or not items:
        raise ValueError("batch manifest must be a non-empty list or contain items/micrographs")
    normalized: List[Dict[str, Any]] = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"batch manifest item {i} must be an object")
        micrograph_path = item.get("micrograph_path") or item.get("image_path")
        particles_path = item.get("particles_path") or item.get("picks_path")
        if not micrograph_path or not particles_path:
            raise ValueError(
                f"batch manifest item {i} requires micrograph_path and particles_path"
            )
        normalized.append({
            "micrograph_path": str(micrograph_path),
            "particles_path": str(particles_path),
            "ctf_path": item.get("ctf_path"),
            "micrograph_name": item.get("micrograph_name") or os.path.basename(str(micrograph_path)),
        })
    return normalized


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
        "source_micrograph_count": 1,
    }


def extract_particles_batch(
    *,
    batch_manifest_path: str,
    box_size: int,
    edge_width: int = 2,
    apix: Optional[float] = None,
    output_dir: Optional[str] = None,
    allow_partial: bool = True,
    output_stem: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract one aggregate particle stack from many micrograph/picks pairs."""
    items = _load_batch_manifest(batch_manifest_path)
    stem = output_stem or Path(batch_manifest_path).stem or "particle_stack"
    mrcs_path, star_path, json_path = _resolve_output_paths_for_stem(
        output_dir, batch_manifest_path, stem,
    )

    all_rows = []
    for item in items:
        micrograph_path = item["micrograph_path"]
        particles_path = item["particles_path"]
        micrograph_name = item["micrograph_name"]

        micrograph = _load_micrograph(micrograph_path)
        particles = _load_particles(particles_path)
        ctf_lookup = _maybe_load_ctf(item.get("ctf_path"), micrograph_name)
        config = ParticleStackConfig(
            box_size=box_size,
            edge_width=edge_width,
            allow_partial=allow_partial,
            micrograph_pixel_size_angstrom=apix,
            image_name=micrograph_name,
            ctf_lookup=ctf_lookup,
        )
        rows = build_particle_records(
            micrograph=micrograph,
            coordinates=_as_particle_coords(particles),
            config=config,
        )
        for row in rows:
            all_rows.append(replace(row, index=len(all_rows) + 1))

    if all_rows:
        create_particle_stack(all_rows, mrcs_path)
    write_relion_star(
        rows=all_rows,
        output_path=star_path,
        stack_path=mrcs_path,
        micrograph_pixel_size_angstrom=apix,
    )
    write_json_output(rows=all_rows, output_path=json_path)

    return {
        "mrcs_path": mrcs_path,
        "star_path": star_path,
        "json_path": json_path,
        "particle_count": len(all_rows),
        "micrograph_name": stem,
        "source_micrograph_path": batch_manifest_path,
        "source_micrograph_count": len(items),
    }
