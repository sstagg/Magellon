from __future__ import annotations

import math

import numpy as np


class Lattice:
    def __init__(self, firstpoint: tuple[float, float], spacing: float, tolerance: float):
        self.points: list[tuple[float, float]] = []
        self.lattice_points: dict[tuple[int, int], tuple[float, float]] = {}
        self.lattice_points_err: dict[tuple[int, int], float] = {}
        self.center: tuple[float, float] | None = None
        self.tolerance = tolerance
        self.spacing = spacing
        self.t00 = None
        self.t01 = None
        self.t10 = None
        self.t11 = None
        self.matrix: np.ndarray | None = None
        self.angle: float | None = None
        self.add_first_point(firstpoint)

    def raster(self, shape: tuple[int, int] | None = None, layers: int | None = None) -> list[tuple[float, float]]:
        if shape is None and layers is None:
            raise RuntimeError("lattice raster requires shape and/or layers")
        if shape is None:
            maxn = int(layers)
        else:
            maxdist = np.hypot(*shape)
            maxn = int(np.ceil(maxdist / self.spacing))
        if layers is not None:
            maxn = min(maxn, layers)
        if self.center is None or self.matrix is None:
            return []
        points = [self.center]
        for i in range(-maxn, maxn + 1):
            iv0 = i * self.matrix[0, 0]
            iv1 = i * self.matrix[0, 1]
            for j in range(-maxn, maxn + 1):
                if i == 0 and j == 0:
                    continue
                jv0 = j * self.matrix[1, 0]
                jv1 = j * self.matrix[1, 1]
                row = self.center[0] + iv0 + jv0
                col = self.center[1] + iv1 + jv1
                if shape is None or (0 <= row <= shape[0] - 1 and 0 <= col <= shape[1] - 1):
                    points.append((float(row), float(col)))
        return points

    def optimize_raster(
        self,
        all_points: list[tuple[float, float]],
        better_points: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        for better_point in better_points:
            for index, point in enumerate(all_points):
                distance = math.hypot(point[0] - better_point[0], point[1] - better_point[1])
                if distance / self.spacing < self.tolerance:
                    all_points[index] = better_point
                    break
        return all_points

    def add_point(self, newpoint: tuple[float, float]) -> None:
        if len(self.points) == 0:
            self.add_first_point(newpoint)
        elif len(self.points) == 1:
            self.add_second_point(newpoint)
        else:
            self.add_any_point(newpoint)

    def add_first_point(self, firstpoint: tuple[float, float]) -> None:
        self.points.append(firstpoint)
        self.lattice_points[(0, 0)] = firstpoint
        self.lattice_points_err[(0, 0)] = 0.0
        self.center = firstpoint

    def add_second_point(self, secondpoint: tuple[float, float]) -> None:
        if self.center is None:
            return
        if self.matrix is None:
            v0 = secondpoint[0] - self.center[0]
            v1 = secondpoint[1] - self.center[1]
            dist = np.hypot(v0, v1)
            nf = dist / self.spacing
            n = int(round(nf))
            if n == 0:
                return
            err = abs(nf - n)
            if err < self.tolerance:
                point = (n, 0)
                matrix = np.array(((v0 / n, v1 / n), (v1 / n, -v0 / n)), dtype=np.float32)
                self.matrix = matrix
                inv = np.linalg.inv(matrix)
                self.t00 = float(inv[0, 0])
                self.t01 = float(inv[0, 1])
                self.t10 = float(inv[1, 0])
                self.t11 = float(inv[1, 1])
                self.angle = float(np.arctan2(v1, v0))
                self.spacing = float(dist)
                self.lattice_points[point] = secondpoint
                self.lattice_points_err[point] = 0.0
                self.points.append(secondpoint)
        else:
            self.add_any_point(secondpoint)

    def add_any_point(self, point: tuple[float, float]) -> None:
        if self.center is None or None in (self.t00, self.t01, self.t10, self.t11):
            return
        p0 = point[0] - self.center[0]
        p1 = point[1] - self.center[1]
        c0 = p0 * self.t00 + p1 * self.t01
        c1 = p0 * self.t10 + p1 * self.t11
        cint0 = round(c0)
        cint1 = round(c1)
        err0 = c0 - cint0
        err1 = c1 - cint1
        err = float(np.sqrt(err0 * err0 + err1 * err1))

        if err < self.tolerance:
            closest = int(cint0), int(cint1)
            if closest in self.lattice_points_err:
                closestpoint = self.lattice_points[closest]
                closesterr = self.lattice_points_err[closest]
                if closesterr > err:
                    self.points.remove(closestpoint)
                    self.points.append(point)
                    self.lattice_points[closest] = point
                    self.lattice_points_err[closest] = err
            else:
                self.lattice_points[closest] = point
                self.lattice_points_err[closest] = err
                self.points.append(point)


def sort_points_by_distance(points: list[tuple[float, float]], center: tuple[float, float] = (0, 0)) -> list[tuple[float, float]]:
    return sorted(points, key=lambda point: math.hypot(point[0] - center[0], point[1] - center[1]))


def points_to_fake_lattice(points: list[tuple[float, float]]) -> Lattice | None:
    if not points:
        return None
    lattice = Lattice(points[0], 1.0, 0.0)
    if len(points) > 1:
        for point in points[1:]:
            lattice.points.append(point)
        points = sort_points_by_distance(points, center=points[0])
        if len(points) > 2:
            v0 = (points[1][0] - points[0][0], points[1][1] - points[0][1])
            angle = 0.0
            n = 2
            while n < len(points) and (angle < math.radians(10) or math.pi - angle < math.radians(10)):
                v1 = (points[0][0] - points[n][0], points[0][1] - points[n][1])
                mv0 = np.array(v0)
                mv1 = np.array(v1)
                angle = math.acos(mv0.dot(mv1) / (np.linalg.norm(mv0) * np.linalg.norm(mv1)))
                n += 1
            if n == len(points):
                v1 = (v0[1], -v0[0])
        else:
            v0 = (points[1][1] - points[0][1], points[1][0] - points[0][0])
            v1 = (v0[1], -v0[0])
        lattice.matrix = np.array((v0, v1), dtype=np.float32)
    return lattice


def points_to_lattice(
    points: list[tuple[float, float]],
    spacing: float,
    tolerance: float,
    first_is_center: bool = False,
) -> Lattice | None:
    if not points:
        return None
    if first_is_center:
        lattices = [Lattice(points[0], spacing, tolerance)]
    else:
        lattices = [Lattice(point, spacing, tolerance) for point in points]

    for point in points:
        for lattice in lattices:
            lattice.add_point(point)

    if len(points) == 1:
        return lattices[0]

    best_lattice = None
    maxpoints = 1
    for lattice in lattices:
        if len(lattice.points) > maxpoints:
            maxpoints = len(lattice.points)
            best_lattice = lattice
    return best_lattice
