from __future__ import annotations

import numpy as np

import models

Hole = models.Hole


def circle_stats(image: np.ndarray, coord: tuple[float, float], radius: int) -> dict[str, float] | None:
    row = int(round(coord[0]))
    col = int(round(coord[1]))
    rmin = row - radius
    rmax = row + radius
    cmin = col - radius
    cmax = col + radius
    if rmin < 0 or rmax >= image.shape[0] or cmin < 0 or cmax >= image.shape[1]:
        return None
    subimage = image[rmin : rmax + 1, cmin : cmax + 1]
    rr, cc = np.ogrid[: subimage.shape[0], : subimage.shape[1]]
    center_r = (subimage.shape[0] - 1) / 2.0
    center_c = (subimage.shape[1] - 1) / 2.0
    mask = (rr - center_r) ** 2 + (cc - center_c) ** 2 <= radius * radius
    roi = subimage[mask]
    return {"mean": float(roi.mean()), "std": float(roi.std()), "n": int(roi.size)}


def calc_hole_stats(image: np.ndarray, holes: list[Hole], radius: int = 20) -> list[Hole]:
    valid_holes: list[Hole] = []
    for hole in holes:
        stats = circle_stats(image, hole.stats["center"], radius)
        if stats is None:
            continue
        hole.stats["hole_stat_radius"] = radius
        hole.stats["hole_n"] = stats["n"]
        hole.stats["hole_mean"] = stats["mean"]
        hole.stats["hole_std"] = stats["std"]
        valid_holes.append(hole)
    return valid_holes
