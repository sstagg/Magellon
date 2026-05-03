"""CAN classifier compute glue.

Phase 7b (2026-05-03) vendors the algorithm; this module owns the
plumbing around it: STAR parsing, per-particle MRC reads, preprocess,
align+CAN, and output writing.

Bus carries refs only (rule 1, project_artifact_bus_invariants.md):
the input ``mrcs_path`` / ``star_path`` are paths on the data plane;
the output ``class_averages_path`` etc. are paths too. Scalar
summaries (``num_classes_emitted``, ``num_particles_classified``,
``apix``) ride on the result envelope.

GPU-acceleration deps (torch, scikit-image) are loaded lazily inside
the algorithm; this module is import-clean against numpy + scipy +
mrcfile only, so plugin contract tests run without them. Production
deployments install the full stack via the plugin's requirements.txt /
CUDA Dockerfile.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RELION STAR + per-particle MRC reader
# ---------------------------------------------------------------------------
# Small, self-contained — copied from Sandbox/magellon_can_classifier/cli.py
# (Phase 7b vendoring). The CLI's argparse + main loop are NOT vendored;
# the plugin runs from a TaskMessage so the orchestration is here.


def _parse_relion_star_tables(path: str) -> Dict[str, List[Dict[str, str]]]:
    """Parse a RELION STAR file into named tables ('data_particles',
    'data_optics', ...). Tolerates loop_ blocks; ignores comments."""
    lines = Path(path).read_text().splitlines()
    tables: Dict[str, List[Dict[str, str]]] = {}
    current_block = ""
    labels: List[str] = []
    in_loop = False
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("data_"):
            current_block = line.strip()
            in_loop = False
            labels = []
            tables.setdefault(current_block, [])
            continue
        if line == "loop_":
            in_loop = True
            labels = []
            continue
        if in_loop and line.startswith("_"):
            labels.append(line.split()[0])
            continue
        if in_loop and labels:
            vals = line.split()
            if len(vals) < len(labels):
                continue
            row = {labels[i]: vals[i] for i in range(len(labels))}
            tables.setdefault(current_block, []).append(row)
    return tables


def _resolve_image_path(star_path: str, image_name: str) -> Tuple[str, int]:
    """Parse RELION ``NNNNNN@stack.mrcs`` token → (abs path, 0-based index).

    The phase 5 stack-maker fix emits this canonical RELION order
    (NNNNNN@stack.mrcs); the inverse-order original was the integration
    bug called out in MAGELLON_PARTICLE_PIPELINE.md.
    """
    if "@" not in image_name:
        raise RuntimeError(f"Unsupported _rlnImageName format: {image_name}")
    idx_txt, rel = image_name.split("@", 1)
    idx0 = int(idx_txt) - 1
    abs_path = str((Path(star_path).parent / rel).resolve())
    return abs_path, idx0


def _derive_apix_from_star(
    particle_rows: List[Dict[str, str]],
    optics_rows: List[Dict[str, str]],
) -> Optional[float]:
    """Pull pixel size from the STAR — particle column first, optics
    fallback. Phase 5's stack-maker fix writes ``_rlnImagePixelSize``
    (what RELION expects), not the legacy ``_rlnPixelSize``."""
    pixvals: List[float] = []
    for row in particle_rows:
        v = row.get("_rlnImagePixelSize")
        if v is not None:
            try:
                pixvals.append(float(v))
            except ValueError:
                pass
    if pixvals:
        return float(np.median(np.asarray(pixvals, dtype=np.float32)))

    if optics_rows:
        group_to_apix: Dict[str, float] = {}
        for row in optics_rows:
            grp = row.get("_rlnOpticsGroup")
            ap = row.get("_rlnImagePixelSize")
            if grp is not None and ap is not None:
                try:
                    group_to_apix[str(grp)] = float(ap)
                except ValueError:
                    pass
        vals: List[float] = []
        for row in particle_rows:
            grp = row.get("_rlnOpticsGroup")
            if grp is not None and str(grp) in group_to_apix:
                vals.append(group_to_apix[str(grp)])
        if vals:
            return float(np.median(np.asarray(vals, dtype=np.float32)))
    return None


def _load_particles_from_star(
    star_path: str,
    max_particles: Optional[int] = None,
) -> Tuple[np.ndarray, Optional[float]]:
    """Load all particles referenced by ``star_path`` into one 3D ndarray
    [N, Y, X], plus the derived pixel size. Caches per-stack opens."""
    import mrcfile  # lazy

    tables = _parse_relion_star_tables(star_path)
    rows = tables.get("data_particles", [])
    if not rows:
        raise RuntimeError(f"No particle rows found in STAR: {star_path}")
    optics_rows = tables.get("data_optics", [])

    if max_particles is not None:
        rows = rows[: int(max_particles)]

    apix = _derive_apix_from_star(rows, optics_rows)

    stack_cache: Dict[str, np.ndarray] = {}
    particles: List[np.ndarray] = []
    for row in rows:
        imgname = row.get("_rlnImageName")
        if imgname is None:
            raise RuntimeError(f"STAR row missing _rlnImageName: {row}")
        stack_path, idx0 = _resolve_image_path(star_path, imgname)
        if stack_path not in stack_cache:
            with mrcfile.open(stack_path, permissive=True) as m:
                stack_cache[stack_path] = np.asarray(m.data, dtype=np.float32, order="C")
        stack = stack_cache[stack_path]
        if stack.ndim == 2:
            # Single-particle stack (unusual but valid).
            arr = stack
        elif stack.ndim == 3:
            if idx0 < 0 or idx0 >= stack.shape[0]:
                raise RuntimeError(
                    f"Particle index {idx0+1} out of range for stack {stack_path} "
                    f"(N={stack.shape[0]})"
                )
            arr = stack[idx0]
        else:
            raise RuntimeError(f"unsupported stack dim {stack.ndim} at {stack_path}")
        particles.append(arr)

    if not particles:
        raise RuntimeError(f"Loaded 0 particles from {star_path}")
    return np.stack(particles, axis=0).astype(np.float32, copy=False), apix


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_mrcs(stack: np.ndarray, path: str) -> None:
    import mrcfile  # lazy

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with mrcfile.new(path, overwrite=True) as m:
        m.set_data(stack.astype(np.float32, copy=False))


def _write_assignments_csv(
    path: str,
    *,
    rotations: np.ndarray,
    shifts: np.ndarray,
    ref_assign: np.ndarray,
    ref_scores: np.ndarray,
) -> None:
    """One row per particle: index, mra_assignment, rotation, shift_y,
    shift_x, mra_score. Index is 0-based to match the algorithm's
    output arrays; downstream readers can offset."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["particle_index", "mra_assignment", "rotation_deg",
             "shift_y", "shift_x", "mra_score"]
        )
        n = int(rotations.shape[0])
        for i in range(n):
            w.writerow([
                i,
                int(ref_assign[i]),
                float(rotations[i]),
                float(shifts[i, 0]),
                float(shifts[i, 1]),
                float(ref_scores[i]) if np.isfinite(ref_scores[i]) else "",
            ])


def _write_class_counts_csv(path: str, counts: np.ndarray) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["class_id", "count"])
        for cid, c in enumerate(counts.tolist()):
            w.writerow([int(cid), int(c)])


def _write_run_summary(
    path: str,
    *,
    num_classes_emitted: int,
    num_particles_classified: int,
    apix: Optional[float],
    align_iters: int,
    iteration_history: list,
    output_dir: str,
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(
            {
                "num_classes_emitted": num_classes_emitted,
                "num_particles_classified": num_particles_classified,
                "apix": apix,
                "align_iters": align_iters,
                "iteration_history": iteration_history,
                "output_dir": output_dir,
            },
            f,
            indent=2,
        )


# ---------------------------------------------------------------------------
# Public API consumed by plugin.execute()
# ---------------------------------------------------------------------------


def classify_stack(
    *,
    mrcs_path: str,
    star_path: str,
    output_dir: str,
    apix: Optional[float],
    num_classes: int,
    num_presentations: int,
    align_iters: int,
    threads: int,
    can_threads: int,
    compute_backend: str,
    max_particles: Optional[int],
    invert: bool,
    write_aligned_stack: bool,
    engine_opts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """End-to-end CAN classification of one particle stack.

    Loads particles via the STAR (handles multi-stack lookups via
    ``NNNNNN@stack.mrcs`` tokens), preprocesses, runs the topology
    loop (CAN → MRA per iteration), and writes outputs to
    ``output_dir``. Returns a summary dict the plugin's result
    factory consumes.

    The heavy algorithm imports (torch / scikit-image) live inside
    :mod:`plugin.algorithm.classifier`; this function is import-clean
    against numpy + scipy + mrcfile alone.
    """
    # Lazy imports so the plugin contract tests don't need the
    # algorithm runtime installed.
    from plugin.algorithm import (
        CanParams,
        class_half_averages,
        preprocess_stack,
        run_align_and_can,
    )

    opts = engine_opts or {}
    seed = int(opts.get("seed", 0))
    # CAN learning rates — names mirror the Sandbox CLI defaults.
    # ``learn`` is the primary (winner) learning rate; ``ilearn`` is
    # the neighbour rate (slower).
    primary_learn = float(opts.get("learn", 0.01))
    secondary_learn = float(opts.get("ilearn", 0.0005))
    max_age = int(opts.get("max_age", 200))
    lowpass_resolution = opts.get("lowpass_resolution")
    fft_scale = float(opts.get("fft_scale", 1.0))
    phase_flip_ctf = bool(opts.get("phase_flip_ctf", False))
    center_particles = bool(opts.get("center_particles", True))
    normalize = bool(opts.get("normalize", True))

    # Load particles + derive apix if not supplied.
    raw_stack, derived_apix = _load_particles_from_star(
        star_path, max_particles=max_particles
    )
    effective_apix = float(apix if apix is not None else (derived_apix or 1.0))
    logger.info(
        "classify_stack: loaded %d particles from %s (apix=%.4f)",
        raw_stack.shape[0], star_path, effective_apix,
    )

    # Preprocess (centering / normalize / lowpass / fft scaling /
    # phase flipping). Heavy lifting delegated to the algorithm.
    pre = preprocess_stack(
        raw_stack,
        apix=effective_apix,
        invert=invert,
        center=center_particles,
        normalize=normalize,
        lowpass_resolution=(
            float(lowpass_resolution) if lowpass_resolution is not None else None
        ),
        fft_scale=fft_scale,
        phase_flip_ctf=phase_flip_ctf,
        n_threads=int(threads),
    )

    # Run topology loop.
    can_params = CanParams(
        num_classes=int(num_classes),
        num_presentations=int(num_presentations),
        primary_learn=primary_learn,
        secondary_learn=secondary_learn,
        max_age=max_age,
        can_threads=int(can_threads),
        compute_backend=str(compute_backend),
    )
    result = run_align_and_can(
        preprocessed_stack=pre,
        apix=effective_apix * fft_scale,
        align_iters=int(align_iters),
        can_params=can_params,
        seed=seed,
        verbose=False,
        n_threads=int(threads),
        include_aligned_stack=write_aligned_stack,
        work_dir=output_dir,
    )

    # Write outputs.
    os.makedirs(output_dir, exist_ok=True)
    class_averages_path = os.path.join(output_dir, "class_averages.mrcs")
    assignments_csv_path = os.path.join(output_dir, "assignments.csv")
    class_counts_csv_path = os.path.join(output_dir, "class_counts.csv")
    run_summary_path = os.path.join(output_dir, "run_summary.json")
    iteration_history_path = os.path.join(output_dir, "iteration_history.json")

    class_averages = np.asarray(result["class_averages"], dtype=np.float32)
    _write_mrcs(class_averages, class_averages_path)
    _write_class_counts_csv(class_counts_csv_path, np.asarray(result["class_counts"]))
    _write_assignments_csv(
        assignments_csv_path,
        rotations=np.asarray(result["rotations"]),
        shifts=np.asarray(result["shifts"]),
        ref_assign=np.asarray(result["mra_reference_assignments"]),
        ref_scores=np.asarray(result["mra_reference_scores"]),
    )
    _write_run_summary(
        run_summary_path,
        num_classes_emitted=int(class_averages.shape[0]),
        num_particles_classified=int(pre.shape[0]),
        apix=effective_apix,
        align_iters=int(align_iters),
        iteration_history=list(result.get("iteration_history") or []),
        output_dir=output_dir,
    )
    with open(iteration_history_path, "w") as f:
        json.dump(list(result.get("iteration_history") or []), f, indent=2)

    aligned_stack_path: Optional[str] = None
    if write_aligned_stack and "aligned_stack" in result:
        aligned_stack_path = os.path.join(output_dir, "aligned_stack.mrcs")
        _write_mrcs(np.asarray(result["aligned_stack"], dtype=np.float32), aligned_stack_path)

    return {
        "class_averages_path": class_averages_path,
        "assignments_csv_path": assignments_csv_path,
        "class_counts_csv_path": class_counts_csv_path,
        "run_summary_path": run_summary_path,
        "iteration_history_path": iteration_history_path,
        "aligned_stack_path": aligned_stack_path,
        "num_classes_emitted": int(class_averages.shape[0]),
        "num_particles_classified": int(pre.shape[0]),
        "apix": effective_apix,
        "output_dir": output_dir,
    }
