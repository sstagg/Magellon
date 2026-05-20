"""``micassess`` command-line entry point.

This is the thin orchestration layer: it parses arguments, converts MRC inputs
to PNG, drives the model, and sorts the results.  All numerical work lives in
:mod:`cryoassess.core` and :mod:`cryoassess.models`.
"""

from __future__ import annotations

import argparse
import glob
import multiprocessing as mp
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from cryoassess.core.labels import (
    DECENT_LABEL,
    GREAT_LABEL,
    LABEL_LIST,
    assign_labels,
)
from cryoassess.core.mrc import load_micrograph, to_grayscale_image
from cryoassess.core.starfile import (
    micrograph_blockcode,
    read_star,
    star_to_micrograph_list,
    write_star,
)


@dataclass
class MicAssessConfig:
    """Resolved settings for one MicAssess run."""

    input: str
    model_dir: str
    detector: str = "K2"
    output: str = "MicAssess"
    batch_size: int = 32
    t1: float = 0.1
    t2: float = 0.1
    threads: Optional[int] = None
    gpus: str = "0"
    dont_reset: bool = False


def parse_args(argv: Optional[Sequence[str]] = None) -> MicAssessConfig:
    """Parse ``argv`` into a :class:`MicAssessConfig`."""

    ap = argparse.ArgumentParser(prog="micassess", description="Assess cryo-EM micrograph quality.")
    ap.add_argument("-i", "--input", required=True,
                    help="A micrographs star file, or a glob pattern matching .mrc files.")
    ap.add_argument("-m", "--model", default="./weights", dest="model_dir",
                    help="Directory holding the four MicAssess .h5 weight files.")
    ap.add_argument("-d", "--detector", default="K2", choices=["K2", "K3"],
                    help="Detector type. Default: K2.")
    ap.add_argument("-o", "--output", default="MicAssess",
                    help="Output directory name. Default: MicAssess.")
    ap.add_argument("-b", "--batch_size", type=int, default=32,
                    help="Prediction batch size. Lower it on out-of-memory errors.")
    ap.add_argument("--t1", type=float, default=0.1,
                    help="Good/bad tolerance. Higher rejects more micrographs as bad.")
    ap.add_argument("--t2", type=float, default=0.1,
                    help="Great/decent tolerance. Higher demotes more 'great' to 'good'.")
    ap.add_argument("--threads", type=int, default=None,
                    help="MRC->PNG conversion threads. Default: all CPUs.")
    ap.add_argument("--gpus", default="0",
                    help="Comma-separated GPU indices. Default: 0.")
    ap.add_argument("--dont_reset", action="store_true",
                    help="Reuse PNGs from a previous run and skip MRC conversion.")
    ns = ap.parse_args(argv)
    return MicAssessConfig(
        input=ns.input, model_dir=ns.model_dir, detector=ns.detector, output=ns.output,
        batch_size=ns.batch_size, t1=ns.t1, t2=ns.t2, threads=ns.threads,
        gpus=ns.gpus, dont_reset=ns.dont_reset,
    )


def resolve_input_star(input_arg: str) -> str:
    """Return a star-file path for ``input_arg``.

    A ``.star`` argument is used as-is.  A glob pattern is expanded and written
    to ``micrographs.star`` so the rest of the pipeline has a uniform input.
    """

    if input_arg.endswith(".star"):
        return input_arg

    micrographs = sorted(glob.glob(input_arg))
    if not micrographs:
        raise FileNotFoundError(f"no micrographs matched the pattern {input_arg!r}")
    star_path = "micrographs.star"
    with open(star_path, "w") as handle:
        handle.write("data_\nloop_\n_rlnMicrographName\n")
        handle.write("\n".join(micrographs) + "\n")
    print(f"Generated star file {star_path} ({len(micrographs)} micrographs).")
    return star_path


def _convert_one(task: Tuple[str, str]) -> None:
    """Worker: convert one MRC file to a PNG under ``png_dir``."""

    mrc_path, png_dir = task
    try:
        image = load_micrograph(mrc_path)
        name = os.path.splitext(os.path.basename(mrc_path))[0] + ".png"
        to_grayscale_image(image).save(os.path.join(png_dir, name))
    except Exception as exc:  # one bad file must not abort the whole batch
        print(f"  skipped {mrc_path}: {exc}")


def convert_micrographs(mic_list: Sequence[str], png_dir: str, threads: Optional[int]) -> None:
    """Convert every MRC in ``mic_list`` to a PNG under ``png_dir`` in parallel."""

    Path(png_dir).mkdir(parents=True, exist_ok=True)
    worker_count = threads if threads else mp.cpu_count()
    print(f"Converting {len(mic_list)} micrographs in {worker_count} threads...")
    with mp.Pool(worker_count) as pool:
        pool.map(_convert_one, [(mrc, png_dir) for mrc in mic_list])
    print("Conversion finished.")


def write_scores(output_dir: str, png_files: Sequence[str],
                 binary_probs, good_probs) -> None:
    """Write per-micrograph good/great probability TSVs into ``output_dir``."""

    for filename, probs, column in (
        ("probs_good.tsv", binary_probs, "good"),
        ("probs_great.tsv", good_probs, "great"),
    ):
        with open(os.path.join(output_dir, filename), "w") as handle:
            for path, prob in zip(png_files, probs):
                handle.write(f"{os.path.basename(path)}\t{1 - prob[0]}\n")


def sort_outputs(output_dir: str, png_files: Sequence[str],
                 labels: Sequence[int]) -> Tuple[List[str], List[str]]:
    """Copy each PNG into its predicted-label directory.

    Returns ``(good_list, great_list)`` where the good list is decent + great.
    """

    for label_name in LABEL_LIST:
        Path(os.path.join(output_dir, label_name)).mkdir(parents=True, exist_ok=True)

    great_list: List[str] = []
    decent_list: List[str] = []
    for path, label in zip(png_files, labels):
        shutil.copy2(path, os.path.join(output_dir, LABEL_LIST[label]))
        if label == GREAT_LABEL:
            great_list.append(path)
        elif label == DECENT_LABEL:
            decent_list.append(path)
    return decent_list + great_list, great_list


def _write_subset_star(star_path: str, basenames: set, suffix: str) -> None:
    """Write a star file keeping only micrographs whose basename is in ``basenames``."""

    star_df = read_star(star_path)
    block = micrograph_blockcode(star_df)
    df = star_df[block][0]
    keep = df["_rlnMicrographName"].apply(
        lambda path: os.path.splitext(os.path.basename(path))[0] in basenames
    )
    star_df[block][0] = df[keep].reset_index(drop=True)

    out = os.path.join(
        os.path.dirname(star_path),
        os.path.splitext(os.path.basename(star_path))[0] + suffix,
    )
    write_star(star_df, out)
    print(f"Wrote {out} ({int(keep.sum())} micrographs).")


def write_star_outputs(star_path: str, good_list: Sequence[str],
                       great_list: Sequence[str]) -> None:
    """Write ``*_great.star`` and ``*_good.star`` next to the input star file."""

    if great_list:
        _write_subset_star(star_path, {_basename(f) for f in great_list}, "_great.star")
    else:
        print('No "great" micrographs found.')
    if good_list:
        _write_subset_star(star_path, {_basename(f) for f in good_list}, "_good.star")
    else:
        print('No "good" micrographs found.')


def _basename(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def report(labels: Sequence[int], good_list: Sequence[str],
           great_list: Sequence[str]) -> None:
    """Print a per-class summary of the run."""

    total = len(labels)
    print(f"Total:\t {total} micrographs")
    for index, name in enumerate(LABEL_LIST):
        count = sum(1 for label in labels if label == index)
        print(f"{name}:\t {count} micrographs")
    if total:
        print(f"{100 * len(great_list) / total:.2f}% are great (written to *_great.star).")
        print(f"{100 * len(good_list) / total:.2f}% are good (written to *_good.star).")
    print("Details can be found in the output directory.")


def run(config: MicAssessConfig) -> None:
    """Execute a full MicAssess run from a resolved config."""

    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = config.gpus

    png_root = os.path.join(config.output, "png")
    png_data = os.path.join(png_root, "data")
    star_path = resolve_input_star(config.input)

    if config.dont_reset:
        print("Reusing existing PNGs; skipping MRC conversion.")
        for label_name in LABEL_LIST:
            shutil.rmtree(os.path.join(config.output, label_name), ignore_errors=True)
    else:
        shutil.rmtree(config.output, ignore_errors=True)
        convert_micrographs(star_to_micrograph_list(star_path), png_data, config.threads)

    # Imported here so CUDA_VISIBLE_DEVICES is set before TensorFlow starts.
    from cryoassess.models.micassess import predict_micrographs

    print("Assessing micrographs...")
    binary, good, bad = predict_micrographs(
        png_root, config.model_dir, config.detector, config.batch_size
    )

    png_files = sorted(glob.glob(os.path.join(png_data, "*.png")))
    write_scores(config.output, png_files, binary, good)

    labels = assign_labels(binary, good, bad, config.t1, config.t2)
    good_list, great_list = sort_outputs(config.output, png_files, labels)
    write_star_outputs(star_path, good_list, great_list)
    report(labels, good_list, great_list)


def main(argv: Optional[Sequence[str]] = None) -> None:
    run(parse_args(argv))


if __name__ == "__main__":
    main()
