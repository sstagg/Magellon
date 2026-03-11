"""Geometry helpers for RELION-style Euler angles."""

from __future__ import annotations

import math
from typing import Iterable, List, Tuple

from scipy.spatial.transform import Rotation

EulerTuple = Tuple[float, float, float]


def relion_euler_to_matrix(rot: float, tilt: float, psi: float):
    """Return a 3x3 rotation matrix from RELION rot, tilt, psi in degrees."""
    # RELION convention: rotate around Z, then Y, then Z (intrinsic convention in scipy).
    # SciPy's lowercase 'zyz' with intrinsic=False uses rotations about fixed axes in order.
    # This matches the standard RELION external convention for many workflows.
    return Rotation.from_euler("ZYZ", [rot, tilt, psi], degrees=True).as_matrix()


def generate_even_eulers(count: int) -> List[EulerTuple]:
    """Generate approximately uniform Euler sampling for a target number of projections."""
    if count <= 0:
        raise ValueError("count must be greater than zero")

    # Fibonacci/spherical sampling gives a near-uniform spread of tilt/rot over the sphere.
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    eulers: List[EulerTuple] = []
    for i in range(count):
        offset = (i + 0.5) / count
        z = 1.0 - 2.0 * offset
        tilt_rad = math.acos(z)
        rot_rad = (i * golden_angle) % (2.0 * math.pi)

        rot = math.degrees(rot_rad) % 360.0
        tilt = math.degrees(tilt_rad)
        psi = (360.0 * i / count) % 360.0
        eulers.append((rot, tilt, psi))

    return eulers


def as_angle_triplets(entries: Iterable[Iterable[float]]) -> List[EulerTuple]:
    """Normalize and validate user-supplied Euler values."""
    normalized = []
    for item in entries:
        item = tuple(item)
        if len(item) != 3:
            raise ValueError(f"Euler entry {item} is invalid; expected 3 values.")
        rot, tilt, psi = map(float, item)
        normalized.append((float(rot), float(tilt), float(psi)))
    return normalized
