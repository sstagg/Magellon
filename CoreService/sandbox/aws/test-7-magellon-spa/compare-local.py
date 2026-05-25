#!/usr/bin/env python3
"""
Compare magellon-spa local outputs against RELION reference outputs.

Reads:
  - Local:   sandbox/aws/test-7-magellon-spa/outputs-local/{Class2D,Class3D,Refine3D}/
  - RELION:  magellon-rust-mrc/sandbox/relion-oracle/data/pipeline/{Class2D,Class3D,Refine3D}/

Computes greedy-bipartite-match correlation per class. Same comparison
the magellon-rust-mrc oracle tests do, but on the end-to-end pipeline
output (vs single-iteration consistency).
"""

import os
import sys
import numpy as np
import mrcfile
from itertools import permutations

LOCAL = os.path.dirname(os.path.abspath(__file__))
LOCAL_OUT = os.path.join(LOCAL, "outputs-local")
RELION_REF = os.path.normpath(
    os.path.join(LOCAL, "..", "..", "..", "..", "..",
                 "magellon-rust-mrc", "sandbox", "relion-oracle", "data", "pipeline")
)


def correlation(a, b):
    a = a.flatten().astype(np.float64)
    b = b.flatten().astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    denom = np.sqrt((a * a).sum() * (b * b).sum())
    return 0.0 if denom < 1e-12 else float((a * b).sum() / denom)


def greedy_match(corr):
    k = corr.shape[0]
    used_i = [False] * k
    used_j = [False] * k
    pairs = []
    for _ in range(k):
        best = (-2.0, 0, 0)
        for i in range(k):
            if used_i[i]:
                continue
            for j in range(k):
                if used_j[j]:
                    continue
                if corr[i, j] > best[0]:
                    best = (corr[i, j], i, j)
        used_i[best[1]] = True
        used_j[best[2]] = True
        pairs.append((best[1], best[2], best[0]))
    return pairs, np.mean([p[2] for p in pairs])


def load_mrcs(path):
    """Multi-section MRC file → np.array of shape (K, n, n)."""
    with mrcfile.open(path, permissive=True) as f:
        return np.array(f.data)


def load_mrc(path):
    """Single-volume MRC → np.array of shape (n, n, n)."""
    with mrcfile.open(path, permissive=True) as f:
        return np.array(f.data)


def compare_class2d():
    ours = os.path.join(LOCAL_OUT, "Class2D", "classes.mrcs")
    theirs = os.path.join(RELION_REF, "Class2D", "run_it005_classes.mrcs")
    if not (os.path.exists(ours) and os.path.exists(theirs)):
        print(f"Class2D: skipped (ours={os.path.exists(ours)}, relion={os.path.exists(theirs)})")
        return
    a = load_mrcs(ours)
    b = load_mrcs(theirs)
    print(f"Class2D: ours={a.shape}, relion={b.shape}")
    if a.shape != b.shape:
        print("  shape mismatch — can't compare directly")
        return
    k = a.shape[0]
    corr = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            corr[i, j] = correlation(a[i], b[j])
    pairs, mean_corr = greedy_match(corr)
    high = sum(1 for _, _, c in pairs if c > 0.7)
    med = sum(1 for _, _, c in pairs if c > 0.4)
    print(f"  greedy match: mean = {mean_corr:.3f}, {high}/{k} at corr > 0.7, {med}/{k} at corr > 0.4")
    for i, j, c in sorted(pairs, key=lambda p: -p[2])[:5]:
        print(f"    ours[{i:2d}] vs relion[{j:2d}]  corr = {c:.3f}")


def compare_class3d():
    rel_dir = os.path.join(RELION_REF, "Class3D")
    rel_files = sorted([f for f in os.listdir(rel_dir) if f.startswith("run_it005_class") and f.endswith(".mrc")])
    ours_dir = os.path.join(LOCAL_OUT, "Class3D")
    if not os.path.isdir(ours_dir):
        print("Class3D: skipped (no local output)")
        return
    ours_files = sorted([f for f in os.listdir(ours_dir) if f.startswith("class") and f.endswith(".mrc")])
    if not ours_files or not rel_files:
        print(f"Class3D: skipped (ours={len(ours_files)}, relion={len(rel_files)})")
        return
    a = np.stack([load_mrc(os.path.join(ours_dir, f)) for f in ours_files])
    b = np.stack([load_mrc(os.path.join(rel_dir, f)) for f in rel_files])
    print(f"Class3D: ours={a.shape}, relion={b.shape}")
    if a.shape != b.shape:
        print("  shape mismatch — can't compare directly")
        return
    k = a.shape[0]
    corr = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            corr[i, j] = correlation(a[i], b[j])
    pairs, mean_corr = greedy_match(corr)
    print(f"  greedy match: mean = {mean_corr:.3f}")
    for i, j, c in sorted(pairs, key=lambda p: -p[2]):
        print(f"    ours[{i}] vs relion[{j}]  corr = {c:.3f}")


def compare_refine3d():
    ours = os.path.join(LOCAL_OUT, "Refine3D", "final.mrc")
    theirs = os.path.join(RELION_REF, "Refine3D", "run_class001.mrc")
    if not (os.path.exists(ours) and os.path.exists(theirs)):
        print(f"Refine3D: skipped (ours={os.path.exists(ours)}, relion={os.path.exists(theirs)})")
        return
    a = load_mrc(ours)
    b = load_mrc(theirs)
    print(f"Refine3D: ours={a.shape}, relion={b.shape}")
    if a.shape != b.shape:
        print("  shape mismatch")
        return
    print(f"  full-resolution correlation = {correlation(a, b):.3f}")


def report_timings():
    """Read timing.txt from each stage's output dir."""
    print("\n=== per-stage wall-clock ===")
    for stage in ["Class2D", "Class3D", "Refine3D", "CtfRefine"]:
        timing = os.path.join(LOCAL_OUT, stage, "timing.txt")
        if os.path.exists(timing):
            with open(timing) as f:
                print(f"  {f.read().strip()}")


if __name__ == "__main__":
    print("=== magellon-spa local vs RELION reference ===")
    compare_class2d()
    print()
    compare_class3d()
    print()
    compare_refine3d()
    report_timings()
