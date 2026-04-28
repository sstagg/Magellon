from __future__ import annotations

import math

import lattice
import models

points_to_fake_lattice = lattice.points_to_fake_lattice
points_to_lattice = lattice.points_to_lattice
Blob = models.Blob
Hole = models.Hole
LatticeFitResult = models.LatticeFitResult


def _points_to_holes(points: list[tuple[float, float]]) -> list[Hole]:
    holes: list[Hole] = []
    for index, point in enumerate(points):
        info = {"center": point, "convolved": False}
        holes.append(Hole(center=point, hole_number=index + 1, stats=dict(info), info=info))
    return holes


def _convolve_3x3_with_blob_points(
    points: list[tuple[float, float]],
    image_shape: tuple[int, int],
    spacing: float,
    tolerance: float,
) -> tuple[list[tuple[float, float]], object]:
    if len(points) < 2:
        return [], None
    total_points: list[tuple[float, float]] = []
    best_lattice = None
    vector = (points[1][0] - points[0][0], points[1][1] - points[0][1])
    vector_length = math.hypot(vector[0], vector[1])
    if vector_length == 0:
        return [], None
    scaled_vector = (vector[0] * spacing / vector_length, vector[1] * spacing / vector_length)
    for point in points:
        shifted = (point[0] + scaled_vector[0], point[1] + scaled_vector[1])
        best_lattice = points_to_lattice([point, shifted], spacing, tolerance, first_is_center=True)
        if best_lattice is None:
            continue
        total_points.extend(best_lattice.raster(image_shape, layers=1))
    return total_points, best_lattice


def fit_hole_lattice(
    blobs: list[Blob],
    image_shape: tuple[int, int],
    spacing: float,
    tolerance: float = 0.1,
    extend: str = "off",
) -> LatticeFitResult:
    points = [tuple(blob.center) for blob in blobs]
    if len(points) < 2 and extend != "off":
        return LatticeFitResult(lattice=None, holes=[])

    accept_all = False
    if extend == "3x3":
        best_lattice = True
    else:
        if spacing > 0:
            best_lattice = points_to_lattice(points, spacing, tolerance)
        else:
            center = (image_shape[0] // 2, image_shape[1] // 2)
            points = sorted(points, key=lambda point: math.hypot(point[0] - center[0], point[1] - center[1]))
            best_lattice = points_to_fake_lattice(points)
            accept_all = True

    if best_lattice is None:
        return LatticeFitResult(lattice=None, holes=[])

    if extend == "full":
        if accept_all:
            raise ValueError("Cannot extend unspecified lattice to full")
        raster_points = best_lattice.raster(image_shape)
        raster_points = best_lattice.optimize_raster(raster_points, best_lattice.points)
    elif extend == "3x3":
        if accept_all:
            raise ValueError("Cannot extend unspecified lattice to 3x3")
        raster_points, best_lattice = _convolve_3x3_with_blob_points(points, image_shape, spacing, tolerance)
    else:
        raster_points = best_lattice.points

    holes = _points_to_holes(raster_points)
    return LatticeFitResult(lattice=best_lattice, holes=holes)
