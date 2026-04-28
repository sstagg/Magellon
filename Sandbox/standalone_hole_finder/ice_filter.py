from __future__ import annotations

import math

import models

Hole = models.Hole


MIN_INTENSITY = 1e-6


def get_thickness(i0: float, intensity: float) -> float:
    intensity = min(intensity, i0)
    intensity = max(intensity, MIN_INTENSITY)
    return math.log(i0 / intensity)


def get_stdev_thickness(stdev_intensity: float, mean_intensity: float) -> float:
    if stdev_intensity >= mean_intensity:
        return 10.0
    return math.log(mean_intensity / (mean_intensity - stdev_intensity))


def calc_ice_and_filter(
    holes: list[Hole],
    i0: float,
    tmin: float = 0.0,
    tmax: float = 0.1,
    tstdmin: float = 0.05,
    tstdmax: float = 0.5,
) -> tuple[list[Hole], list[Hole]]:
    good_holes: list[Hole] = []
    for hole in holes:
        if "hole_mean" not in hole.stats:
            continue
        mean = float(hole.stats["hole_mean"])
        std = float(hole.stats["hole_std"])
        tm = get_thickness(i0, mean)
        ts = get_stdev_thickness(std, mean)
        hole.stats["thickness-mean"] = tm
        hole.stats["thickness-stdev"] = ts
        hole.stats["good"] = bool((tmin <= tm <= tmax) and (tstdmin <= ts < tstdmax))
        if hole.stats["good"]:
            good_holes.append(hole)
    return holes, good_holes
