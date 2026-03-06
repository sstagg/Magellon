#!/usr/bin/env python

from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

try:
    # Package mode: python -m magellon_can_classifier
    from .classifier import (
        _fft_scale_image,
        CanParams,
        frc_curve,
        frc_resolution,
        make_replayed_class_averages_with_halves,
        preprocess_stack,
        run_align_and_can,
    )
except ImportError:
    # Script mode: python cli.py
    from classifier import (
        _fft_scale_image,
        CanParams,
        frc_curve,
        frc_resolution,
        make_replayed_class_averages_with_halves,
        preprocess_stack,
        run_align_and_can,
    )

try:
    import mrcfile
except Exception as exc:  # pragma: no cover
    mrcfile = None
    _mrc_import_error = exc
else:
    _mrc_import_error = None


def _require_mrcfile() -> None:
    if mrcfile is None:
        raise RuntimeError(
            "mrcfile is required for stack I/O. Install with: pip install mrcfile "
            f"(import error: {_mrc_import_error})"
        )


def _read_stack(path: str) -> np.ndarray:
    _require_mrcfile()
    with mrcfile.open(path, permissive=True) as m:
        data = np.asarray(m.data, dtype=np.float32)
    if data.ndim == 2:
        data = data[None, ...]
    if data.ndim != 3:
        raise ValueError(f"Expected 3D stack in {path}, got shape {data.shape}")
    return data


def _write_stack(path: str, data: np.ndarray) -> None:
    _require_mrcfile()
    arr = np.asarray(data, dtype=np.float32)
    with mrcfile.new(path, overwrite=True) as m:
        m.set_data(arr)


def _write_frc_outputs(
    half1: np.ndarray,
    half2: np.ndarray,
    half_counts: np.ndarray,
    apix: float,
    outdir: str,
    prefix: str,
) -> str:
    os.makedirs(outdir, exist_ok=True)
    summary_path = os.path.join(outdir, f"{prefix}_frc_summary.csv")
    with open(summary_path, "w", newline="") as sf:
        sw = csv.writer(sf)
        sw.writerow(["class_index_0based", "half1_count", "half2_count", "res_0.5_A", "res_0.143_A"])
        for c in range(int(half1.shape[0])):
            n1 = int(half_counts[c, 0]) if half_counts.ndim == 2 else 0
            n2 = int(half_counts[c, 1]) if half_counts.ndim == 2 else 0
            curve_path = os.path.join(outdir, f"{prefix}_class_{c:03d}_frc.csv")
            if n1 > 0 and n2 > 0:
                freq, res, frc = frc_curve(half1[c], half2[c], apix=apix)
                with open(curve_path, "w", newline="") as cf:
                    cw = csv.writer(cf)
                    cw.writerow(["freq_1_per_A", "resolution_A", "frc"])
                    for i in range(freq.size):
                        cw.writerow([float(freq[i]), float(res[i]), float(frc[i])])
                r05 = frc_resolution(freq, frc, 0.5)
                r0143 = frc_resolution(freq, frc, 0.143)
                sw.writerow([c, n1, n2, r05 if r05 is not None else "", r0143 if r0143 is not None else ""])
            else:
                with open(curve_path, "w", newline="") as cf:
                    cw = csv.writer(cf)
                    cw.writerow(["freq_1_per_A", "resolution_A", "frc"])
                sw.writerow([c, n1, n2, "", ""])
    return summary_path


def _write_iteration_alignment_json(path: str, assignments: np.ndarray, rotations: np.ndarray, shifts: np.ndarray, scores: np.ndarray) -> None:
    rows = []
    n = int(assignments.size)
    for i in range(n):
        rows.append(
            {
                "particle_index_0based": int(i),
                "class_index_0based": int(assignments[i]),
                "rotation_degrees": float(rotations[i]),
                "shift_y_px": float(shifts[i, 0]),
                "shift_x_px": float(shifts[i, 1]),
                "score": float(scores[i]) if scores.size == n else None,
            }
        )
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)


def _write_iteration_alignment_star(path: str, assignments: np.ndarray, rotations: np.ndarray, shifts: np.ndarray, scores: np.ndarray) -> None:
    n = int(assignments.size)
    with open(path, "w") as f:
        f.write("data_particles\n\n")
        f.write("loop_\n")
        f.write("_magParticleIndex #1\n")
        f.write("_rlnClassNumber #2\n")
        f.write("_rlnAnglePsi #3\n")
        f.write("_rlnOriginX #4\n")
        f.write("_rlnOriginY #5\n")
        f.write("_rlnCtfFigureOfMerit #6\n")
        for i in range(n):
            cls_1based = int(assignments[i]) + 1
            ang = float(rotations[i])
            sx = float(shifts[i, 1])
            sy = float(shifts[i, 0])
            score = float(scores[i]) if scores.size == n else 0.0
            f.write(f"{i} {cls_1based} {ang:.6f} {sx:.6f} {sy:.6f} {score:.6f}\n")


def _nearest_even_box_for_target_apix(box_size: int, apix: float, target_apix: float) -> tuple[int, float]:
    """
    Pick an even output box size that yields apix_new = apix * box / new_box
    as close as possible to target_apix.
    Returns (new_box, fft_scale), where fft_scale = new_box / box_size.
    """
    b = int(box_size)
    if b <= 2:
        return b, 1.0
    target = float(target_apix)
    if target <= 1e-8:
        return b, 1.0
    ideal = (float(apix) * float(b)) / target
    c0 = int(round(ideal))
    cands = set()
    for d in range(-4, 5):
        x = max(2, c0 + d)
        if x % 2 != 0:
            x += 1
        cands.add(x)
    best_box = b
    best_err = abs(float(apix) * float(b) / float(best_box) - target)
    for nb in sorted(cands):
        apix_new = float(apix) * float(b) / float(nb)
        err = abs(apix_new - target)
        if err < best_err:
            best_err = err
            best_box = nb
    return int(best_box), float(best_box) / float(b)


def _best_resolution_from_frc_summary(summary_csv: str) -> float | None:
    best = None
    with open(summary_csv, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            txt = row.get("res_0.143_A", "") or row.get("res_0.5_A", "")
            if txt == "":
                continue
            try:
                v = float(txt)
            except Exception:
                continue
            if v <= 0:
                continue
            if best is None or v < best:
                best = v
    return best


def _parse_relion_star_tables(path: str) -> dict[str, list[dict[str, str]]]:
    lines = Path(path).read_text().splitlines()
    tables: dict[str, list[dict[str, str]]] = {}
    current_block = ""
    labels: list[str] = []
    in_loop = False
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("data_"):
            current_block = line.strip()
            in_loop = False
            labels = []
            if current_block not in tables:
                tables[current_block] = []
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


def _resolve_image_path(star_path: str, image_name: str) -> tuple[str, int]:
    if "@" not in image_name:
        raise RuntimeError(f"Unsupported _rlnImageName format: {image_name}")
    idx_txt, rel = image_name.split("@", 1)
    idx0 = int(idx_txt) - 1
    abs_path = str((Path(star_path).parent / rel).resolve())
    return abs_path, idx0


def _derive_star_apix(
    particle_rows: list[dict[str, str]],
    optics_rows: list[dict[str, str]],
) -> float | None:
    pixvals = []
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
        group_to_apix: dict[str, float] = {}
        for row in optics_rows:
            grp = row.get("_rlnOpticsGroup")
            ap = row.get("_rlnImagePixelSize")
            if grp is not None and ap is not None:
                try:
                    group_to_apix[str(grp)] = float(ap)
                except ValueError:
                    pass
        vals = []
        for row in particle_rows:
            grp = row.get("_rlnOpticsGroup")
            if grp is not None and str(grp) in group_to_apix:
                vals.append(group_to_apix[str(grp)])
        if vals:
            return float(np.median(np.asarray(vals, dtype=np.float32)))
    return None


def _read_stack_particles_from_star(
    star_path: str,
    max_particles: int | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, float | None], float | None]:
    _require_mrcfile()
    tables = _parse_relion_star_tables(star_path)
    rows = tables.get("data_particles", [])
    if not rows:
        raise RuntimeError(f"No particle rows found in STAR: {star_path}")
    optics_rows = tables.get("data_optics", [])

    # cache stacks by path
    stack_cache: dict[str, np.ndarray] = {}
    optics_lookup: dict[str, dict[str, str]] = {}
    for o in optics_rows:
        grp = o.get("_rlnOpticsGroup")
        if grp is not None:
            optics_lookup[str(grp)] = o

    def _get_ctf_value(row: dict[str, str], key: str) -> float | None:
        if key in row:
            try:
                return float(row[key])
            except ValueError:
                return None
        grp = row.get("_rlnOpticsGroup")
        if grp is not None and str(grp) in optics_lookup and key in optics_lookup[str(grp)]:
            try:
                return float(optics_lookup[str(grp)][key])
            except ValueError:
                return None
        return None

    particles: list[np.ndarray] = []
    defocus_u: list[float] = []
    defocus_v: list[float] = []
    voltage: list[float] = []
    cs: list[float] = []
    amp: list[float] = []

    if max_particles is not None:
        rows = rows[: int(max_particles)]

    for row in rows:
        imgname = row.get("_rlnImageName")
        if imgname is None:
            raise RuntimeError("STAR missing _rlnImageName")
        stack_path, idx0 = _resolve_image_path(star_path, imgname)
        if stack_path not in stack_cache:
            stack_cache[stack_path] = _read_stack(stack_path)
        stack = stack_cache[stack_path]
        if idx0 < 0 or idx0 >= stack.shape[0]:
            raise RuntimeError(f"Particle index out of bounds: {imgname}")
        particles.append(stack[idx0])
        du = _get_ctf_value(row, "_rlnDefocusU")
        dv = _get_ctf_value(row, "_rlnDefocusV")
        defocus_u.append(0.0 if du is None else float(du))
        defocus_v.append(0.0 if dv is None else float(dv))
        vv = _get_ctf_value(row, "_rlnVoltage")
        cc = _get_ctf_value(row, "_rlnSphericalAberration")
        aa = _get_ctf_value(row, "_rlnAmplitudeContrast")
        if vv is not None:
            voltage.append(vv)
        if cc is not None:
            cs.append(cc)
        if aa is not None:
            amp.append(aa)

    ctf_per_particle = {
        "defocus_u_angstrom": np.asarray(defocus_u, dtype=np.float32),
        "defocus_v_angstrom": np.asarray(defocus_v, dtype=np.float32),
    }
    ctf_defaults = {
        "voltage_kv": float(np.median(voltage)) if voltage else None,
        "cs_mm": float(np.median(cs)) if cs else None,
        "amp_contrast": float(np.median(amp)) if amp else None,
    }
    apix = _derive_star_apix(rows, optics_rows)
    return np.stack(particles).astype(np.float32), ctf_per_particle, ctf_defaults, apix


def _index_particles_from_star(
    star_path: str,
    max_particles: int | None = None,
) -> tuple[list[tuple[str, int]], dict[str, np.ndarray], dict[str, float | None], float | None, tuple[int, int]]:
    """
    Parse STAR and return particle references (path + index), CTF arrays/defaults,
    derived apix, and raw particle box size without materializing a full stack.
    """
    _require_mrcfile()
    tables = _parse_relion_star_tables(star_path)
    rows = tables.get("data_particles", [])
    if not rows:
        raise RuntimeError(f"No particle rows found in STAR: {star_path}")
    optics_rows = tables.get("data_optics", [])
    if max_particles is not None:
        rows = rows[: int(max_particles)]
    if len(rows) == 0:
        raise RuntimeError("No particles selected after --max-particles filtering")

    optics_lookup: dict[str, dict[str, str]] = {}
    for o in optics_rows:
        grp = o.get("_rlnOpticsGroup")
        if grp is not None:
            optics_lookup[str(grp)] = o

    def _get_ctf_value(row: dict[str, str], key: str) -> float | None:
        if key in row:
            try:
                return float(row[key])
            except ValueError:
                return None
        grp = row.get("_rlnOpticsGroup")
        if grp is not None and str(grp) in optics_lookup and key in optics_lookup[str(grp)]:
            try:
                return float(optics_lookup[str(grp)][key])
            except ValueError:
                return None
        return None

    refs: list[tuple[str, int]] = []
    defocus_u: list[float] = []
    defocus_v: list[float] = []
    voltage: list[float] = []
    cs: list[float] = []
    amp: list[float] = []

    for row in rows:
        imgname = row.get("_rlnImageName")
        if imgname is None:
            raise RuntimeError("STAR missing _rlnImageName")
        stack_path, idx0 = _resolve_image_path(star_path, imgname)
        refs.append((stack_path, int(idx0)))
        du = _get_ctf_value(row, "_rlnDefocusU")
        dv = _get_ctf_value(row, "_rlnDefocusV")
        defocus_u.append(0.0 if du is None else float(du))
        defocus_v.append(0.0 if dv is None else float(dv))
        vv = _get_ctf_value(row, "_rlnVoltage")
        cc = _get_ctf_value(row, "_rlnSphericalAberration")
        aa = _get_ctf_value(row, "_rlnAmplitudeContrast")
        if vv is not None:
            voltage.append(vv)
        if cc is not None:
            cs.append(cc)
        if aa is not None:
            amp.append(aa)

    first_path, first_idx = refs[0]
    with mrcfile.open(first_path, permissive=True) as m:
        data = m.data
        if data.ndim == 2:
            if first_idx != 0:
                raise RuntimeError(f"First STAR index out of bounds for 2D stack: {first_idx}")
            box = (int(data.shape[0]), int(data.shape[1]))
        elif data.ndim == 3:
            if first_idx < 0 or first_idx >= data.shape[0]:
                raise RuntimeError(f"First STAR index out of bounds: {first_idx}")
            box = (int(data.shape[1]), int(data.shape[2]))
        else:
            raise RuntimeError(f"Unexpected stack dimensionality in {first_path}: {data.shape}")

    ctf_per_particle = {
        "defocus_u_angstrom": np.asarray(defocus_u, dtype=np.float32),
        "defocus_v_angstrom": np.asarray(defocus_v, dtype=np.float32),
    }
    ctf_defaults = {
        "voltage_kv": float(np.median(voltage)) if voltage else None,
        "cs_mm": float(np.median(cs)) if cs else None,
        "amp_contrast": float(np.median(amp)) if amp else None,
    }
    apix = _derive_star_apix(rows, optics_rows)
    return refs, ctf_per_particle, ctf_defaults, apix, box


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Standalone align + CAN classifier for particle stacks")
    p.add_argument("--star", default=None, help="Input Relion particle STAR file")
    p.add_argument("--stack", default=None, help="Input particle stack (.mrc/.mrcs); fallback if no --star")
    p.add_argument("--apix", type=float, default=None, help="Pixel size (A/pix); optional if present in STAR")
    p.add_argument("--outdir", default="can_output", help="Output directory")
    p.add_argument("--max-particles", type=int, default=None, help="Limit processing to first N particles")

    # preprocessing / alignment
    p.add_argument("--lowpass-resolution", type=float, default=None, help="Low-pass resolution (A)")
    p.add_argument(
        "--init-resolution",
        type=float,
        default=None,
        help="Deprecated with fixed-scaling mode. Kept for compatibility and currently unused.",
    )
    p.add_argument(
        "--fft-scale",
        type=float,
        default=1.0,
        help="Fourier-domain image scaling factor applied in preprocessing (e.g., 0.5 downsamples)",
    )
    p.add_argument("--invert", action="store_true", help="Invert particle contrast")
    p.add_argument("--no-center", action="store_true", help="Disable centering")
    p.add_argument("--no-normalize", action="store_true", help="Disable normalization")
    p.add_argument(
        "--no-center-averages",
        action="store_true",
        help="Disable class-average center-of-mass recentering before masking",
    )
    p.add_argument(
        "--particle-diameter-ang",
        type=float,
        default=None,
        help="Particle diameter in Angstrom. If set, apply circular mask to references/class averages at 1.25x diameter",
    )
    p.add_argument(
        "--align-iters",
        type=int,
        default=3,
        help="Number of full topology iterations (each iteration is CAN then MRA)",
    )
    p.add_argument(
        "--align-progress-every",
        type=int,
        default=250,
        help="Print alignment progress every N particles",
    )
    p.add_argument(
        "--mra-log-each-particle",
        action="store_true",
        help="Print per-particle MRA winner details (slower)",
    )
    p.add_argument(
        "--write-aligned-stack",
        action="store_true",
        help="Write aligned_stack.mrcs (disabled by default to reduce I/O on large runs)",
    )
    p.add_argument("--threads", type=int, default=1, help="Worker threads for per-particle preprocess/alignment")

    # CTF phase flip
    p.add_argument("--phase-flip-ctf", action="store_true", help="Apply CTF phase flipping")

    # CAN parameters
    p.add_argument("--num-classes", type=int, default=50, help="Target number of CAN classes")
    p.add_argument("--num-presentations", type=int, default=200000, help="CAN presentations/steps")
    p.add_argument("--learn", type=float, default=0.01, help="Primary learning rate")
    p.add_argument("--ilearn", type=float, default=0.0005, help="Neighbor learning rate")
    p.add_argument("--max-age", type=int, default=25, help="Max edge age")
    p.add_argument("--can-threads", type=int, default=1, help="Threads for CAN assignment/averaging stages")
    p.add_argument(
        "--compute-backend",
        type=str,
        default="cpu",
        choices=["cpu", "torch-auto", "torch-cuda", "torch-mps", "torch-cpu"],
        help="Compute backend for CAN math",
    )
    p.add_argument("--seed", type=int, default=0, help="Random seed")
    p.add_argument("--progress-every", type=int, default=5000, help="Print CAN progress every N steps")
    p.add_argument("--checkpoint-every", type=int, default=0, help="CAN checkpoint interval in presentations (0 disables)")
    p.add_argument(
        "--early-stop-assignment-delta",
        type=float,
        default=None,
        help="Early stop threshold for checkpoint assignment change fraction (e.g., 0.015)",
    )
    p.add_argument(
        "--early-stop-error-rel-improve",
        type=float,
        default=None,
        help="Early stop threshold for checkpoint mean winner-distance relative improvement (e.g., 0.01)",
    )
    p.add_argument("--early-stop-patience", type=int, default=0, help="Consecutive stable checkpoints required to stop")
    p.add_argument("--early-stop-min-presentations", type=int, default=0, help="Minimum presentations before early stop")
    p.add_argument("--quiet", action="store_true", help="Reduce stdout diagnostics")
    return p


def main() -> int:
    args = _build_parser().parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    verbose = not bool(args.quiet)
    if args.threads < 1:
        raise RuntimeError("--threads must be >= 1")
    if args.can_threads < 1:
        raise RuntimeError("--can-threads must be >= 1")

    if verbose:
        print("[cli] starting align+CAN run")
        print(f"[cli] outdir={os.path.abspath(args.outdir)}")
        print(f"[cli] threads={int(args.threads)}")
        print(f"[cli] can_threads={int(args.can_threads)}")
        print(f"[cli] align_progress_every={int(args.align_progress_every)}")

    if not args.star and not args.stack:
        raise RuntimeError("Provide --star or --stack")

    input_kind = "star" if args.star else "stack"
    input_path = os.path.abspath(args.star if args.star else args.stack)
    if not os.path.isfile(input_path):
        raise RuntimeError(f"Input file does not exist: {input_path}")


    # Build source accessors without materializing full particle stack in RAM.
    star_refs = None
    star_handles: dict[str, Any] = {}
    stack_handle = None
    if args.star:
        if verbose:
            print(f"[cli] indexing STAR: {args.star}")
        star_refs, star_ctf, star_ctf_defaults, star_apix, raw_box = _index_particles_from_star(
            args.star, max_particles=args.max_particles
        )
        n_particles = int(len(star_refs))

        def _load_raw_chunk(start: int, end: int) -> np.ndarray:
            out = np.zeros((end - start, raw_box[0], raw_box[1]), dtype=np.float32)
            for ii, pidx in enumerate(range(start, end)):
                sp, si = star_refs[pidx]
                if sp not in star_handles:
                    star_handles[sp] = mrcfile.mmap(sp, permissive=True)
                out[ii] = np.asarray(star_handles[sp].data[si], dtype=np.float32)
            return out

        def _close_raw_source() -> None:
            for h in star_handles.values():
                try:
                    h.close()
                except Exception:
                    pass
            star_handles.clear()
    else:
        _require_mrcfile()
        stack_handle = mrcfile.mmap(args.stack, permissive=True)
        sdata = stack_handle.data
        if sdata.ndim == 2:
            total_n = 1
            raw_box = (int(sdata.shape[0]), int(sdata.shape[1]))
        elif sdata.ndim == 3:
            total_n = int(sdata.shape[0])
            raw_box = (int(sdata.shape[1]), int(sdata.shape[2]))
        else:
            raise RuntimeError(f"Expected 2D/3D stack, got {sdata.shape}")
        n_particles = total_n if args.max_particles is None else min(total_n, int(args.max_particles))
        if n_particles <= 0:
            raise RuntimeError("No particles selected after --max-particles filtering")
        star_ctf = None
        star_ctf_defaults = {"voltage_kv": 300.0, "cs_mm": 2.7, "amp_contrast": 0.1}
        star_apix = None

        def _load_raw_chunk(start: int, end: int) -> np.ndarray:
            if sdata.ndim == 2:
                if start != 0 or end != 1:
                    raise RuntimeError("2D stack only supports one particle")
                return np.asarray(sdata, dtype=np.float32)[None, :, :]
            return np.asarray(sdata[start:end], dtype=np.float32)

        def _close_raw_source() -> None:
            try:
                stack_handle.close()
            except Exception:
                pass

    if args.apix is not None:
        apix = float(args.apix)
    elif star_apix is not None:
        apix = float(star_apix)
    else:
        raise RuntimeError("Pixel size not provided: pass --apix or include _rlnImagePixelSize in STAR")

    if verbose:
        print(f"[cli] particles={n_particles} box={raw_box[0]}x{raw_box[1]} apix={apix:.5f}")
        print(f"[cli] fft_scale={float(args.fft_scale):.5f}")

    if args.phase_flip_ctf and not args.star:
        raise RuntimeError("phase-flip-ctf requires --star so CTF is read from STAR metadata")

    defocus = None
    ctf_voltage = None
    ctf_cs = None
    ctf_amp = None
    if args.phase_flip_ctf:
        # Relion defocus is in Angstrom; convert avg(U,V) to micrometers.
        u = star_ctf["defocus_u_angstrom"]
        v = star_ctf["defocus_v_angstrom"]
        defocus = ((u + v) * 0.5 / 1.0e4).astype(np.float32)
        if np.all(defocus == 0):
            raise RuntimeError("STAR is missing valid _rlnDefocusU/_rlnDefocusV for phase flipping")
        ctf_voltage = star_ctf_defaults["voltage_kv"]
        ctf_cs = star_ctf_defaults["cs_mm"]
        ctf_amp = star_ctf_defaults["amp_contrast"]
        if ctf_voltage is None or ctf_cs is None or ctf_amp is None:
            raise RuntimeError(
                "STAR is missing CTF metadata (_rlnVoltage, _rlnSphericalAberration, _rlnAmplitudeContrast)"
            )
    if verbose and args.phase_flip_ctf:
        print(
            f"[cli] phase-flip CTF from STAR: defocus_um median={float(np.median(defocus)):.4f} "
            f"range=({float(defocus.min()):.4f},{float(defocus.max()):.4f}) "
            f"voltage={ctf_voltage}kV cs={ctf_cs}mm amp={ctf_amp}"
        )

    can_params = CanParams(
        num_presentations=int(args.num_presentations),
        primary_learn=float(args.learn),
        secondary_learn=float(args.ilearn),
        max_age=int(args.max_age),
        num_classes=int(args.num_classes),
        progress_every=int(args.progress_every),
        can_threads=int(args.can_threads),
        compute_backend=str(args.compute_backend),
        checkpoint_every=int(args.checkpoint_every),
        early_stop_assignment_delta=args.early_stop_assignment_delta,
        early_stop_error_rel_improve=args.early_stop_error_rel_improve,
        early_stop_patience=int(args.early_stop_patience),
        early_stop_min_presentations=int(args.early_stop_min_presentations),
    )
    if verbose:
        print(f"[cli] CAN params: {can_params}")

    iter_pad = max(3, len(str(max(1, int(args.align_iters)))))
    fixed_scale = float(args.fft_scale)
    if fixed_scale <= 0:
        raise RuntimeError("--fft-scale must be > 0")
    if args.init_resolution is not None and verbose:
        print(
            f"[cli] --init-resolution is deprecated for this workflow and ignored; "
            f"using fixed --fft-scale={fixed_scale:.4f} every iteration"
        )
    n_iters = int(args.align_iters)
    n_start = min(5000, int(n_particles))
    if n_iters <= 1:
        iter_counts = [int(n_particles)]
    else:
        iter_counts = []
        for i in range(n_iters):
            f = float(i) / float(max(1, n_iters - 1))
            iter_counts.append(int(round(n_start + f * (int(n_particles) - n_start))))
        iter_counts[-1] = int(n_particles)
        for i in range(1, len(iter_counts)):
            iter_counts[i] = max(iter_counts[i], iter_counts[i - 1])

    raw_chunk_size = max(64, min(2048, int(max(64, 4_000_000 // max(1, raw_box[0] * raw_box[1])))))
    can_init_nodes = None
    out = None
    effective_apix = float(apix)
    pre_path = os.path.join(args.outdir, "preprocessed_stack.mrcs")

    raw_box_n = int(raw_box[0])
    iter_scale = fixed_scale

    for it in range(1, n_iters + 1):
        n_use = int(iter_counts[it - 1])
        effective_apix = float(apix) / float(iter_scale) if abs(float(iter_scale)) > 1e-12 else float(apix)
        if it == n_iters:
            pre_path = os.path.join(args.outdir, "preprocessed_stack.mrcs")
            cleanup_pre_path = False
        else:
            tmp = tempfile.NamedTemporaryFile(
                prefix=f"preprocessed_iter{it:0{iter_pad}d}_",
                suffix=".mrcs",
                dir=args.outdir,
                delete=False,
            )
            pre_path = tmp.name
            tmp.close()
            cleanup_pre_path = True
        if verbose:
            print(
                f"[cli] iter {it}/{n_iters}: n_particles={n_use} scale={iter_scale:.4f} effective_apix={effective_apix:.5f}"
            )
            print(f"[cli] iter {it}/{n_iters}: preprocessing -> {pre_path}")

        # Build this iteration's preprocessed stack (subset + chosen Fourier scale).
        raw0 = _load_raw_chunk(0, 1)
        def0 = defocus[0:1] if defocus is not None else None
        pre0 = preprocess_stack(
            stack=raw0,
            apix=apix,
            fft_scale=float(iter_scale),
            lowpass_resolution=None,
            invert=bool(args.invert),
            center=not bool(args.no_center),
            normalize=not bool(args.no_normalize),
            phase_flip_ctf=bool(args.phase_flip_ctf),
            ctf_defocus_um=def0,
            ctf_voltage_kv=ctf_voltage if ctf_voltage is not None else 300.0,
            ctf_cs_mm=ctf_cs if ctf_cs is not None else 2.7,
            ctf_amp_contrast=ctf_amp if ctf_amp is not None else 0.1,
            n_threads=int(args.threads),
        )
        pre_box = (int(pre0.shape[1]), int(pre0.shape[2]))
        with mrcfile.new_mmap(pre_path, shape=(n_use, pre_box[0], pre_box[1]), mrc_mode=2, overwrite=True) as pre_out:
            pre_out.data[0:1] = pre0
            for start in range(1, n_use, raw_chunk_size):
                end = min(n_use, start + raw_chunk_size)
                raw_chunk = _load_raw_chunk(start, end)
                def_chunk = defocus[start:end] if defocus is not None else None
                pre_chunk = preprocess_stack(
                    stack=raw_chunk,
                    apix=apix,
                    fft_scale=float(iter_scale),
                    lowpass_resolution=None,
                    invert=bool(args.invert),
                    center=not bool(args.no_center),
                    normalize=not bool(args.no_normalize),
                    phase_flip_ctf=bool(args.phase_flip_ctf),
                    ctf_defocus_um=def_chunk,
                    ctf_voltage_kv=ctf_voltage if ctf_voltage is not None else 300.0,
                    ctf_cs_mm=ctf_cs if ctf_cs is not None else 2.7,
                    ctf_amp_contrast=ctf_amp if ctf_amp is not None else 0.1,
                    n_threads=int(args.threads),
                )
                pre_out.data[start:end] = pre_chunk
                del raw_chunk, pre_chunk
                gc.collect()

        # Warm-start node vectors come from the previous iteration's MRA averages.
        # If box size changed due to a new Fourier scale, resize warm-start nodes to match
        # this iteration's preprocessed box before passing them into CAN.
        can_init_nodes_iter = can_init_nodes
        if can_init_nodes_iter is not None:
            ph, pw = int(pre_box[0]), int(pre_box[1])
            nh, nw = int(can_init_nodes_iter.shape[1]), int(can_init_nodes_iter.shape[2])
            if (nh, nw) != (ph, pw):
                if nh <= 0 or nw <= 0:
                    can_init_nodes_iter = None
                else:
                    sy = float(ph) / float(nh)
                    sx = float(pw) / float(nw)
                    if abs(sy - sx) > 1e-6:
                        raise RuntimeError(
                            f"Warm-start resize requires isotropic scaling, got previous box={(nh, nw)} current box={(ph, pw)}"
                        )
                    s = sy
                    can_init_nodes_iter = np.stack(
                        [_fft_scale_image(np.asarray(can_init_nodes_iter[i], dtype=np.float32), s) for i in range(can_init_nodes_iter.shape[0])],
                        axis=0,
                    ).astype(np.float32)
                    if verbose:
                        print(
                            f"[cli] iter {it}/{n_iters}: resized CAN warm-start nodes "
                            f"from box={nh} to box={ph} (scale={s:.4f})"
                        )

        # Single CAN->MRA iteration run; warm-start CAN from previous iteration MRA averages.
        def _on_stage(stage: str, _iter_local: int, avgs: np.ndarray, _counts: np.ndarray) -> None:
            s = str(stage).strip().lower()
            if s == "can":
                p = os.path.join(args.outdir, f"can_class_averages_iter{it:0{iter_pad}d}.mrcs")
            elif s == "mra":
                p = os.path.join(args.outdir, f"mra_class_averages_iter{it:0{iter_pad}d}.mrcs")
            else:
                return
            _write_stack(p, np.asarray(avgs, dtype=np.float32))
            if verbose:
                print(f"[cli] wrote {s.upper()} class averages: {p}")

        pre_mmap = mrcfile.mmap(pre_path, permissive=True)
        pre_iter = np.asarray(pre_mmap.data, dtype=np.float32)
        out = run_align_and_can(
            preprocessed_stack=pre_iter,
            apix=effective_apix,
            align_iters=1,
            can_params=can_params,
            mask_diameter_angstrom=args.particle_diameter_ang,
            seed=int(args.seed) + (it - 1),
            verbose=verbose,
            n_threads=int(args.threads),
            align_progress_every=int(args.align_progress_every),
            mra_log_each_particle=bool(args.mra_log_each_particle),
            center_class_averages=not bool(args.no_center_averages),
            iteration_callback=_on_stage,
            include_aligned_stack=bool(args.write_aligned_stack and it == n_iters),
            work_dir=args.outdir,
            can_init_nodes=can_init_nodes_iter,
        )
        del pre_iter
        try:
            pre_mmap.close()
        except Exception:
            pass
        gc.collect()

        # Write per-iteration transform tables.
        asn_i = np.asarray(out.get("mra_reference_assignments"), dtype=np.int32)
        rot_i = np.asarray(out.get("rotations"), dtype=np.float32)
        shf_i = np.asarray(out.get("shifts"), dtype=np.float32)
        scr_i = np.asarray(out.get("mra_reference_scores"), dtype=np.float32)
        base = os.path.join(args.outdir, f"iteration_mra_iter{it:0{iter_pad}d}")
        _write_iteration_alignment_json(f"{base}.json", asn_i, rot_i, shf_i, scr_i)
        _write_iteration_alignment_star(f"{base}.star", asn_i, rot_i, shf_i, scr_i)

        # Per-iteration FRC (reporting only; scaling is now fixed by --fft-scale).
        h1_i = np.asarray(out.get("final_preprocessed_half1"), dtype=np.float32)
        h2_i = np.asarray(out.get("final_preprocessed_half2"), dtype=np.float32)
        hc_i = np.asarray(out.get("final_preprocessed_half_counts"), dtype=np.int32)
        frc_dir_i = os.path.join(args.outdir, f"frc_iter{it:0{iter_pad}d}")
        frc_sum_i = _write_frc_outputs(h1_i, h2_i, hc_i, apix=float(effective_apix), outdir=frc_dir_i, prefix=f"iter{it:0{iter_pad}d}")
        if verbose:
            best_res_i = _best_resolution_from_frc_summary(frc_sum_i)
            print(f"[cli] iter {it}/{n_iters}: best FRC resolution={best_res_i}")

        # Warm-start CAN for next iteration from current MRA averages (largest classes first).
        mra_avg_i = np.asarray(out.get("final_preprocessed_class_averages"), dtype=np.float32)
        mra_cnt_i = np.asarray(out.get("final_preprocessed_class_counts"), dtype=np.int32)
        nz = np.where(mra_cnt_i > 0)[0]
        if nz.size >= 2:
            ord_idx = nz[np.argsort(mra_cnt_i[nz])[::-1]]
            can_init_nodes = mra_avg_i[ord_idx].astype(np.float32, copy=True)
        else:
            can_init_nodes = None

        if cleanup_pre_path:
            try:
                os.remove(pre_path)
            except OSError:
                pass

    if bool(args.write_aligned_stack):
        _write_stack(os.path.join(args.outdir, "aligned_stack.mrcs"), out["aligned_stack"])
    elif verbose:
        print("[cli] skipping aligned_stack.mrcs write (default; enable with --write-aligned-stack)")
    _write_stack(os.path.join(args.outdir, "class_averages.mrcs"), out["class_averages"])
    _write_stack(os.path.join(args.outdir, "node_vectors.mrcs"), out["node_vectors"])

    assignments = np.asarray(out["assignments"], dtype=np.int32)
    counts = np.asarray(out["class_counts"], dtype=np.int32)
    rotations = np.asarray(out["rotations"], dtype=np.float32)
    shifts = np.asarray(out.get("shifts"), dtype=np.float32)
    iter_mra_rot = out.get("iteration_mra_rotations", [])
    iter_mra_shf = out.get("iteration_mra_shifts", [])
    mra_ref_assign = np.asarray(out.get("mra_reference_assignments"), dtype=np.int32)
    mra_ref_scores = np.asarray(out.get("mra_reference_scores"), dtype=np.float32)
    n_classes_final = int(out["class_averages"].shape[0])

    # Also generate high-resolution class averages from phase-flipped-only particles
    # (no scaling, no low-pass), replaying final MRA transforms.
    # Do this in chunks to avoid holding an additional full-sized stack in RAM.
    if verbose:
        print("[cli] building high-res phase-flipped class averages from final assignments/transforms (chunked)")
    final_rot = np.asarray(iter_mra_rot[-1], dtype=np.float32) if isinstance(iter_mra_rot, list) and len(iter_mra_rot) > 0 else rotations
    final_shf = np.asarray(iter_mra_shf[-1], dtype=np.float32) if isinstance(iter_mra_shf, list) and len(iter_mra_shf) > 0 else shifts
    if mra_ref_assign.size != n_particles:
        raise RuntimeError("Missing/invalid final MRA reference assignments for high-res averaging")

    n = int(n_particles)
    h, w = int(raw_box[0]), int(raw_box[1])
    k = int(n_classes_final)
    sum_all = np.zeros((k, h, w), dtype=np.float32)
    sum_h1 = np.zeros((k, h, w), dtype=np.float32)
    sum_h2 = np.zeros((k, h, w), dtype=np.float32)
    cnt_all = np.zeros((k,), dtype=np.int64)
    cnt_h1 = np.zeros((k,), dtype=np.int64)
    cnt_h2 = np.zeros((k,), dtype=np.int64)
    # Heuristic chunk size based on box area; targets modest transient memory footprint.
    chunk_size = max(64, min(2048, int(max(64, 4_000_000 // max(1, h * w)))))
    if verbose:
        print(f"[cli] high-res chunk size={chunk_size}")

    for start in range(0, n, chunk_size):
        end = min(n, start + chunk_size)
        if verbose and (start == 0 or end == n or ((start // chunk_size) % 10 == 0)):
            print(f"[cli] high-res chunk {start}:{end}/{n}")
        defocus_chunk = defocus[start:end] if (defocus is not None) else None
        raw_chunk = _load_raw_chunk(start, end)
        src_chunk = preprocess_stack(
            stack=raw_chunk,
            apix=apix,
            fft_scale=1.0,
            lowpass_resolution=None,
            invert=False,
            center=not bool(args.no_center),
            normalize=False,
            phase_flip_ctf=bool(args.phase_flip_ctf),
            ctf_defocus_um=defocus_chunk,
            ctf_voltage_kv=ctf_voltage if ctf_voltage is not None else 300.0,
            ctf_cs_mm=ctf_cs if ctf_cs is not None else 2.7,
            ctf_amp_contrast=ctf_amp if ctf_amp is not None else 0.1,
            n_threads=int(args.threads),
        )
        c_avg, c_cnt, c_h1, c_h2, c_half = make_replayed_class_averages_with_halves(
            source_stack=src_chunk,
            assignments=mra_ref_assign[start:end],
            rotations_deg=final_rot[start:end],
            shifts_lowres_px=final_shf[start:end],
            fft_scale=float(args.fft_scale),
            n_classes=n_classes_final,
            n_threads=int(args.threads),
        )
        sum_all += c_avg * c_cnt[:, None, None].astype(np.float32)
        sum_h1 += c_h1 * c_half[:, 0][:, None, None].astype(np.float32)
        sum_h2 += c_h2 * c_half[:, 1][:, None, None].astype(np.float32)
        cnt_all += c_cnt.astype(np.int64)
        cnt_h1 += c_half[:, 0].astype(np.int64)
        cnt_h2 += c_half[:, 1].astype(np.int64)
        del raw_chunk, src_chunk, c_avg, c_cnt, c_h1, c_h2, c_half
        gc.collect()

    hires_avgs = np.zeros_like(sum_all, dtype=np.float32)
    hires_half1 = np.zeros_like(sum_h1, dtype=np.float32)
    hires_half2 = np.zeros_like(sum_h2, dtype=np.float32)
    nz_all = cnt_all > 0
    nz_h1 = cnt_h1 > 0
    nz_h2 = cnt_h2 > 0
    hires_avgs[nz_all] = (sum_all[nz_all] / cnt_all[nz_all, None, None].astype(np.float32)).astype(np.float32)
    hires_half1[nz_h1] = (sum_h1[nz_h1] / cnt_h1[nz_h1, None, None].astype(np.float32)).astype(np.float32)
    hires_half2[nz_h2] = (sum_h2[nz_h2] / cnt_h2[nz_h2, None, None].astype(np.float32)).astype(np.float32)
    hires_counts = cnt_all.astype(np.int32)
    hires_half_counts = np.stack([cnt_h1, cnt_h2], axis=1).astype(np.int32)
    _write_stack(os.path.join(args.outdir, "class_averages_highres_phaseflip.mrcs"), hires_avgs)
    hires_frc_summary = _write_frc_outputs(
        hires_half1,
        hires_half2,
        hires_half_counts,
        apix=float(apix),
        outdir=os.path.join(args.outdir, "frc_highres_phaseflip"),
        prefix="highres_phaseflip",
    )

    with open(os.path.join(args.outdir, "assignments.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "particle_index_0based",
                "class_index_0based",
                "rotation_degrees",
                "mra_reference_index_0based",
                "mra_reference_score",
            ]
        )
        for i in range(assignments.size):
            w.writerow(
                [
                    i,
                    int(assignments[i]),
                    float(rotations[i]),
                    int(mra_ref_assign[i]) if mra_ref_assign.size == assignments.size else "",
                    float(mra_ref_scores[i]) if mra_ref_scores.size == assignments.size else "",
                ]
            )

    with open(os.path.join(args.outdir, "class_counts.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "class_index_0based",
                "count_highres_phaseflip_avg",
                "highres_half1_count",
                "highres_half2_count",
            ]
        )
        for c in range(max(int(counts.size), int(hires_counts.size))):
            hc = int(hires_counts[c]) if c < hires_counts.size else 0
            hh1 = int(hires_half_counts[c, 0]) if c < hires_half_counts.shape[0] else 0
            hh2 = int(hires_half_counts[c, 1]) if c < hires_half_counts.shape[0] else 0
            w.writerow([c, hc, hh1, hh2])

    summary = {
        "input_star": os.path.abspath(args.star) if args.star else None,
        "input_stack": os.path.abspath(args.stack) if args.stack else None,
        "outdir": os.path.abspath(args.outdir),
        "n_particles": int(n_particles),
        "max_particles": int(args.max_particles) if args.max_particles is not None else None,
        "threads": int(args.threads),
        "can_threads": int(args.can_threads),
        "align_progress_every": int(args.align_progress_every),
        "write_aligned_stack": bool(args.write_aligned_stack),
        "box_size": [int(raw_box[0]), int(raw_box[1])],
        "apix": float(apix),
        "fft_scale": float(args.fft_scale),
        "effective_apix_after_fft_scale": float(effective_apix),
        "can_params": asdict(can_params),
        "compute_backend": str(args.compute_backend),
        "align_iters": int(args.align_iters),
        "topology_total_iterations": int(args.align_iters),
        "mra_method": "skimage-polar",
        "particle_diameter_ang": float(args.particle_diameter_ang) if args.particle_diameter_ang is not None else None,
        "mask_diameter_factor": 1.25 if args.particle_diameter_ang is not None else None,
        "phase_flip_ctf": bool(args.phase_flip_ctf),
        "center_class_averages": not bool(args.no_center_averages),
        "ctf_voltage_kv": ctf_voltage,
        "ctf_cs_mm": ctf_cs,
        "ctf_amp_contrast": ctf_amp,
        "n_classes_final": n_classes_final,
        "highres_phaseflip_class_averages": os.path.join(os.path.abspath(args.outdir), "class_averages_highres_phaseflip.mrcs"),
        "frc_highres_phaseflip_summary_csv": os.path.abspath(hires_frc_summary),
        "can_steps_run": int(out.get("can_steps_run", int(args.num_presentations))),
        "can_early_stopped": bool(out.get("can_early_stopped", False)),
    }
    with open(os.path.join(args.outdir, "run_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    with open(os.path.join(args.outdir, "iteration_history.json"), "w") as f:
        json.dump(out.get("iteration_history", []), f, indent=2)

    with open(os.path.join(args.outdir, "can_checkpoint_history.json"), "w") as f:
        json.dump(out.get("can_checkpoint_history", []), f, indent=2)

    _close_raw_source()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
