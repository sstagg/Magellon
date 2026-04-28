from __future__ import annotations

import math

import numpy as np
import scipy.ndimage

import models

Blob = models.Blob


def _calc_perimeter(component_mask: np.ndarray) -> float:
    perimeter = 0.0
    rows, cols = component_mask.shape
    for row in range(rows):
        for col in range(cols):
            if not component_mask[row, col]:
                continue
            neighbors = 0
            if row > 0 and component_mask[row - 1, col]:
                neighbors += 1
            if row < rows - 1 and component_mask[row + 1, col]:
                neighbors += 1
            if col > 0 and component_mask[row, col - 1]:
                neighbors += 1
            if col < cols - 1 and component_mask[row, col + 1]:
                neighbors += 1
            perimeter += 4 - neighbors
    return perimeter


def find_blobs(
    correlation: np.ndarray,
    threshold_mask: np.ndarray,
    border: int = 20,
    max_blobs: int = 100,
    max_blob_size: int = 50,
    min_blob_size: int = 0,
    min_blob_roundness: float = 0.8,
) -> list[Blob]:
    labeled, count = scipy.ndimage.label(threshold_mask.astype(bool), structure=np.ones((3, 3), dtype=np.int8))
    blobs: list[Blob] = []

    for label_index in range(1, count + 1):
        component_mask = labeled == label_index
        coords = np.argwhere(component_mask)
        if coords.size == 0:
            continue

        row_min, col_min = coords.min(axis=0)
        row_max, col_max = coords.max(axis=0)
        if (
            row_min < border
            or col_min < border
            or row_max >= correlation.shape[0] - border
            or col_max >= correlation.shape[1] - border
        ):
            continue

        size = int(coords.shape[0])
        if size < min_blob_size:
            continue
        if max_blob_size > 0 and size > max_blob_size:
            continue

        values = correlation[component_mask]
        mean = float(values.mean())
        stddev = float(values.std())
        center = tuple(map(float, scipy.ndimage.center_of_mass(component_mask.astype(np.float32))))
        maxpos_local = np.argmax(values)
        max_coords = coords[maxpos_local]
        maximum_position = (int(max_coords[0]), int(max_coords[1]))
        perimeter = _calc_perimeter(component_mask)
        roundness = 0.0 if perimeter == 0 else float((4.0 * math.pi * size) / (perimeter * perimeter))
        if roundness < min_blob_roundness:
            continue

        blobs.append(
            Blob(
                center=center,
                size=size,
                mean=mean,
                stddev=stddev,
                roundness=roundness,
                maximum_position=maximum_position,
                label_index=label_index,
            )
        )

    blobs.sort(key=lambda blob: blob.mean, reverse=True)
    if max_blobs > 0:
        blobs = blobs[:max_blobs]
    return blobs
