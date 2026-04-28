from __future__ import annotations

import numpy as np


def read_mrc(path: str) -> np.ndarray:
    with open(path, "rb") as handle:
        header = np.fromfile(handle, dtype=np.int32, count=256)
        if header.size < 4:
            raise ValueError("Invalid MRC file: header too short")
        nx, ny, nz, mode = map(int, header[:4])
        dtype_map = {
            0: np.int8,
            1: np.int16,
            2: np.float32,
            6: np.uint16,
        }
        if mode not in dtype_map:
            raise ValueError(f"Unsupported MRC mode: {mode}")
        handle.seek(1024)
        data = np.fromfile(handle, dtype=dtype_map[mode], count=nx * ny * max(1, nz))
    if data.size != nx * ny * max(1, nz):
        raise ValueError("Invalid MRC file: unexpected data length")
    if nz <= 1:
        return data.reshape((ny, nx)).astype(np.float32)
    return data.reshape((nz, ny, nx)).astype(np.float32)
