"""Projection kernels for generating cryo-EM-like Euler-dependent images."""

from __future__ import annotations

import sys
from typing import Sequence

import numpy as np
from scipy.ndimage import affine_transform, map_coordinates

from .geometry import relion_euler_to_matrix


def project_volume(
    volume: np.ndarray,
    rot: float,
    tilt: float,
    psi: float,
    interpolation: int = 1,
) -> np.ndarray:
    """
    Create a single 2D projection from a 3D MRC volume.

    Parameters:
      - volume: expected shape (Z, Y, X)
      - rot, tilt, psi: RELION Euler angles in degrees
      - interpolation: scipy affine_transform spline order
    """
    if volume.ndim != 3:
        raise ValueError("Input volume must be 3D.")
    if interpolation < 0 or interpolation > 5:
        raise ValueError("interpolation order must be in range [0, 5]")

    # Convert to (X, Y, Z) for consistent XYZ matrix math.
    vol_xyz = np.transpose(volume, (2, 1, 0))
    shape = vol_xyz.shape
    nx, ny, nz = shape

    rot_matrix = relion_euler_to_matrix(rot, tilt, psi)
    affine = rot_matrix.T

    center = np.array([nx / 2.0, ny / 2.0, nz / 2.0], dtype=np.float64)
    offset = center - np.dot(affine, center)

    # Rotate around image center and use the same shape so output stacks align.
    rotated = affine_transform(
        vol_xyz,
        matrix=affine,
        offset=offset,
        order=interpolation,
        mode="constant",
        cval=0.0,
        prefilter=interpolation > 1,
    )

    # Beam direction is along Z after rotation in this convention.
    projection = rotated.sum(axis=2)

    # Return (Y, X) to match standard image conventions.
    return np.asarray(projection.T, dtype=np.float32)


def _fftfreq_centered(n: int) -> np.ndarray:
    return np.fft.fftshift(np.fft.fftfreq(n)).astype(np.float64) * n


def _pad_volume_zero(volume: np.ndarray, pad_factor: int = 2) -> np.ndarray:
    if pad_factor <= 1:
        return np.asarray(volume, dtype=np.float32)

    nz, ny, nx = volume.shape
    pz, py, px = pad_factor * nz, pad_factor * ny, pad_factor * nx
    padded = np.zeros((pz, py, px), dtype=np.float32)
    z0 = (pz - nz) // 2
    y0 = (py - ny) // 2
    x0 = (px - nx) // 2
    padded[z0 : z0 + nz, y0 : y0 + ny, x0 : x0 + nx] = volume
    return padded


def _sample_complex_volume(F: np.ndarray, coords_zyx: np.ndarray, order: int = 3) -> np.ndarray:
    real = map_coordinates(
        F.real,
        coords_zyx,
        order=order,
        mode="constant",
        cval=0.0,
        prefilter=(order > 1),
    )
    imag = map_coordinates(
        F.imag,
        coords_zyx,
        order=order,
        mode="constant",
        cval=0.0,
        prefilter=(order > 1),
    )
    return real + 1j * imag


def project_volume_fft_reference(
    volume: np.ndarray,
    rot: float,
    tilt: float,
    psi: float,
    pad_factor: int = 2,
    interpolation: int = 3,
    output_size: int | None = None,
) -> np.ndarray:
    if volume.ndim != 3:
        raise ValueError("Input volume must be 3D.")
    if interpolation < 0 or interpolation > 5:
        raise ValueError("interpolation order must be in range [0, 5]")

    V = np.asarray(volume, dtype=np.float32)
    padded = _pad_volume_zero(V, pad_factor=pad_factor)
    spectrum = np.fft.fftshift(
        np.fft.fftn(np.fft.ifftshift(padded), axes=(0, 1, 2))
    )
    return project_volume_fft_reference_from_state(
        spectrum_shifted=spectrum,
        original_shape=V.shape,
        rot=rot,
        tilt=tilt,
        psi=psi,
        output_size=output_size,
        interpolation=interpolation,
    )


def prepare_fft_reference_state(
    volume: np.ndarray,
    pad_factor: int = 2,
) -> tuple[np.ndarray, tuple[int, int, int]]:
    V = np.asarray(volume, dtype=np.float32)
    padded = _pad_volume_zero(V, pad_factor=pad_factor)
    spectrum = np.fft.fftshift(
        np.fft.fftn(np.fft.ifftshift(padded), axes=(0, 1, 2))
    )
    return spectrum, V.shape


def project_volume_fft_reference_from_state(
    spectrum_shifted: np.ndarray,
    original_shape: tuple[int, int, int],
    rot: float,
    tilt: float,
    psi: float,
    interpolation: int = 3,
    output_size: int | None = None,
) -> np.ndarray:
    if spectrum_shifted.ndim != 3:
        raise ValueError("spectrum_shifted must be 3D.")
    if interpolation < 0 or interpolation > 5:
        raise ValueError("interpolation order must be in range [0, 5]")

    nz, ny, nx = spectrum_shifted.shape
    if not (nz == ny == nx):
        raise ValueError("fft-reference path currently requires a cubic padded volume.")

    n = nx
    m = n if output_size is None else int(output_size)
    if m <= 0:
        raise ValueError("output_size must be a positive integer.")

    u = _fftfreq_centered(m)
    v = _fftfreq_centered(m)
    uu, vv = np.meshgrid(u, v, indexing="xy")
    plane_pts = np.stack(
        [uu.ravel(), vv.ravel(), np.zeros(m * m, dtype=np.float64)],
        axis=0,
    )

    R = relion_euler_to_matrix(rot, tilt, psi)
    xyz = R.T @ plane_pts

    cx = (nx - 1) / 2.0
    cy = (ny - 1) / 2.0
    cz = (nz - 1) / 2.0
    x_idx = xyz[0] + cx
    y_idx = xyz[1] + cy
    z_idx = xyz[2] + cz
    coords_zyx = np.vstack([z_idx, y_idx, x_idx])

    slice_2d = _sample_complex_volume(
        spectrum_shifted, coords_zyx, order=interpolation
    ).reshape((m, m))
    projection = np.fft.fftshift(np.fft.ifft2(np.fft.ifftshift(slice_2d))).real
    image = np.asarray(projection, dtype=np.float32)

    target_x, target_y = original_shape[1], original_shape[2]
    if target_x > image.shape[0] or target_y > image.shape[1]:
        raise ValueError("fft-reference output is smaller than original projection shape.")
    return _center_crop_2d(image, target_x, target_y)


def _build_fft_grid(shape):
    nx, ny, nz = shape
    x = (np.arange(nx, dtype=np.float64) - nx / 2.0) / nx
    y = (np.arange(ny, dtype=np.float64) - ny / 2.0) / ny
    xx, yy = np.meshgrid(x, y, indexing="ij")
    return xx.ravel(), yy.ravel(), np.zeros(xx.size, dtype=np.float64)


def project_volume_fft(
    spectrum_shifted: np.ndarray,
    rot: float,
    tilt: float,
    psi: float,
    precomputed_grid: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
    crop_shape: tuple[int, int] | None = None,
    interpolation: int = 1,
) -> np.ndarray:
    """
    FFT-slice projection using the projection-slice theorem.
    spectrum_shifted should be a shifted 3D FFT of a centered (X, Y, Z) volume.
    """
    if spectrum_shifted.ndim != 3:
        raise ValueError("spectrum_shifted must be 3D.")
    if interpolation < 0 or interpolation > 5:
        raise ValueError("interpolation order must be in range [0, 5]")

    nx, ny, nz = spectrum_shifted.shape
    if precomputed_grid is None:
        base_x, base_y, base_z = _build_fft_grid((nx, ny, nz))
    else:
        base_x, base_y, base_z = precomputed_grid

    rot_matrix = relion_euler_to_matrix(rot, tilt, psi)
    base = np.vstack([base_x, base_y, base_z])  # (3, N)
    rotated = rot_matrix.T @ base  # map output frequency plane to input frequency coordinates

    coords = np.empty((3, base_x.size), dtype=np.float64)
    coords[0] = rotated[0] * nx + nx / 2.0
    coords[1] = rotated[1] * ny + ny / 2.0
    coords[2] = rotated[2] * nz + nz / 2.0

    sampled = map_coordinates(
        spectrum_shifted,
        coords,
        order=interpolation,
        mode="wrap",
        cval=0.0,
    )
    plane = sampled.reshape((nx, ny))
    projection = np.fft.ifft2(np.fft.ifftshift(plane))
    image = np.asarray(np.real(projection), dtype=np.float32)

    if crop_shape is None:
        return image.T

    target_x, target_y = crop_shape
    if target_x <= 0 or target_y <= 0:
        return image.T

    cropped = _center_crop_2d(image, target_x, target_y)

    return cropped.T


def project_volume_fft_legacy(
    spectrum_shifted: np.ndarray,
    rot: float,
    tilt: float,
    psi: float,
    precomputed_grid: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None,
    crop_shape: tuple[int, int] | None = None,
    interpolation: int = 1,
) -> np.ndarray:
    """
    Legacy FFT projection path kept for rollback and comparison.
    """
    if spectrum_shifted.ndim != 3:
        raise ValueError("spectrum_shifted must be 3D.")
    if interpolation < 0 or interpolation > 5:
        raise ValueError("interpolation order must be in range [0, 5]")

    nx, ny, nz = spectrum_shifted.shape
    if precomputed_grid is None:
        base_x, base_y, base_z = _build_fft_grid((nx, ny, nz))
    else:
        base_x, base_y, base_z = precomputed_grid

    rot_matrix = relion_euler_to_matrix(rot, tilt, psi)
    base = np.vstack([base_x, base_y, base_z])  # (3, N)
    rotated = rot_matrix.T @ base

    coords = np.empty((3, base_x.size), dtype=np.float64)
    coords[0] = rotated[0] * nx + nx / 2.0
    coords[1] = rotated[1] * ny + ny / 2.0
    coords[2] = rotated[2] * nz + nz / 2.0

    sampled = map_coordinates(
        spectrum_shifted,
        coords,
        order=interpolation,
        mode="wrap",
        cval=0.0,
    )
    plane = sampled.reshape((nx, ny))
    projection = np.fft.ifft2(np.fft.ifftshift(plane))
    image = np.asarray(np.real(projection), dtype=np.float32)

    if crop_shape is None:
        return image.T

    target_x, target_y = crop_shape
    if target_x <= 0 or target_y <= 0:
        return image.T

    cropped = _center_crop_2d(image, target_x, target_y)
    return cropped.T


def _apply_fft_origin_phase_correction(
    spectrum_shifted: np.ndarray,
    shift: tuple[int, int, int],
) -> np.ndarray:
    """
    Undo the phase term introduced by spatially shifting the padded array content.
    """
    sx, sy, sz = shift
    if sx == 0 and sy == 0 and sz == 0:
        return spectrum_shifted

    nx, ny, nz = spectrum_shifted.shape
    fx = (np.arange(nx, dtype=np.float64) - nx / 2.0) / nx
    fy = (np.arange(ny, dtype=np.float64) - ny / 2.0) / ny
    fz = (np.arange(nz, dtype=np.float64) - nz / 2.0) / nz

    phase = np.exp(
        2j
        * np.pi
        * (
            fx[:, None, None] * float(sx)
            + fy[None, :, None] * float(sy)
            + fz[None, None, :] * float(sz)
        )
    )
    return spectrum_shifted * phase


def _center_crop_2d(image: np.ndarray, target_x: int, target_y: int) -> np.ndarray:
    nx, ny = image.shape
    if target_x > nx or target_y > ny:
        raise ValueError("crop_shape cannot exceed plane shape.")
    sx = (nx - target_x) // 2
    sy = (ny - target_y) // 2
    ex = sx + target_x
    ey = sy + target_y
    return image[sx:ex, sy:ey]


def prepare_fft_state(volume_xyz: np.ndarray, padding: float = 1.5):
    """
    Build reusable FFT state for repeated FFT-based projections.
    volume_xyz must be in (X, Y, Z) order.
    """
    if volume_xyz.ndim != 3:
        raise ValueError("volume_xyz must be 3D.")
    padded, orig_shape, shift = _pad_volume(volume_xyz, padding=padding)
    spectrum = np.fft.fftshift(
        np.fft.fftn(np.fft.ifftshift(np.asarray(padded, dtype=np.float64)), axes=(0, 1, 2))
    )
    grid = _build_fft_grid(spectrum.shape)
    return spectrum, grid, orig_shape


def _pad_volume(data: np.ndarray, padding: float) -> tuple[np.ndarray, tuple[int, int, int], tuple[int, int, int]]:
    if padding <= 1.0:
        data_array = np.asarray(data, dtype=np.float64)
        return data_array, tuple(data_array.shape), (0, 0, 0)

    nx, ny, nz = data.shape
    padded_shape = (int(np.ceil(nx * padding)), int(np.ceil(ny * padding)), int(np.ceil(nz * padding)))
    edge_vals = _edge_voxel_mean(data)
    padded = np.full(padded_shape, fill_value=edge_vals, dtype=np.float64)
    start_x = (padded_shape[0] - nx) // 2
    start_y = (padded_shape[1] - ny) // 2
    start_z = (padded_shape[2] - nz) // 2

    padded[
        start_x:start_x + nx,
        start_y:start_y + ny,
        start_z:start_z + nz,
    ] = data
    return padded, (nx, ny, nz), (start_x, start_y, start_z)


def _edge_voxel_mean(data: np.ndarray) -> float:
    if data.size == 0:
        return 0.0

    edges = np.concatenate(
        (
            data[0, :, :].ravel(),
            data[-1, :, :].ravel(),
            data[:, 0, :].ravel(),
            data[:, -1, :].ravel(),
            data[:, :, 0].ravel(),
            data[:, :, -1].ravel(),
        )
    )
    return float(np.mean(edges))


def make_projection_stack(
    volume: np.ndarray,
    eulers: Sequence[Sequence[float]],
    show_progress: bool = True,
) -> np.ndarray:
    if not eulers:
        raise ValueError("No projections requested.")

    projections = []
    total = len(eulers)
    for index, (rot, tilt, psi) in enumerate(eulers, start=1):
        projections.append(
            project_volume(volume, float(rot), float(tilt), float(psi))
        )
        if show_progress:
            finished = index
            progress = (finished / total) * 100.0
            text = f"Projected {finished}/{total} ({progress:.1f}%)"
            end = "\n" if finished == total else "\r"
            print(text, end=end, file=sys.stdout, flush=True)

    return np.stack(projections, axis=0)


def iter_projections(
    volume: np.ndarray,
    eulers: Sequence[Sequence[float]],
    interpolation: int = 1,
    backend: str = "real",
    fft_padding: float = 1.5,
    show_progress: bool = True,
):
    if not eulers:
        raise ValueError("No projections requested.")

    if backend not in {"real", "fft", "fft-legacy", "fft-reference"}:
        raise ValueError("backend must be 'real', 'fft', 'fft-legacy', or 'fft-reference'.")

    precomputed_grid = None
    crop_shape = None
    spectrum = None
    reference_fft = None
    reference_shape = None
    if backend in {"fft", "fft-legacy"}:
        volume_xyz = np.asarray(np.transpose(volume, (2, 1, 0)), dtype=np.float64)
        spectrum, precomputed_grid, orig_shape = prepare_fft_state(volume_xyz, padding=fft_padding)
        crop_shape = orig_shape[:2]
    elif backend == "fft-reference":
        reference_fft, reference_shape = prepare_fft_reference_state(volume, pad_factor=2)

    total = len(eulers)
    for index, (rot, tilt, psi) in enumerate(eulers, start=1):
        if backend == "real":
            projection = project_volume(
                volume,
                float(rot),
                float(tilt),
                float(psi),
                interpolation=interpolation,
            )
        elif backend == "fft-reference":
            projection = project_volume_fft_reference_from_state(
                reference_fft,
                reference_shape,
                float(rot),
                float(tilt),
                float(psi),
                interpolation=interpolation,
            )
        else:
            projector = project_volume_fft if backend == "fft" else project_volume_fft_legacy
            projection = projector(
                spectrum,
                float(rot),
                float(tilt),
                float(psi),
                precomputed_grid=precomputed_grid,
                crop_shape=crop_shape,
                interpolation=interpolation,
            )

        if show_progress:
            progress = (index / total) * 100.0
            text = f"Projected {index}/{total} ({progress:.1f}%)"
            end = "\n" if index == total else "\r"
            print(text, end=end, file=sys.stdout, flush=True)

        yield projection
