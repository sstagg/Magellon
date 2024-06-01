import h5py
import mrcfile
import starfile
import cv2
import os
import cProfile
import torch
import shutil

import numpy as np
import pandas as pd
import matplotlib as mpl

from matplotlib import pyplot as plt
from tqdm import tqdm

from train import sequence5, MRCNetwork
import dataset

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
        # print(np.sqrt(img.shape)[0])
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

    height, width = img.shape
    
    M = cv2.getRotationMatrix2D((width/2, height/2), 0, factor)
    return cv2.warpAffine(img, M, img.shape[::-1], borderMode=cv2.BORDER_REPLICATE)

def compute_class_dist(particles, passthrough):
    
    pass

        

def main():
    mpl.use('TkAgg')

    hdf5_path = '/nfs/home/khom/data120.hdf5'
    h5_dataset = h5py.File(hdf5_path, 'r')['data/images']

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

    hdf5_path = '/nfs/home/khom/data-vlen2.hdf5'
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

def main3(replace_existing=False):
    '''
    Visualize differing quality of images, for a given particle
    Useful for subjectively determining the "scale" of manually scoring an image.
    '''

    n_particles = 5
    scores = np.arange(0, 1.1, step=0.1)
    data_path =  '/nfs/home/khom/data'
    hdf5_path = '/nfs/home/khom/data-vlen-same.hdf5'
    labeled_img_dir = 'labeled-images'

    if replace_existing:
        shutil.rmtree(labeled_img_dir, ignore_errors=True)
        # if os.path.exists(labeled_img_dir):
        #     os.rmdir(labeled_img_dir)
        print('Removed existing labeled image directory')

    os.makedirs(labeled_img_dir, exist_ok=True)
    
    particles = tuple(np.random.choice(os.listdir(data_path), size=n_particles, replace=False))
    targets = pd.read_hdf(hdf5_path, 'targets')


    images = dataset.MRCImageDataset(
        mode='hdf5',
        hdf5_path=hdf5_path,
        use_features=True,
        transform=lambda arr: torch.Tensor(arr[0]).unsqueeze(0)
    )

    sample_targets = targets[targets['img_name'].str.startswith(particles)]
    sample_targets['particle_name'] = sample_targets['img_name'].str.extract(r'([A-z0-9]+)_\d+')

    def sample_particle_imgs(df):
        closest_score_idx = lambda scores, target: np.argmin(np.abs(scores-target))
        desired_idx = [closest_score_idx(df['score'], s) for s in scores]

        return df.iloc[desired_idx]


    samples = sample_targets.groupby('particle_name').apply(sample_particle_imgs)

    # print(samples.index.get_level_values(0))
    # print(samples.loc[samples.index.get_level_values(0)[0]])

    for particle_name in set(samples.index.get_level_values(0)):
        sampled_particles = samples.loc[particle_name]
        
        num_subplots = 12 # number of subplots per plot
        rows, cols = 3, 4
        fig, axes = plt.subplots(rows, cols)
        fig.suptitle(f'Particle: {particle_name}')
        fig.subplots_adjust(hspace=0.4)
        fig.subplots_adjust(wspace=0.4)

        for i in range(len(sampled_particles)):
            img_label = targets.iloc[sampled_particles.index[i]]['score']
            img, _, _ = images[sampled_particles.index[i]]

            ax = axes[i//cols, i%cols]
            ax.axis('off')
            ax.imshow(img[0][0], cmap='gray')
            ax.set_title(f'{img_label :.4f}')

        fig.savefig(f'{labeled_img_dir}/{particle_name}.png')
        print(f'Finished {particle_name}')






if __name__ == '__main__':
    # cProfile.run('main()')
    # main()

    # test_ragged_input()
    # main1()
    main3(replace_existing=False)

