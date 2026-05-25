#!/usr/bin/env python3
"""Compare a Class2D output dir's classes.mrcs against RELION's iter5.

Usage: compare-class2d.py <local_class2d_dir>

Same greedy-bipartite-match correlation as compare-local.py but takes
the output dir as an arg so we can compare A/B runs without juggling
hardcoded paths.
"""
import os
import sys
import numpy as np
import mrcfile

LOCAL = os.path.dirname(os.path.abspath(__file__))
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
    with mrcfile.open(path, permissive=True) as f:
        return np.array(f.data)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: compare-class2d.py <local_class2d_dir>")
    ours_dir = sys.argv[1]
    ours = os.path.join(ours_dir, "classes.mrcs")
    theirs = os.path.join(RELION_REF, "Class2D", "run_it005_classes.mrcs")
    if not (os.path.exists(ours) and os.path.exists(theirs)):
        sys.exit(f"missing: ours={os.path.exists(ours)} relion={os.path.exists(theirs)}")
    a = load_mrcs(ours)
    b = load_mrcs(theirs)
    print(f"{ours_dir}: ours={a.shape}, relion={b.shape}")
    if a.shape != b.shape:
        sys.exit("shape mismatch")
    k = a.shape[0]
    corr = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            corr[i, j] = correlation(a[i], b[j])
    pairs, mean_corr = greedy_match(corr)
    high = sum(1 for _, _, c in pairs if c > 0.7)
    med = sum(1 for _, _, c in pairs if c > 0.4)
    print(f"  greedy match: mean = {mean_corr:.3f}, {high}/{k} at corr > 0.7, {med}/{k} at corr > 0.4")
    for i, j, c in sorted(pairs, key=lambda p: -p[2])[:10]:
        print(f"    ours[{i:2d}] vs relion[{j:2d}]  corr = {c:.3f}")


if __name__ == "__main__":
    main()
