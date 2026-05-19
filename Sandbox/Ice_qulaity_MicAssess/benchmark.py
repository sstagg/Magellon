#!/usr/bin/env python3
"""
Benchmark micassess on the 30 labeled example PNGs.

Folder names encode ground truth:
  0Great, 1Decent, 2Contamination_..., 3Empty_no_ice,
  4Crystalline_ice, 5Empty_ice_no_particles_but_vitreous_ice

Outputs: per-class accuracy, confusion matrix, overall accuracy, and timing.
"""

import os
import time
import glob
import json
from pathlib import Path

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import numpy as np
from PIL import Image

# ── constants (must match micassess.py) ─────────────────────────────────────
IMG_DIM = 494
IMG_W   = 512          # K2 detector

LABEL_LIST = [
    "0Great",
    "1Decent",
    "2Contamination_Aggregate_Crack_Breaking_Drifting",
    "3Empty_no_ice",
    "4Crystalline_ice",
    "5Empty_ice_no_particles_but_vitreous_ice",
]

WEIGHTS_DIR  = Path(__file__).parent / "weights"
EXAMPLES_DIR = Path(__file__).parent / "Examples"

T1 = 0.1   # good/bad threshold  (same default as micassess)
T2 = 0.1   # great/decent threshold


# ── preprocessing (from cryoassess/lib/utils.py) ────────────────────────────
def _normalize(x: np.ndarray) -> np.ndarray:
    return (x - np.mean(x)) / (np.std(x) + 1e-8)

def _circular_mask(h: int, w: int) -> np.ndarray:
    cx, cy = w // 2, h // 2
    radius = min(cx, cy, w - cx, h - cy)
    Y, X = np.ogrid[:h, :w]
    return (X - cx) ** 2 + (Y - cy) ** 2 <= radius ** 2

def preprocess_k2(img: np.ndarray) -> np.ndarray:
    norm = _normalize(img)
    mask = _circular_mask(norm.shape[0], norm.shape[1])
    out  = norm.copy()
    out[~mask] = 0.0
    return out


# ── image loading ────────────────────────────────────────────────────────────
def load_examples():
    """Return (images_array, true_labels, filenames)."""
    images, labels, names = [], [], []
    for label_idx, folder_name in enumerate(LABEL_LIST):
        folder = EXAMPLES_DIR / folder_name
        for png_path in sorted(folder.glob("*.png")):
            img = Image.open(png_path).convert("L").resize(
                (IMG_W, IMG_DIM), Image.LANCZOS
            )
            arr = np.asarray(img, dtype=np.float32)
            arr = preprocess_k2(arr)
            arr = arr[..., np.newaxis]          # (H, W, 1)
            images.append(arr)
            labels.append(label_idx)
            names.append(png_path.name)
    return np.stack(images, axis=0), np.array(labels), names


# ── model building (mirrors micassess.build_models for K2/center) ────────────
def build_models():
    import tensorflow as tf
    try:
        import tf_keras as keras
    except ImportError:
        keras = tf.keras

    from tf_keras.models import load_model, Model
    from tf_keras.layers import Input, Cropping2D, Concatenate, Lambda
    from cryoassess.lib import fft as fft_lib

    base_path   = glob.glob(str(WEIGHTS_DIR / "base_*"))[0]
    binary_path = glob.glob(str(WEIGHTS_DIR / "fine_binary_*"))[0]
    good_path   = glob.glob(str(WEIGHTS_DIR / "fine_good_*"))[0]
    bad_path    = glob.glob(str(WEIGHTS_DIR / "fine_bad_*"))[0]

    inputs = Input(shape=(IMG_DIM, IMG_W, 1))
    crop   = Cropping2D(cropping=((0, 0), (9, 9)))(inputs)   # K2/center

    raw_base = load_model(base_path)
    raw_base = Model(raw_base.inputs, raw_base.layers[-2].output)
    r_features = raw_base(crop, training=False)

    f_features = Lambda(fft_lib.radavg_logps_sigmoid_tf, name="f_features")(crop)
    f_features = tf.reshape(f_features, (tf.shape(inputs)[0], 247))

    features   = Concatenate(axis=1)([r_features, f_features])
    base_model = Model(inputs, features)

    binary_head = load_model(binary_path)
    good_head   = load_model(good_path)
    bad_head    = load_model(bad_path)

    return base_model, binary_head, good_head, bad_head


# ── label assignment (from micassess.assign_label) ──────────────────────────
def assign_label(prob, fine_good_prob, fine_bad_prob, t1=T1, t2=T2):
    if prob[0] <= (1 - t1):          # "good" side of binary head
        return 0 if fine_good_prob[0] < (1 - t2) else 1
    return int(np.argmax(fine_bad_prob)) + 2


# ── benchmark ────────────────────────────────────────────────────────────────
def run_benchmark():
    print("=" * 60)
    print("  MicAssess Benchmark — Example Images (K2, t1=0.1, t2=0.1)")
    print("=" * 60)

    # Load examples
    t0 = time.time()
    images, true_labels, filenames = load_examples()
    print(f"\nLoaded {len(images)} images in {time.time()-t0:.1f}s")
    for i, name in enumerate(LABEL_LIST):
        n = int(np.sum(true_labels == i))
        print(f"  [{i}] {name}: {n} images")

    # Build models
    print("\nBuilding models...")
    t0 = time.time()
    base_model, binary_head, good_head, bad_head = build_models()
    print(f"  Done in {time.time()-t0:.1f}s")

    # Run prediction
    print("\nRunning prediction...")
    t0 = time.time()
    features        = base_model.predict(images, verbose=0)
    probs           = binary_head.predict(features, verbose=0)
    fine_good_probs = good_head.predict(features, verbose=0)
    fine_bad_probs  = bad_head.predict(features, verbose=0)
    inference_time  = time.time() - t0
    print(f"  Inference for {len(images)} images: {inference_time:.2f}s  "
          f"({inference_time/len(images)*1000:.0f} ms/image)")

    # Assign labels
    pred_labels = np.array([
        assign_label(probs[i], fine_good_probs[i], fine_bad_probs[i])
        for i in range(len(images))
    ])

    # ── Results ──────────────────────────────────────────────────────────────
    overall_acc = float(np.mean(pred_labels == true_labels))
    print(f"\nOverall accuracy: {overall_acc*100:.1f}%  ({int(np.sum(pred_labels==true_labels))}/{len(images)})")

    # Per-class accuracy
    print("\nPer-class results:")
    print(f"  {'Class':<55} {'GT':>3}  {'Corr':>4}  {'Acc':>6}")
    print("  " + "-" * 72)
    per_class = {}
    for i, name in enumerate(LABEL_LIST):
        mask    = true_labels == i
        correct = int(np.sum(pred_labels[mask] == i))
        total   = int(np.sum(mask))
        acc     = correct / total if total else 0.0
        per_class[name] = {"total": total, "correct": correct, "accuracy": acc}
        print(f"  {name:<55} {total:>3}  {correct:>4}  {acc*100:>5.1f}%")

    # Confusion matrix
    n = len(LABEL_LIST)
    cm = np.zeros((n, n), dtype=int)
    for t, p in zip(true_labels, pred_labels):
        cm[t, p] += 1

    print("\nConfusion matrix (rows=true, cols=predicted):")
    header = "      " + "".join(f"{i:>5}" for i in range(n))
    print(header)
    for i, row in enumerate(cm):
        print(f"  [{i}]  " + "".join(f"{v:>5}" for v in row))

    # Per-image detail
    print("\nPer-image predictions:")
    print(f"  {'File':<60} {'True':>4}  {'Pred':>4}  {'Match':>5}")
    print("  " + "-" * 77)
    for fname, true_l, pred_l in zip(filenames, true_labels, pred_labels):
        match = "OK" if true_l == pred_l else "FAIL"
        print(f"  {fname:<60} {true_l:>4}  {pred_l:>4}  {match:>5}")

    # Save JSON results
    results = {
        "overall_accuracy": overall_acc,
        "inference_time_seconds": inference_time,
        "ms_per_image": inference_time / len(images) * 1000,
        "num_images": len(images),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "predictions": [
            {"file": f, "true": int(t), "pred": int(p)}
            for f, t, p in zip(filenames, true_labels, pred_labels)
        ],
    }
    out_path = Path(__file__).parent / "benchmark_results.json"
    with open(out_path, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nResults saved to {out_path}")
    print("=" * 60)
    return results


if __name__ == "__main__":
    run_benchmark()
