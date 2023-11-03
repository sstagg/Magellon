import h5py
import mrcfile
import starfile
import cv2
import os
import cProfile
import torch

import numpy as np
import pandas as pd
import matplotlib as mpl

from matplotlib import pyplot as plt
from tqdm import tqdm

from train import sequence5, MRCNetwork

def normalize(arr, upper=1, round_int=False):
    mini, maxi = arr.min(), arr.max()
    if mini == maxi:
        return np.zeros_like(arr)
    res = upper * (arr - mini) / (maxi - mini)
    return np.round(res).astype(np.int32) if round_int else res

# Utility function to find the range of brightness of each image
def get_brightness_range(h5_dataset):
    for i in range(len(h5_dataset)):
        img = h5_dataset[i]

        print(img.min(), img.max())

# Utility function to plot an image and is local histogram equalized version 
def plot_img_eq(img):
    img = normalize(img, upper=255).astype(np.uint16)
    img = np.expand_dims(img, -1)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    eq_img = clahe.apply(img)
    
    plt.figure(0)
    plt.imshow(eq_img, cmap='gray')
    plt.figure(1)
    plt.imshow(img, cmap='gray')
    plt.show()

# Utility function to simply plot an image
def plot_img(img, ax=None):
    print(img.min(), img.max(), img.dtype)
    if len(img.shape) == 1:
        print(np.sqrt(img.shape)[0])
        d = np.round(np.sqrt(img.shape)[0]).astype(np.int32)
        img = img.reshape(d,d)
    img = normalize(img, upper=255).astype(np.uint16)

    if ax:
        ax.imshow(img, cmap='gray')
    else:
        plt.imshow(img, cmap='gray')
        plt.show()


def img_zoom_out(img, factor):
    '''
    Zooms out on an image with respect to its center, and fills the borders with black 

    :param img: 2D ndarray of the greyscale image
    :param factor: float representing amount to zoom out (e.g. factor=2.0 means zoom out 2.0x)

    :return: 2D ndarray of the zoomed out image. The shape will be the same as the input image 
    '''

    # First, make a larger black image and place the original image in the middle, then downscale
    # to the original image size

    height, width = img.shape
    # new_height, new_width = round(height*factor), round(width*factor)
    # new_img = np.zeros((new_height, new_width))

    # # (a, b) is the top left corner of the original image, centered in the new enlarged image
    # a, b = (new_height - height) // 2, (new_width - width) // 2
    # new_img[a:a+height, b:b+width] = img

    

    # return cv2.resize(new_img, img.shape, interpolation=cv2.INTER_AREA)

    
    M = cv2.getRotationMatrix2D((width/2, height/2), 0, factor)
    return cv2.warpAffine(img, M, img.shape[::-1], borderMode=cv2.BORDER_REPLICATE)

# Sanity check for passing in batches of images of non-uniform size
def test_ragged_input():

    hdf5_path = '/nfs/home/khom/data-vlen.hdf5'
    h5_dataset = h5py.File(hdf5_path, 'r')['data/images']

    shapes = []
    
    for i in range(len(h5_dataset)):
        w =  round(np.sqrt(h5_dataset[i].shape[0]))


        if w < 31:
            shapes.append(w)
        # print(h5_dataset)

    print(shapes)
    plt.hist(shapes)
    plt.show()
        

def main():
    mpl.use('TkAgg')

    hdf5_path = '/nfs/home/khom/data120.hdf5'
    h5_dataset = h5py.File(hdf5_path, 'r')['data/images']

    # get_brightness_range(h5_dataset)

    # fig, axes = plt.subplots(2, 2)
    # zoomed_out = img_zoom_out(h5_dataset[101], 2.0)
    # # print(h5_dataset[101].shape)
    # plot_img(zoomed_out, ax=axes[0,0])
    # plot_img(h5_dataset[101], ax=axes[0,1])

    # zoomed_in = img_zoom_out(h5_dataset[101], 0.5)
    # plot_img(zoomed_in, ax=axes[1,0])
    # plot_img(h5_dataset[101], ax=axes[1,1])
    
    # plt.show()

    p = '/nfs/home/khom/data/'
    arr = []
    for i, particle_name in tqdm(list(enumerate(os.listdir(p)))):
        
        full_path = os.path.join(p, particle_name, 'run_classes.mrcs')
        model_path = os.path.join(p, particle_name, 'run_model.star')
        if os.path.isfile(full_path):
            # print(f'{i}: Size of {particle_name}: {os.path.getsize(full_path) / (1024*1024) :.4f} MB')
            with mrcfile.open(full_path) as file:
                df = starfile.read(model_path, read_n_blocks=1)
                current_img_size = df["rlnCurrentImageSize"].item()
                arr.append((file.header['nx'].item(), current_img_size))

                # print(f'{file.header["nx"]} ---- {file.data.shape[1]} {file.data.shape[2]} ---- {starfile.read(model_path, read_n_blocks=1)["rlnCurrentImageSize"].item()}')
            # arr.append(starfile.read(full_path, read_n_blocks=1)['rlnCurrentImageSize'].item())
    print(arr)
    plt.hist(arr)
    plt.show()

def main1():
    mpl.use('TkAgg')
    n = 20
    fig, ax = plt.subplots(4,5)

    hdf5_path = '/nfs/home/khom/data210-2.hdf5'
    h5_dataset = h5py.File(hdf5_path, 'r')['data/images']

    ind = np.random.randint(0, len(h5_dataset), size=n)

    for i in range(n):
        plot_img(h5_dataset[ind[i]], ax[i//5, i%5])

    plt.show()

def main2():
    mpl.use('TkAgg')
    n = 20
    fig, ax = plt.subplots(4,5)
    fig0, ax0 = plt.subplots(4,5)

    hdf5_path = '/nfs/home/khom/data210.hdf5'
    h5_dataset = h5py.File(hdf5_path, 'r')['data/images']

    path2 = '/nfs/home/khom/data210.hdf5'

    ind = np.random.randint(0, len(h5_dataset), size=n)

    for i in range(n):
        plot_img(h5_dataset[ind[i]], ax[i//5, i%5])

    plt.show()

if __name__ == '__main__':
    # cProfile.run('main()')
    # main()

    # test_ragged_input()
    main1()

