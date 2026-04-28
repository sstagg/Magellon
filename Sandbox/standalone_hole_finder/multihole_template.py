from __future__ import annotations

import math

import numpy as np
import scipy.ndimage
import scipy.signal


class TemplateConvolver:
    def __init__(self) -> None:
        self.single: np.ndarray | None = None
        self.npoint = 1
        self.single_scale = 1.0
        self.unit_vector = np.eye(2, dtype=np.float32)

    def set_single_template(self, array: np.ndarray) -> None:
        self.single = array.astype(np.float32)

    def set_config(self, npoint: int, single_scale: float) -> None:
        self.npoint = max(1, int(npoint))
        self.single_scale = float(single_scale)

    def set_square_unit_vector(self, spacing: float, angle_degrees: float) -> None:
        angle = math.radians(angle_degrees)
        unit_vector = np.array(
            (
                spacing * math.sin(angle),
                -spacing * math.cos(angle),
                spacing * math.cos(angle),
                spacing * math.sin(angle),
            ),
            dtype=np.float32,
        )
        self.unit_vector = unit_vector.reshape((2, 2))

    def get_vectors(self, npoint: int) -> np.ndarray:
        is_odd = bool(npoint % 2)
        vectors = [(-1, -1), (1, 1), (1, -1), (-1, 1)]
        if is_odd:
            base_vectors = [(0, 0), (-1, 0), (1, 0), (0, 1), (0, -1)]
            vectors = base_vectors + vectors
        out = np.array(vectors[:npoint], dtype=np.float32)
        if not is_odd:
            out = out / 2.0
        return out

    def scale_single_template(self) -> np.ndarray:
        if self.single is None:
            raise ValueError("Single template is required")
        return scipy.ndimage.zoom(self.single, self.single_scale)

    def make_lattice_vectors(self) -> np.ndarray:
        vectors = self.get_vectors(self.npoint)
        lattice_vectors = np.zeros(vectors.shape, dtype=np.float32)
        for i, point in enumerate(vectors):
            lattice_vectors[i, 0] = float(np.dot(point, self.unit_vector[0]))
            lattice_vectors[i, 1] = float(np.dot(point, self.unit_vector[1]))
        return lattice_vectors

    def calculate_new_template_shape(self, lattice_vectors: np.ndarray, single_shape: tuple[int, int]) -> tuple[int, int]:
        rows = lattice_vectors[:, 0]
        cols = lattice_vectors[:, 1]
        row_size = int(rows.max() - rows.min()) if rows.size else 0
        col_size = int(cols.max() - cols.min()) if cols.size else 0
        return row_size + single_shape[0], col_size + single_shape[1]

    def make_lattice_image(self, single: np.ndarray) -> np.ndarray:
        lattice_vectors = self.make_lattice_vectors()
        shape = self.calculate_new_template_shape(lattice_vectors, single.shape)
        center = np.array((shape[0] // 2, shape[1] // 2), dtype=np.int32)
        centered_vectors = np.rint(lattice_vectors).astype(np.int32) + center
        image = np.zeros(shape, dtype=np.float32)
        for row, col in centered_vectors:
            if 0 <= row < shape[0] and 0 <= col < shape[1]:
                image[int(row), int(col)] = 1.0
        return image

    def make_multi_template(self) -> np.ndarray:
        single = self.scale_single_template()
        lattice_image = self.make_lattice_image(single)
        template = scipy.signal.fftconvolve(lattice_image, single, mode="same")
        return template.astype(np.float32)
