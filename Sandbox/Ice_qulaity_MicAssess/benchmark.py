#!/usr/bin/env python3
"""Benchmark MicAssess on the labelled example PNGs.

The folder names under ``Examples/`` encode the ground-truth class (0Great ..
5Empty_ice_...).  This script loads those PNGs, runs the K2/centre model, and
reports per-class accuracy, a confusion matrix, and timing.

Unlike a live run it skips the MRC->PNG stage and feeds the example PNGs
straight to the model.  All model and preprocessing logic comes from the
``cryoassess`` package -- this file only loads images and prints results.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import numpy as np
from PIL import Image

from cryoassess.core.labels import LABEL_LIST, assign_label
from cryoassess.core.preprocessing import preprocess_micrograph
from cryoassess.models.micassess import IMG_DIM, detector_width

WEIGHTS_DIR = Path(__file__).parent / "weights"
EXAMPLES_DIR = Path(__file__).parent / "Examples"
IMG_W = detector_width("K2")

T1 = 0.1  # good/bad tolerance
T2 = 0.1  # great/decent tolerance


def load_examples():
    """Return ``(images, true_labels, filenames)`` for every example PNG."""

    images, labels, names = [], [], []
    for label_idx, folder_name in enumerate(LABEL_LIST):
        for png_path in sorted((EXAMPLES_DIR / folder_name).glob("*.png")):
            pixels = Image.open(png_path).convert("L").resize(
                (IMG_W, IMG_DIM), Image.LANCZOS
            )
            processed = preprocess_micrograph(np.asarray(pixels, dtype=np.float32))
            images.append(processed[..., np.newaxis])
            labels.append(label_idx)
            names.append(png_path.name)
    return np.stack(images, axis=0), np.array(labels), names


def run_benchmark():
    print("=" * 60)
    print("  MicAssess Benchmark - Example Images (K2, t1=0.1, t2=0.1)")
    print("=" * 60)

    t0 = time.time()
    images, true_labels, filenames = load_examples()
    print(f"\nLoaded {len(images)} images in {time.time() - t0:.1f}s")

    from cryoassess.models.micassess import build_models, predict

    print("\nBuilding model...")
    t0 = time.time()
    models = build_models(str(WEIGHTS_DIR), detector="K2", cutpos="center")
    print(f"  Done in {time.time() - t0:.1f}s")

    print("\nRunning prediction...")
    t0 = time.time()
    binary_probs, good_probs, bad_probs = predict(images, *models)
    inference_time = time.time() - t0
    print(
        f"  Inference for {len(images)} images: {inference_time:.2f}s "
        f"({inference_time / len(images) * 1000:.0f} ms/image)"
    )

    pred_labels = np.array([
        assign_label(binary_probs[i], good_probs[i], bad_probs[i], T1, T2)
        for i in range(len(images))
    ])

    overall_acc = float(np.mean(pred_labels == true_labels))
    correct = int(np.sum(pred_labels == true_labels))
    print(f"\nOverall accuracy: {overall_acc * 100:.1f}%  ({correct}/{len(images)})")

    print("\nPer-class results:")
    per_class = {}
    for i, name in enumerate(LABEL_LIST):
        mask = true_labels == i
        class_correct = int(np.sum(pred_labels[mask] == i))
        total = int(np.sum(mask))
        accuracy = class_correct / total if total else 0.0
        per_class[name] = {"total": total, "correct": class_correct, "accuracy": accuracy}
        print(f"  {name:<55} {class_correct:>2}/{total:<2}  {accuracy * 100:>5.1f}%")

    n = len(LABEL_LIST)
    confusion = np.zeros((n, n), dtype=int)
    for true_l, pred_l in zip(true_labels, pred_labels):
        confusion[true_l, pred_l] += 1
    print("\nConfusion matrix (rows=true, cols=predicted):")
    print("      " + "".join(f"{i:>5}" for i in range(n)))
    for i, row in enumerate(confusion):
        print(f"  [{i}]  " + "".join(f"{v:>5}" for v in row))

    results = {
        "overall_accuracy": overall_acc,
        "inference_time_seconds": inference_time,
        "ms_per_image": inference_time / len(images) * 1000,
        "num_images": len(images),
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
        "predictions": [
            {"file": f, "true": int(t), "pred": int(p)}
            for f, t, p in zip(filenames, true_labels, pred_labels)
        ],
    }
    out_path = Path(__file__).parent / "benchmark_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {out_path}")
    print("=" * 60)
    return results


if __name__ == "__main__":
    run_benchmark()
