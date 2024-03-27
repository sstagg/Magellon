import os
from PIL import Image
import mrcfile
import numpy as np
import scipy
from scipy.fft import fft2
import scipy.fftpack
import matplotlib.pyplot as plt


def compute_file_fft(mrc_abs_path, abs_out_file_name, height=1024):
    # Fourier transform of the image
    with mrcfile.open(mrc_abs_path, permissive=True) as mrc:
        mic = mrc.data.reshape(mrc.data.shape[-2], mrc.data.shape[-1])
    F1 = fft2(np.array(mic).astype(float))
    # Shift so that low spatial frequencies are in the center.
    F2 = scipy.fft.fftshift(F1)

    new_img = np.log(1 + abs(F2))

    f = down_sample(new_img, height)
    new_img = Image.fromarray(abs(f))

    plt.imsave(abs_out_file_name, new_img, cmap='gray')
    return


def down_sample(img, height):
    '''
        Downsample 2d array using fourier transform.
        factor is the downsample factor.
        '''
    m, n = img.shape[-2:]
    ds_factor = m / height
    width = round(n / ds_factor / 2) * 2
    F = np.fft.rfft2(img)
    A = F[..., 0:height // 2, 0:width // 2 + 1]
    B = F[..., -height // 2:, 0:width // 2 + 1]
    F = np.concatenate([A, B], axis=0)
    f = np.fft.irfft2(F, s=(height, width))
    return f
