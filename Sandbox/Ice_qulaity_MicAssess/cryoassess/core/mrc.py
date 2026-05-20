"""MRC micrograph loading, FFT downsampling, and grayscale conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Union

import mrcfile
import numpy as np
from PIL import Image

PathLike = Union[str, Path]

DEFAULT_HEIGHT = 494  # the fixed input height MicAssess models expect

_EPS = 1e-7


def load_micrograph(path: PathLike) -> np.ndarray:
    """Load an MRC file as a 2-D array, collapsing a singleton stack axis.

    Uses a context manager so the file handle and memory map are released --
    the original code leaked both by calling ``mrcfile.open(...).data`` inline.
    """

    with mrcfile.open(str(path), permissive=True) as mrc:
        data = np.array(mrc.data)
    if data.ndim == 3:
        data = data.reshape(data.shape[-2], data.shape[-1])
    if data.ndim != 2:
        raise ValueError(f"expected a 2-D micrograph, got array shape {data.shape}")
    return data


def load_stack(path: PathLike) -> np.ndarray:
    """Load an MRC(S) file as a 3-D stack ``(n, height, width)``.

    A 2-D file is promoted to a single-slice stack so callers can iterate
    uniformly -- used for RELION 2D class-average stacks.
    """

    with mrcfile.open(str(path), permissive=True) as mrc:
        data = np.array(mrc.data)
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    if data.ndim != 3:
        raise ValueError(f"expected a 2-D or 3-D MRC stack, got shape {data.shape}")
    return data


def fft_downsample(image: np.ndarray, height: int = DEFAULT_HEIGHT) -> np.ndarray:
    """Downsample a 2-D image to ``height`` rows via a Fourier-space crop.

    The width is scaled by the same factor and rounded to an even number so the
    aspect ratio is preserved.
    """

    rows, cols = image.shape[-2:]
    ds_factor = rows / height
    width = round(cols / ds_factor / 2) * 2
    spectrum = np.fft.rfft2(image)
    top = spectrum[..., 0:height // 2, 0:width // 2 + 1]
    bottom = spectrum[..., -height // 2:, 0:width // 2 + 1]
    cropped = np.concatenate([top, bottom], axis=0)
    return np.fft.irfft2(cropped, s=(height, width))


def scale_to_uint8(image: np.ndarray) -> np.ndarray:
    """Linearly rescale an array to the 0-255 ``uint8`` range."""

    array = np.asarray(image, dtype=np.float64)
    span = array.max() - array.min()
    return ((array - array.min()) / (span + _EPS) * 255).astype("uint8")


def to_grayscale_image(image: np.ndarray, height: int = DEFAULT_HEIGHT) -> Image.Image:
    """Downsample a micrograph and return it as an 8-bit grayscale PIL image."""

    return Image.fromarray(scale_to_uint8(fft_downsample(image, height))).convert("L")


def crop_center(image: np.ndarray, crop_w: int, crop_h: int) -> np.ndarray:
    """Crop a ``crop_w`` x ``crop_h`` window from the centre of ``image``."""

    rows, cols = image.shape[0], image.shape[1]
    start_x = cols // 2 - crop_w // 2
    start_y = rows // 2 - crop_h // 2
    return image[start_y:start_y + crop_h, start_x:start_x + crop_w]


def crop_left(image: np.ndarray, crop_w: int, crop_h: int) -> np.ndarray:
    """Crop a ``crop_w`` x ``crop_h`` window flush with the left edge."""

    start_y = image.shape[0] // 2 - crop_h // 2
    return image[start_y:start_y + crop_h, 0:crop_w]


def crop_right(image: np.ndarray, crop_w: int, crop_h: int) -> np.ndarray:
    """Crop a ``crop_w`` x ``crop_h`` window flush with the right edge."""

    rows, cols = image.shape[0], image.shape[1]
    start_y = rows // 2 - crop_h // 2
    return image[start_y:start_y + crop_h, cols - crop_w:cols]
