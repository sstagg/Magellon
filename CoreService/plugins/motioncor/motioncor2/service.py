"""MotionCor2 plugin — wraps the motioncor2 binary behind the PluginBase contract.

Drives MotionCor2 non-interactively, then parses the log for per-frame drift
(``dx``, ``dy`` in pixels). The parsed vectors let the frontend render a drift
overlay without re-reading the log.
"""
from __future__ import annotations

import logging
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Type

from models.plugins_models import (
    MOTIONCOR_TASK,
    PluginInfo,
    RecuirementResultEnum,
    RequirementResult,
    TaskCategory,
)
from plugins.base import PluginBase
from plugins.motioncor.models import (
    DriftSample,
    MotionCorInput,
    MotionCorOutput,
    MotionCorResultSummary,
)

logger = logging.getLogger(__name__)

MOTIONCOR_BINARY = "motioncor2"


class MotionCor2Plugin(PluginBase[MotionCorInput, MotionCorOutput]):
    """MotionCor2 wrapper. Non-Python dependency — surfaces missing binary via
    ``check_requirements`` so the UI can warn before submit."""

    task_category: TaskCategory = MOTIONCOR_TASK

    # -- metadata ----------------------------------------------------------

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="motioncor2",
            developer="Magellon",
            description="Movie motion correction wrapper around UCSF MotionCor2",
            version="1.0.0",
        )

    @classmethod
    def input_schema(cls) -> Type[MotionCorInput]:
        return MotionCorInput

    @classmethod
    def output_schema(cls) -> Type[MotionCorOutput]:
        return MotionCorOutput

    # -- requirements ------------------------------------------------------

    def check_requirements(self) -> List[RequirementResult]:
        binary = shutil.which(MOTIONCOR_BINARY)
        if not binary:
            return [RequirementResult(
                result=RecuirementResultEnum.FAILURE,
                condition="motioncor2 binary on PATH",
                message=f"'{MOTIONCOR_BINARY}' was not found on PATH.",
                instructions="Install MotionCor2 and make sure the binary is on PATH (and that a CUDA-capable GPU is available).",
            )]
        return [RequirementResult(
            result=RecuirementResultEnum.SUCCESS,
            condition="motioncor2 binary on PATH",
            message=f"Found at {binary}",
        )]

    # -- execution ---------------------------------------------------------

    def execute(self, input_data: MotionCorInput) -> MotionCorOutput:
        binary = shutil.which(MOTIONCOR_BINARY)
        if not binary:
            raise RuntimeError("motioncor2 binary is not available on PATH")

        if not os.path.isfile(input_data.movie_path):
            raise FileNotFoundError(f"Input movie not found: {input_data.movie_path}")

        output_dir = Path(input_data.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(input_data.movie_path).stem
        out_mrc = output_dir / f"{stem}_aligned.mrc"
        log_prefix = output_dir / f"{stem}_motioncor.log"

        cmd = _build_cmd(binary, input_data, out_mrc, log_prefix)

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                f"motioncor2 exited with status {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
            )

        drift = _parse_drift_log(log_prefix) if log_prefix.exists() else []
        summary = _summarize_drift(drift)

        return MotionCorOutput(
            aligned_mrc_path=str(out_mrc),
            log_path=str(log_prefix) if log_prefix.exists() else None,
            drift=drift,
            summary=summary,
        )


# ---------------------------------------------------------------------------
# Command construction
# ---------------------------------------------------------------------------

def _build_cmd(binary: str, params: MotionCorInput, out_mrc: Path, log_prefix: Path) -> List[str]:
    cmd: List[str] = [binary]

    ext = Path(params.movie_path).suffix.lower()
    if ext == ".tif" or ext == ".tiff":
        cmd += ["-InTiff", params.movie_path]
    elif ext == ".eer":
        cmd += ["-InEer", params.movie_path]
    else:
        cmd += ["-InMrc", params.movie_path]

    cmd += ["-OutMrc", str(out_mrc)]
    cmd += ["-PixSize", str(params.pixel_size)]
    cmd += ["-FmDose", str(params.dose_per_frame)]
    cmd += ["-kV", str(params.voltage_kv)]
    cmd += ["-FtBin", str(params.ft_bin)]
    cmd += ["-Iter", str(params.iterations)]
    cmd += ["-Bft", f"{params.b_factor_global} {params.b_factor_local}"]
    cmd += ["-Patch", f"{params.patch_rows} {params.patch_cols}"]
    cmd += ["-Gpu", params.gpu_ids]
    cmd += ["-LogFile", str(log_prefix)]

    if params.gain_reference_path:
        cmd += ["-Gain", params.gain_reference_path]
        cmd += ["-RotGain", str(params.rotate_gain)]
        cmd += ["-FlipGain", str(params.flip_gain)]

    if params.extra_args:
        cmd += params.extra_args

    return cmd


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------

# MotionCor2 writes per-frame shifts in its log. A typical line looks like:
#   "  x Shift   y Shift"   header
#   "  1   -0.123    0.456"
_SHIFT_LINE_RE = re.compile(r"^\s*(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$")


def _parse_drift_log(path: Path) -> List[DriftSample]:
    try:
        text = path.read_text()
    except OSError:
        return []

    samples: List[DriftSample] = []
    for raw in text.splitlines():
        m = _SHIFT_LINE_RE.match(raw)
        if not m:
            continue
        frame, dx, dy = int(m.group(1)), float(m.group(2)), float(m.group(3))
        samples.append(DriftSample(frame=frame, dx=dx, dy=dy))

    # De-duplicate by frame (MotionCor may report per-iteration shifts);
    # keep the last occurrence which is the converged one.
    by_frame: dict[int, DriftSample] = {}
    for s in samples:
        by_frame[s.frame] = s
    return [by_frame[k] for k in sorted(by_frame)]


def _summarize_drift(samples: List[DriftSample]) -> MotionCorResultSummary:
    if not samples:
        return MotionCorResultSummary(total_drift_pixels=0.0, max_frame_drift_pixels=0.0, num_frames=0)

    magnitudes = [math.hypot(s.dx, s.dy) for s in samples]

    # Frame-to-frame deltas give "how much did the stage move between frames"
    # — more faithful than absolute magnitudes which drift with reference choice.
    deltas = []
    for prev, cur in zip(samples, samples[1:]):
        deltas.append(math.hypot(cur.dx - prev.dx, cur.dy - prev.dy))

    total = sum(deltas)
    peak = max(deltas) if deltas else max(magnitudes)

    return MotionCorResultSummary(
        total_drift_pixels=total,
        max_frame_drift_pixels=peak,
        num_frames=len(samples),
    )
