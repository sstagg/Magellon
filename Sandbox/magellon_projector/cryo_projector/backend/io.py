"""I/O helpers for MRC maps."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple

import numpy as np
import mrcfile


@dataclass(frozen=True)
class MRCMeta:
    voxel_size: Tuple[float, float, float]
    header: Dict[str, Any]


def read_mrc(path: str) -> Tuple[np.ndarray, MRCMeta]:
    """Read MRC file and return volume data plus minimal metadata."""
    with mrcfile.open(path, permissive=True) as mrc:
        data = np.array(mrc.data, dtype=np.float32)
        voxel_size = _voxel_size_from_mrc(mrc)
        header = {
            "mean": float(np.mean(data)),
            "rms": float(np.sqrt(np.mean(np.square(data)))) if data.size else 0.0,
            "shape": tuple(int(v) for v in data.shape),
        }
    return data, MRCMeta(voxel_size=voxel_size, header=header)


def write_mrc(data: np.ndarray, path: str, voxel_size: Sequence[float] | None = None):
    """Write a 2D or 3D stack MRC file."""
    payload = np.asarray(data, dtype=np.float32)
    with mrcfile.new(path, overwrite=True) as mrc:
        mrc.set_data(payload)
        if voxel_size is not None:
            voxel_size = _as_voxel_size(voxel_size)
            mrc.voxel_size = voxel_size
        else:
            mrc.voxel_size = (1.0, 1.0, 1.0)


@contextmanager
def open_projection_stack(
    path: str,
    projection_count: int,
    projection_shape,
    voxel_size: Sequence[float] | None = None,
):
    shape = (int(projection_count), int(projection_shape[0]), int(projection_shape[1]))
    payload = np.empty(shape, dtype=np.float32)
    with mrcfile.new(path, overwrite=True) as mrc:
        mrc.set_data(payload)
        if voxel_size is not None:
            mrc.voxel_size = _as_voxel_size(voxel_size)
        else:
            mrc.voxel_size = (1.0, 1.0, 1.0)
        yield mrc


def _voxel_size_from_mrc(mrc) -> Tuple[float, float, float]:
    try:
        candidate = _as_voxel_size(mrc.voxel_size)
        if all(v > 0.0 for v in candidate):
            return candidate
    except (TypeError, ValueError):
        pass
    return _voxel_size_from_header(mrc)


def _voxel_size_from_header(mrc) -> Tuple[float, float, float]:
    """
    Compute voxel spacing from header dimensions. Ignore origin offsets intentionally.
    This avoids brittle behavior from `mrc.voxel_size` implementations across files.
    """
    nx, ny, nz = int(mrc.header.nx), int(mrc.header.ny), int(mrc.header.nz)
    if nx <= 0 or ny <= 0 or nz <= 0:
        raise ValueError("invalid MRC shape in header.")

    try:
        xlen = float(mrc.header.cella.x)
        ylen = float(mrc.header.cella.y)
        zlen = float(mrc.header.cella.z)
    except Exception as exc:
        raise ValueError("missing cell dimensions in header.") from exc

    if xlen <= 0 or ylen <= 0 or zlen <= 0:
        raise ValueError("invalid cell dimensions in header.")

    return (xlen / nx, ylen / ny, zlen / nz)


def _as_voxel_size(voxel_size: Sequence[float]) -> Tuple[float, float, float]:
    values = _flatten_voxel_elements(voxel_size)
    if len(values) == 1:
        return (values[0], values[0], values[0])
    if len(values) == 3:
        return tuple(values)  # type: ignore[return-value]
    raise ValueError("voxel_size must have one value or exactly three values.")


def _flatten_voxel_elements(voxel_size) -> list[float]:
    if isinstance(voxel_size, (int, float, np.integer, np.floating, np.number)):
        return [float(voxel_size)]

    if isinstance(voxel_size, (tuple, list, np.ndarray)):
        items = list(voxel_size)
        if not items:
            raise ValueError("voxel_size cannot be empty.")
        out: list[float] = []
        for item in items:
            out.extend(_flatten_voxel_elements(item))
        return out

    try:
        array_like = np.array(voxel_size).ravel()
        if array_like.ndim == 0:
            return [float(array_like.item())]
        return [float(v) for v in array_like]
    except TypeError as exc:
        raise ValueError("voxel_size must be numeric or a vector of numeric values.") from exc

    scalar = float(voxel_size)  # pragma: no cover - fallback for compatible scalars
    return (scalar, scalar, scalar)
