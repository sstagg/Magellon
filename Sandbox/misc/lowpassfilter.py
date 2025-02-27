#!/usr/bin/env python
import mrcfile
import numpy as np
import scipy.ndimage as ndimage
import scipy.fftpack as fftpack
import sys


def lowpass_filter(image, resolution, pixel_size):
    """
    Apply a low-pass Gaussian filter to a cryo-EM image at a specified resolution.

    Parameters:
    - image: 2D numpy array, the input cryo-EM image.
    - resolution: Target resolution in angstroms.
    - pixel_size: Pixel size in angstroms per pixel.

    Returns:
    - Filtered image.
    """
    # Compute Fourier Transform of the image
    fft_image = fftpack.fftshift(fftpack.fft2(image))

    # Define frequency grid
    ny, nx = image.shape
    y, x = np.ogrid[-ny // 2:ny // 2, -nx // 2:nx // 2]
    freq_radius = np.sqrt(x ** 2 + y ** 2) / max(nx, ny)  # Normalized frequency space

    # Compute sigma in Fourier space
    fc = pixel_size / resolution  # Cutoff frequency in pixels^-1
    sigma = fc / np.sqrt(2 * np.log(2))  # Convert to Gaussian sigma

    # Create Gaussian low-pass filter
    gaussian_filter = np.exp(- (freq_radius ** 2) / (2 * sigma ** 2))

    # Apply filter in Fourier space
    fft_filtered = fft_image * gaussian_filter

    # Inverse FFT to return to real space
    filtered_image = np.real(fftpack.ifft2(fftpack.ifftshift(fft_filtered)))
    filtered_image = filtered_image.astype(np.float32)

    return filtered_image

if __name__ == '__main__':
    in_path=sys.argv[1]
    out_path=sys.argv[2]
    resolution=float(sys.argv[3])
    with mrcfile.open(in_path, permissive=True) as mrc:
        image = np.array(mrc.data, copy=True)
        voxel_size = mrc.voxel_size  # Preserve header information
        pixel_size = voxel_size['x']  # assuming uniform pixel size
        print (pixel_size, image.dtype)
        nx=mrc.header.nx
        ny=mrc.header.ny
        nz=mrc.header.nz
    filtered=(lowpass_filter(image,resolution,pixel_size))

    with mrcfile.new(out_path, overwrite=True) as mrc_processed:
        mrc_processed.set_data(filtered)
        mrc_processed.voxel_size = voxel_size
        mrc_processed.header.nx = nx
        mrc_processed.header.ny = ny
        mrc_processed.header.nz = nz
