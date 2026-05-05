"""Pure FFT computation for the FFT plugin.

Mirror of the algorithm in ``CoreService/services/mrc_image_service.py``
and ``magellon_ctf_plugin/service/fft_service.py``. Kept local here so
the plugin has no runtime dependency on CoreService — the plugin runs
as its own process.

Single input image → single PNG of the centered log-magnitude FFT,
downsampled to ``height``.
"""
from __future__ import annotations

import os
from pathlib import Path

import mrcfile
import numpy as np
import scipy
from PIL import Image
from scipy.fft import fft2
from tifffile import TiffFile

from magellon_sdk.paths import from_canonical_gpfs_path


def _resolve_local_path(path: str) -> str:
    """Translate the canonical wire path to whatever this deployment
    actually has on disk.

    On Linux + Docker (the default ``/gpfs`` bind mount) this is a
    no-op. On Windows direct-run with ``MAGELLON_GPFS_PATH=C:/magellon/gpfs``
    it rewrites ``/gpfs/foo.mrc`` → ``C:/magellon/gpfs/foo.mrc``. The
    plugin's settings YAML (``configs/settings_dev.yml``) drives the
    decision via :class:`BaseAppSettings.MAGELLON_GPFS_PATH`.
    """
    gpfs_path = None
    try:
        from core.settings import AppSettingsSingleton
        gpfs_path = AppSettingsSingleton.get_instance().MAGELLON_GPFS_PATH
    except Exception:  # noqa: BLE001 — keep compute callable in unit tests
        pass
    return from_canonical_gpfs_path(path, gpfs_path=gpfs_path) or path


def _load_image_array(abs_path: str) -> np.ndarray:
    """Load mrc / tiff / png → 2D float array. Extension-driven."""
    abs_path = _resolve_local_path(abs_path)
    ext = Path(abs_path).suffix.lower()
    if ext in (".mrc", ".mrcs"):
        with mrcfile.open(abs_path, permissive=True) as mrc:
            data = mrc.data
            return data.reshape(data.shape[-2], data.shape[-1])
    if ext in (".tif", ".tiff"):
        with TiffFile(abs_path) as tiff:
            return np.asarray(tiff.asarray())
    if ext in (".png", ".jpg", ".jpeg"):
        return np.asarray(Image.open(abs_path).convert("L"))
    raise ValueError(f"Unsupported image extension for FFT: {ext}")


def down_sample(img: np.ndarray, height: int) -> np.ndarray:
    m, n = img.shape[-2:]
    ds_factor = m / height
    width = round(n / ds_factor / 2) * 2
    F = np.fft.rfft2(img)
    A = F[..., 0 : height // 2, 0 : width // 2 + 1]
    B = F[..., -height // 2 :, 0 : width // 2 + 1]
    F = np.concatenate([A, B], axis=0)
    return np.fft.irfft2(F, s=(height, width))


def compute_file_fft(
    image_path: str,
    abs_out_file_name: str,
    height: int = 1024,
) -> str:
    """Compute FFT of ``image_path`` and save the log-magnitude PNG at
    ``abs_out_file_name``. Returns the output path on success."""
    mic = _load_image_array(image_path).astype(float)
    F1 = fft2(mic)
    F2 = scipy.fft.fftshift(F1)
    new_img = np.log(1 + np.abs(F2))

    f = down_sample(new_img, height)
    # Normalize to 0-255 uint8 for greyscale PNG; sidesteps matplotlib.
    f = np.abs(f)
    f_min, f_max = float(f.min()), float(f.max())
    if f_max - f_min < 1e-12:
        scaled = np.zeros_like(f, dtype=np.uint8)
    else:
        scaled = ((f - f_min) / (f_max - f_min) * 255.0).astype(np.uint8)

    os.makedirs(os.path.dirname(abs_out_file_name) or ".", exist_ok=True)
    Image.fromarray(scaled, mode="L").save(abs_out_file_name)
    return abs_out_file_name
