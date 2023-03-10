import numpy as np
import cupy as cp
import mrcfile


def fft_mrc(filename):
    with mrcfile.open(filename) as mrc:
        data = mrc.data.astype(np.float32)
        shape = data.shape
        padded_shape = (cp.fft.next_fast_len(shape[0]), cp.fft.next_fast_len(shape[1]), cp.fft.next_fast_len(shape[2]))
        padded_data = cp.zeros(padded_shape, dtype=np.float32)
        padded_data[:shape[0], :shape[1], :shape[2]] = data
        fft_data = cp.fft.fftn(padded_data)
        return fft_data
