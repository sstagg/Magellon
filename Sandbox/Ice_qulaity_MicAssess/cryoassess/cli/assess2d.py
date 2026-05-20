"""``2dassess`` command-line entry point.

Sorts the 2D class averages in a RELION ``.mrcs`` stack into four buckets and
prints the indices judged "good".  Numerical work lives in
:mod:`cryoassess.core` and :mod:`cryoassess.models`.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
from PIL import Image

from cryoassess.core.mrc import load_stack, scale_to_uint8
from cryoassess.core.preprocessing import cut_by_radius

_EMPTY_TOLERANCE = 1e-7


@dataclass
class Assess2DConfig:
    """Resolved settings for one 2DAssess run."""

    input: str
    model: str = "./weights/2dassess_062119.h5"
    batch_size: int = 32
    name: str = "particle"
    output: str = "2DAssess"


def parse_args(argv: Optional[Sequence[str]] = None) -> Assess2DConfig:
    """Parse ``argv`` into an :class:`Assess2DConfig`."""

    ap = argparse.ArgumentParser(prog="2dassess", description="Assess RELION 2D class averages.")
    ap.add_argument("-i", "--input", required=True,
                    help="Input .mrcs file of 2D class averages.")
    ap.add_argument("-m", "--model", default="./weights/2dassess_062119.h5",
                    help="Path to the 2DAssess .h5 model file.")
    ap.add_argument("-b", "--batch_size", type=int, default=32,
                    help="Prediction batch size. Lower it on out-of-memory errors.")
    ap.add_argument("-n", "--name", default="particle",
                    help="Particle name used in the output file names.")
    ap.add_argument("-o", "--output", default="2DAssess",
                    help="Output directory name. Default: 2DAssess.")
    ns = ap.parse_args(argv)
    return Assess2DConfig(
        input=ns.input, model=ns.model, batch_size=ns.batch_size,
        name=ns.name, output=ns.output,
    )


def convert_class_averages(mrcs_path: str, jpg_dir: str, name: str) -> None:
    """Write each non-empty class average in ``mrcs_path`` as a JPEG.

    Files are named ``<name>_<index>.jpg`` with a 1-based index.
    """

    Path(jpg_dir).mkdir(parents=True, exist_ok=True)
    stack = load_stack(mrcs_path)
    written = 0
    for index, average in enumerate(stack, start=1):
        if abs(float(np.sum(average))) <= _EMPTY_TOLERANCE:
            continue  # skip empty (all-zero) class slots
        cropped = cut_by_radius(average)
        image = Image.fromarray(scale_to_uint8(cropped)).convert("L")
        image.save(os.path.join(jpg_dir, f"{name}_{index}.jpg"))
        written += 1
    print(f"Converted {written} class averages.")


def run(config: Assess2DConfig) -> None:
    """Execute a full 2DAssess run from a resolved config."""

    output = os.path.abspath(config.output)
    shutil.rmtree(output, ignore_errors=True)
    jpg_dir = os.path.join(output, "data")
    convert_class_averages(config.input, jpg_dir, config.name)

    # Imported lazily so the core/conversion path does not require TensorFlow.
    from cryoassess.core.classcenter import is_centered
    from cryoassess.models.assess2d import (
        CLASS_AVERAGE_LABELS,
        build_model,
        class_average_generator,
        predict,
    )

    print("Assessing 2D class averages...")
    model = build_model(os.path.abspath(config.model))
    probs = predict(class_average_generator(output, config.batch_size), model)

    for label_name in CLASS_AVERAGE_LABELS:
        Path(os.path.join(output, label_name)).mkdir(exist_ok=True)

    good_indices = []
    for path, prob in zip(sorted(glob.glob(os.path.join(jpg_dir, "*.jpg"))), probs):
        label = CLASS_AVERAGE_LABELS[int(np.argmax(prob))]
        # An off-centre or multi-object "good" average is demoted to "Clip".
        if label == "Good" and not is_centered(path):
            label = "Clip"
        shutil.copy2(path, os.path.join(output, label))
        if label == "Good":
            match = re.search(rf"{re.escape(config.name)}_(\d+)", os.path.basename(path))
            if match:
                good_indices.append(match.group(1))

    print(f"Outputs are stored in {output}")
    print("Good class average indices (1-based):", ", ".join(good_indices) or "(none)")


def main(argv: Optional[Sequence[str]] = None) -> None:
    run(parse_args(argv))


if __name__ == "__main__":
    main()
