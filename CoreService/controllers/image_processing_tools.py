import numpy as np
from scipy import fftpack
from scipy.ndimage import uniform_filter


def lowpass_filter(image, resolution, pixel_size):
    """
    Apply a low-pass Gaussian filter to a cryo-EM image at a specified resolution.

    Parameters:
    - image: 2D numpy array, the input cryo-EM image.
    - resolution: Target resolution in angstroms.
    - pixel_size: Pixel size in angstroms per pixel.

    Returns:
    - Filtered image as a numpy array with the same shape as input.
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

def box_filter(image,filter_size=3):
    filtered_image = uniform_filter(image, size=filter_size)
    return filtered_image

