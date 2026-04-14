"""CTFFind4 plugin — wraps the ctffind4 binary behind the PluginBase contract.

The binary is expected on ``$PATH``. Input is one MRC micrograph; output is a
structured ``CtfEstimationResult`` (defocus U/V, astigmatism angle, CC, and
fit extent) plus the raw star artifact path so downstream tools can keep the
ground truth on disk.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Type

from models.plugins_models import (
    CTF_TASK,
    PluginInfo,
    RecuirementResultEnum,
    RequirementResult,
    TaskCategory,
)
from plugins.base import PluginBase
from plugins.progress import NullReporter, ProgressReporter
from plugins.ctf.models import (
    CtfEstimationInput,
    CtfEstimationOutput,
    CtfEstimationResult,
)

logger = logging.getLogger(__name__)

CTFFIND_BINARY = "ctffind"  # resolved via PATH; some distros name it ctffind4


class CtffindPlugin(PluginBase[CtfEstimationInput, CtfEstimationOutput]):
    """ctffind4 wrapper. Non-Python dependency — surfaces a clean requirement
    check so the UI can tell users the binary is missing before they run."""

    task_category: TaskCategory = CTF_TASK

    # -- metadata ----------------------------------------------------------

    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="ctffind",
            developer="Magellon",
            description="Defocus/astigmatism estimation via the ctffind4 binary",
            version="1.0.0",
        )

    @classmethod
    def input_schema(cls) -> Type[CtfEstimationInput]:
        return CtfEstimationInput

    @classmethod
    def output_schema(cls) -> Type[CtfEstimationOutput]:
        return CtfEstimationOutput

    # -- requirements ------------------------------------------------------

    def check_requirements(self) -> List[RequirementResult]:
        ctffind = shutil.which(CTFFIND_BINARY) or shutil.which(f"{CTFFIND_BINARY}4")
        if not ctffind:
            return [RequirementResult(
                result=RecuirementResultEnum.FAILURE,
                condition="ctffind binary on PATH",
                message=f"Neither '{CTFFIND_BINARY}' nor '{CTFFIND_BINARY}4' was found on PATH.",
                instructions="Install ctffind4 (https://grigoriefflab.umassmed.edu/ctffind4) and make sure it is on PATH.",
            )]
        return [RequirementResult(
            result=RecuirementResultEnum.SUCCESS,
            condition="ctffind binary on PATH",
            message=f"Found at {ctffind}",
        )]

    # -- execution ---------------------------------------------------------

    def execute(
        self,
        input_data: CtfEstimationInput,
        *,
        reporter: ProgressReporter = NullReporter(),
    ) -> CtfEstimationOutput:
        binary = shutil.which(CTFFIND_BINARY) or shutil.which(f"{CTFFIND_BINARY}4")
        if not binary:
            raise RuntimeError("ctffind binary is not available on PATH")

        if not os.path.isfile(input_data.image_path):
            raise FileNotFoundError(f"Input micrograph not found: {input_data.image_path}")

        output_dir = Path(input_data.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(input_data.image_path).stem
        diag_path = output_dir / f"{stem}_ctf.mrc"
        star_path = output_dir / f"{stem}_ctf.txt"

        # ctffind4 reads parameters from stdin. We drive it non-interactively
        # with the canonical set of prompts.
        stdin_lines = [
            input_data.image_path,
            str(diag_path),
            f"{input_data.pixel_size}",
            f"{input_data.acceleration_voltage}",
            f"{input_data.spherical_aberration}",
            f"{input_data.amplitude_contrast}",
            f"{input_data.box_size}",
            f"{input_data.min_resolution}",
            f"{input_data.max_resolution}",
            f"{input_data.min_defocus}",
            f"{input_data.max_defocus}",
            f"{input_data.defocus_step}",
            "no",  # Do you know what astigmatism is present?
            "yes",  # Find additional phase shift?
            "yes" if input_data.find_additional_phase_shift else "no",
            "no",  # Set expert options?
        ]
        stdin = "\n".join(stdin_lines) + "\n"

        proc = subprocess.run(
            [binary],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=str(output_dir),
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"ctffind exited with status {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
            )

        result = _parse_ctffind_output(star_path, proc.stdout)
        raw_lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]

        return CtfEstimationOutput(
            result=result,
            star_path=str(star_path),
            diagnostic_image_path=str(diag_path) if diag_path.exists() else None,
            raw_lines=raw_lines[-50:],  # keep the tail for debugging, drop banner noise
        )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# ctffind writes a *_ctf.txt file whose final data row is:
# column 1: micrograph number
# col 2:    defocus 1 (Å)  — "major axis"
# col 3:    defocus 2 (Å)  — "minor axis"
# col 4:    astigmatism angle (degrees)
# col 5:    additional phase shift (radians)
# col 6:    cross correlation of best fit
# col 7:    resolution (Å) of first zero (fit extent)
_NUMBER_RE = re.compile(r"-?\d+\.?\d*(?:[eE][+-]?\d+)?")


def _parse_ctffind_output(star_path: Path, stdout: str) -> CtfEstimationResult:
    """Parse the final data row of a ctffind .txt file."""
    if not star_path.exists():
        raise RuntimeError(f"ctffind finished but no output file at {star_path}")

    data_row: List[float] | None = None
    for line in star_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        numbers = [float(m) for m in _NUMBER_RE.findall(stripped)]
        if len(numbers) >= 6:
            data_row = numbers

    if data_row is None:
        raise RuntimeError(f"No data row found in {star_path}")

    return CtfEstimationResult(
        defocus_u=data_row[1],
        defocus_v=data_row[2],
        astigmatism_angle=data_row[3],
        additional_phase_shift=data_row[4] if len(data_row) > 4 else None,
        cc=data_row[5] if len(data_row) > 5 else 0.0,
        resolution_limit=data_row[6] if len(data_row) > 6 else 0.0,
    )
