import time
import cv2
import h5py
import os
import numpy as np
import pandas as pd

'''
Miscellaneous convenience functions and classes.
'''

class Timer:
    '''
    Helper class for timing an operation.
    '''

    def __init__(self):
        self.start = 0
        self.reset()

    def reset(self):
        self.start = time.time()
    
    def get_elapsed(self, reset=True):
        elapsed = time.time() - self.start
        if reset:
            self.reset()
        
        return elapsed    

def normalize(arr):
    '''
    Normalize an array to the range [0,1]
    '''
    mini, maxi = arr.min(), arr.max()
    if mini == maxi:
        return np.zeros_like(arr)
    return (arr - mini) / (maxi - mini)


def resize_to_shape(img, new_shape):
    '''
    Resize image to the desired shape while keeping the same zoom. The aspect ratio of the 
    image and the new shape should match (e.g., a square image should always be reshaped
    to a square).

    :param new_shape (tuple):
        Tuple of (height, width) to reshape to.

    :return (array):
        The reshaped array.
    '''

    interpolation = cv2.INTER_AREA \
                        if img.shape[0] > new_shape[0] \
                        else cv2.INTER_CUBIC
    return cv2.resize(img, new_shape, interpolation=interpolation)

def resize_img(img, factor):
    '''
    Rescales an image with respect to its center, while keeping the same zoom. Useful for
    increasing/decreasing pixel resolution.

    :param img: 
        2D ndarray of the greyscale image
    :param factor: 
        Float representing amount to resize (e.g. factor=2.0 means double the number of
        pixels on each dimension, factor=0.5 means halve the number of pixels on each dimension)

    :return (array): 
        2D ndarray of the resized image. The resized shape will be different according to 
        the resize factor 
    '''

    # Resize the image, and then pad it to a standard size
    new_shape = tuple(np.round(np.array(img.shape) * factor).astype(np.int32))
    new_img = resize_to_shape(img, new_shape)
    return new_img


def hdf5_dataset_params(fixed_len=None):
    '''
    Helper function to get HDF5 parameters depending on if the data is variable length or fixed
    length arrays.

    If fixed_len is None, then data is variable length and must be stored as 1D arrays. Otherwise
    data is stored normally, in 2D fixed size (given by fixed_len).
    '''

    if fixed_len is None:
        return {
            'shape': (0,),
            'maxshape': (None,),
            'chunks': (1,),
            'dtype': h5py.vlen_dtype(np.float32)
        }

    else:
        return {
            'shape': (0, fixed_len, fixed_len),
            'maxshape': (None, fixed_len, fixed_len),
            'chunks': (1, fixed_len, fixed_len),
            'dtype': 'f4'
        }
    
def combine_hdf5(dataset_paths, out_path, fixed_len=None):
    '''
    Combine HDF5 datasets into a single one, and writes the resulting data to a new HDF5 dataset.

    :param dataset_paths: 
        List of directories (as strings) of each of the datasets to combine.
    :param out_path: 
        Path to the new combined HDF5 to create/overwrite.
    :param fixed_len: 
        int or None. If int, then the dataset has square images of fixed size. If None,
        then the arrays in the dataset are variable length. 

    :return None:
    '''
    
    data = []
    targets = []
    n = 0
    
    print(f'Combining {len(dataset_paths)} datasets...')
    for path in dataset_paths:
        f = h5py.File(path, 'r')
        data.append(f['data/images'][:])
        targets.append(pd.read_hdf(path, 'targets'))

        n += f['data/images'].shape[0]
        print(f'Finished {path}')
    print()
    
    if os.path.exists(out_path):
        os.remove(out_path)
        print('Removed existing HDF5 file')

    out_file = h5py.File(out_path, 'a')
    dataset_params = hdf5_dataset_params(fixed_len=fixed_len)

    img_dataset = out_file.create_dataset('data/images', **dataset_params)
    img_dataset.resize((n,) if fixed_len is None else (n, fixed_len, fixed_len))

    img_dataset[:] = np.concatenate(data, axis=0)
    all_targets = pd.concat(targets, axis=0)

    out_file.close()
    all_targets.to_hdf(out_path, 'targets')

    print(f'Wrote to {out_path}\n')


def unconvert_labels(pred, weights):
    '''
    Undo the 'calculate_score' function in 'calculate_class_scores' in dataset.py. Categories
    will not necessarily be integers, however

    Converts scores from [0,1] to [1,5], which correspond to the categories:
    1: (A) Best
    2: (B) Decent
    3: (C) Acceptable
    4: (D) Bad
    5: (F) Unusable
    '''

    return -(((pred - weights*0.2) / 0.2) - 5)