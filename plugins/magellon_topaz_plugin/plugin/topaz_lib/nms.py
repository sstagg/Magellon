"""Non-maximum suppression on a topaz score map — pure numpy.

Direct port of ``topaz.algorithms.non_maximum_suppression`` (GPL-3.0).
Greedy: walks pixels in descending score order, emits each one and
zeros out everything within radius `r`. Returns ``(scores, coords)``
where ``coords[:, 0]`` is x and ``coords[:, 1]`` is y.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def non_maximum_suppression(x: np.ndarray, r: int,
                            threshold: float = -np.inf) -> Tuple[np.ndarray, np.ndarray]:
    """Return ``(scores, coords)`` of suppression-survivor pixels."""
    width = r
    ii, jj = np.meshgrid(np.arange(-width, width + 1), np.arange(-width, width + 1))
    mask = (ii ** 2 + jj ** 2) <= r * r
    ii = ii[mask]
    jj = jj[mask]
    major_axis = x.shape[1]

    A = x.ravel()
    I = np.argsort(A, axis=None)[::-1]

    suppressed: set = set()
    scores = np.zeros(len(A), dtype=np.float32)
    coords = np.zeros((len(A), 2), dtype=np.int32)

    j = 0
    for i in I:
        if A[i] <= threshold:
            break
        if i not in suppressed:
            xx = i % major_axis
            yy = i // major_axis
            scores[j] = A[i]
            coords[j, 0] = xx
            coords[j, 1] = yy
            j += 1
            y_coords = np.clip(yy + ii, 0, x.shape[0])
            x_coords = np.clip(xx + jj, 0, x.shape[1])
            for y_coord, x_coord in zip(y_coords, x_coords):
                suppressed.add(int(y_coord) * major_axis + int(x_coord))

    return scores[:j], coords[:j]


__all__ = ["non_maximum_suppression"]
