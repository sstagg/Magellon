import cv2
import os
import sys
import mrcfile
import starfile
import ray
import time
import itertools
import h5py
import torch
import pandas as pd
import numpy as np
import matplotlib as mpl

from tqdm import tqdm
from matplotlib import pyplot as plt
from torch.utils.data import Dataset, DataLoader

from util import Timer

IMG_DSIZE = (120, 120) # Rescale all images to the same size
REPLACE_INF = 999. # Replace infinity values (inf and -inf) with this constant

'''
Creates and returns the dataset for training the CNN
'''


class MRCImageDataset(Dataset):
    def __init__(self, mode=None, preprocess=False, annotations_file=None, 
                 data_path=None, hdf5_path=None, processed_dir=None,
                 indices=None, use_features=False, 
                 transform=None, target_transform=None):
        '''
        :param mode: it should be either 'normal' or 'hdf5' signifying either
                            listing images in one large directory like normal, or storing everything
                            in an HDF5 file, respectively.
                    if 'normal', the file structure is:☺
                                all images listed in {data_path}/data/
                                annotations stored in {data_path}/targets.csv
                    if 'hdf5', all images and annotations are stored in `data_path`.
                            Within `data.hdf5`, the file structure is:
                                all images listed in /data/images
                                annotations stored in /targets.csv
        :param preprocess: if False, then data_path should be None and no preprocessing 
                            is done; otherwise images and labels will be preprocessed according to `mode`
        :param annotations_file: should be None if preprocess is True. If `preprocess` is True then 
                                annotations will be created as described above.
                                If preprocess is False:
                                    if mode is 'normal', it should be the NAME of the CSV file 
                                        containing target scores for each 2D class. This file should be
                                        directly under `data_path`
                                    if mode is 'hdf5', it should be the name of the Dataset in the
                                    HDF5 file containing the labels DataFrame.
        :param data_path: path to the folder containing raw dataset (default named 'data') 
                            as downloaded from EMPIAR-10812. Should be None if preprocess is False
        :param hdf5_path: path to the resulting HDF5 file, if using mode `hdf5`. If preprocess is True,
                            then this is the path to the HDF5 file to write processed data to
        :param processed_dir: path to the resulting directory of processed images and targests, if using
                        mode `normal`. If preprocess is True, then this is the directory to write 
                        processed images into (in a sub-directory `data/`) and targets/metadata 
                        (in a CSV `targets.csv`)
        :param indices: optional; list of indices used to include only a subset of the data in
                            this Dataset.
        :param use_features: whether or not to include metadata as inputs
        :param transform: as required by pyTorch
        :param target_transform: as required by pyTorch                 
        '''
        print(f'Building MRC image data (mode: {mode}) from {processed_dir if mode == "normal" else hdf5_path}')

        self.mode = mode
        self.transform = transform
        self.target_transform = target_transform

        self.data_path = data_path
        self.hdf5_path = hdf5_path
        self.processed_dir = processed_dir

        
        self.use_features = use_features

        if mode == 'normal':
            if processed_dir is None:
                raise RuntimeError(f'out_data_dir should not be None when in `normal` mode')
            if preprocess:
                out_data_dir = os.path.join(processed_dir, 'data')
                annotations_file = 'targets.csv'
                MRCImageDataset.preprocess_mrc(self.data_path, out_data_dir, annotations_file)

                # self.data_path = os.path.dirname(processed_dir) # Path to processed_data directory
            self.targets = pd.read_csv(os.path.join(processed_dir, annotations_file))

        elif mode == 'hdf5':
            # hdf5_path = '/nfs/home/khom/data.hdf5'
            if preprocess:
                MRCImageDataset.preprocess_mrc_hdf5(self.data_path, hdf5_path)
                # self.data_path = hdf5_path # Path to the HDF5 file
            self.img_data = h5py.File(hdf5_path, 'r')['data/images']
            self.targets = pd.read_hdf(hdf5_path, 'targets')
        else:
            raise RuntimeError(f'Invalid value for mode: {mode}. Should be one of ' + 
                               '"normal", "hdf5"')
        
        # Select a subset from `targets` if specified
        if indices:
            self.select_subset(indices)




    def __len__(self):
        return self.targets.shape[0]

    def __getitem__(self, idx):
        item = self.targets.iloc[idx]
        label = item['score']

        feats = torch.Tensor(item[['est_res', 'class_dist', 'pixel_size']].to_numpy(dtype=np.float32)).to(torch.float32)

        if self.mode != 'hdf5':
            img_path = os.path.join(self.processed_dir, 'data/', f'{item["img_name"]}.npy')
            img = np.load(img_path)
        else:
            img = self.img_data[idx]

        if self.transform:
            img = self.transform(img)
        if self.target_transform:
            label = self.target_transform(label)

        
        return (img, label, feats) if self.use_features else (img, label) 
    
    def select_subset(self, indices):
        '''
        Selects a subset of the data contained in this Dataset in-placae. Same operation as
        providing `indices` in the constructor.
        '''

        print(f'Selecting subset of size {len(indices)} out of {len(self)}')

        if not hasattr(indices, '__getitem__'):
            print(f'Invalid type for indices: {type(indices)}')
        self.targets = self.targets.iloc[list(indices)]

        # Need to modify the HDF5 dataset to accomodate as well
        if self.mode == 'hdf5':
            self.img_data = self.img_data[indices]

        


    
    @staticmethod
    def preprocess_mrc(data_path, out_data_dir, annotations_file):
        '''
        Places each 2D class average in its own PNG file, and creates the labels/metadata
        in a CSV file with each row in the form of:
             (`particle_name`_`index`, `score`, `estimated resolution`, `class distribution`) 
        with `score` calculated as done in RELION 4.0. Images are resized to by 80x80 pixels
        '''

        ray.init(ignore_reinit_error=True, num_cpus=24, object_store_memory=(10**9) * 16, 
                 include_dashboard=False)

        def calculate_class_scores(particle_dir, est_res=None, pixel_size=None):
            '''
            Calculates class scores (between 0 and 1) for each 2D class average
            '''

            # Taken from RELION 4.0 class_ranker.cpp
            calculate_score = lambda r: (
                (0.75+r[1]*0.25)*job_score if r[0] == 1 else
                (0.25+r[1]*0.25)*job_score if r[0] == 2 else
                (0+r[1]*0.25)*job_score if (r[0] == 3 or r[0] == 4) else
                (0.5+r[1]*0.25)*job_score if r[0] == 5 else 0
            )

            model_path = os.path.join(particle_dir, 'run_model.star')
            targets_path = os.path.join(particle_dir, 'backup_selection.star')
            job_score_path = os.path.join(particle_dir, 'job_score.txt')

            # estimated resolution may have been fetched beforehand
            if est_res is None: 
                est_res = starfile.read(model_path, read_n_blocks=2, always_dict=True)['model_classes']['rlnEstimatedResolution']
            if pixel_size is None:
                pixel_size = starfile.read(model_path, read_n_blocks=1, always_dict=True)['model_general']['rlnPixelSize'].item()
            targets = starfile.read(targets_path)['rlnSelected']
            job_score = float(open(job_score_path).read().strip())

            # Calculate scores for each class, exactly how RELION 4.0 does
            weights = ((est_res.min() / est_res) ** 2).rename('weight')
            df = pd.concat([targets, weights, est_res], axis=1)
            
            return df.apply(calculate_score, axis=1)
        
        # 1 GiB of memory for every call of this function 
        @ray.remote(memory=1500 * 1024 * 1024)
        def process_particle_images(particle_name, idx):
            mrc_full_path = os.path.join(data_path, particle_name, 'run_classes.mrcs')
            model_full_path = os.path.join(data_path, particle_name, 'run_model.star')
            particle_metadata = []

            if os.path.isdir(os.path.dirname(mrc_full_path)):
                with mrcfile.open(mrc_full_path) as mrc:
                    # Fetch and calculate metadata to include in the targets file
                    model_star = starfile.read(model_full_path, read_n_blocks=2, always_dict=True)
                    model_general = model_star['model_general']
                    model_classes = model_star['model_classes']
                    

                    class_dist = model_classes['rlnClassDistribution']
                    if ('rlnEstimatedResolution' not in model_classes.columns) or \
                        ('rlnPixelSize' not in model_general.columns):
                        # If estimated resolution is not present, then skip this particle
                        return []    
                    
                    est_res = model_classes['rlnEstimatedResolution']
                    pixel_size = model_general['rlnPixelSize'].item()
                    # Calculate scores in [0, 1], using manual labels and estimated resolution
                    scores = calculate_class_scores(os.path.join(data_path, particle_name), est_res=est_res)
                    # Resize the image
                    imgs = mrc.data

                    for i, img in enumerate(imgs):
                        new_img = normalize(cv2.resize(np.nan_to_num(img), IMG_DSIZE, interpolation=cv2.INTER_AREA))
                        np.save(os.path.join(out_data_dir, f'{particle_name}_{i}.npy'), new_img)
                        particle_metadata.append((f'{particle_name}_{i}', scores[i], est_res[i], class_dist[i], pixel_size))

            print(f'Finished index {idx}: {particle_name} ({len(particle_metadata)} images)')
            return particle_metadata

        
        def normalize(arr):
            mini, maxi = arr.min(), arr.max()
            if mini == maxi:
                return np.zeros_like(arr)
            return (arr - mini) / (maxi - mini)
        
        if not os.path.exists(out_data_dir):
            os.makedirs(out_data_dir)
       
        particle_names = os.listdir(data_path)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files to {out_data_dir}...\n')

        raw_metadata = []
        for i, particle_name in tqdm(enumerate(particle_names)):
            raw_metadata.append(process_particle_images.remote(particle_name, i))
        
        metadata = list(itertools.chain.from_iterable(ray.get(raw_metadata)))

        targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).set_index('img_name').replace([np.inf, -np.inf], REPLACE_INF)
        targets.to_csv(os.path.join(os.path.dirname(out_data_dir), annotations_file))

        print(f'Wrote targets to : {os.path.join(os.path.dirname(out_data_dir), annotations_file)}')
        

    @staticmethod
    def preprocess_mrc_hdf5(data_path, hdf5_path):
        '''
        Does the exact same as `preprocess_mrc` but writes everything to an HDF5 file.

        :param hdf5_path: full path to the HDF5 file to write all results to
        '''

        def calculate_class_scores(particle_dir, est_res=None, pixel_size=None):
            '''
            Calculates class scores (between 0 and 1) for each 2D class average
            '''

            # Taken from RELION 4.0 class_ranker.cpp
            calculate_score = lambda r: (
                (0.75+r[1]*0.25)*job_score if r[0] == 1 else
                (0.25+r[1]*0.25)*job_score if r[0] == 2 else
                (0+r[1]*0.25)*job_score if (r[0] == 3 or r[0] == 4) else
                (0.5+r[1]*0.25)*job_score if r[0] == 5 else 0
            )

            model_path = os.path.join(particle_dir, 'run_model.star')
            targets_path = os.path.join(particle_dir, 'backup_selection.star')
            job_score_path = os.path.join(particle_dir, 'job_score.txt')

            # estimated resolution may have been fetched beforehand
            if est_res is None: 
                est_res = starfile.read(model_path, read_n_blocks=2, always_dict=True)['model_classes']['rlnEstimatedResolution']
            if pixel_size is None:
                pixel_size = starfile.read(model_path, read_n_blocks=1, always_dict=True)['model_general']['rlnPixelSize'].item()
            targets = starfile.read(targets_path)['rlnSelected']
            job_score = float(open(job_score_path).read().strip())

            # Calculate scores for each class, exactly how RELION 4.0 does
            weights = ((est_res.min() / est_res) ** 2).rename('weight')
            df = pd.concat([targets, weights, est_res], axis=1)
            
            return df.apply(calculate_score, axis=1)
        
        def process_particle_images(particle_name, hdf5_dataset, idx):
            '''
            Writes all images in chunks (one chunk per image) to the HDF5 file (the file
            must be open already)

            :param hdf5_dataset: a HDF5 Dataset object to write the images to.
            '''
            mrc_full_path = os.path.join(data_path, particle_name, 'run_classes.mrcs')
            model_full_path = os.path.join(data_path, particle_name, 'run_model.star')
            particle_metadata = []

            if os.path.isdir(os.path.dirname(mrc_full_path)):
                with mrcfile.open(mrc_full_path) as mrc:
                    # Fetch and calculate metadata to include in the targets file
                    model_star = starfile.read(model_full_path, read_n_blocks=2, always_dict=True)
                    model_general = model_star['model_general']
                    model_classes = model_star['model_classes']
                    
                    class_dist = model_classes['rlnClassDistribution']
                    if ('rlnEstimatedResolution' not in model_classes.columns) or \
                        ('rlnPixelSize' not in model_general.columns):
                        # If neccessary metadata is not present, then skip this particle
                        return []    
                    
                    est_res = model_classes['rlnEstimatedResolution']
                    pixel_size = model_general['rlnPixelSize'].item()
                    # Calculate scores in [0, 1], using manual labels other metadata
                    scores = calculate_class_scores(os.path.join(data_path, particle_name), est_res=est_res)
                    imgs = mrc.data

                    # Resize the dataset to fit the new images
                    cur_size, _, _ = hdf5_dataset.shape
                    hdf5_dataset.resize((cur_size+len(imgs),) + IMG_DSIZE)

                    for i, img in enumerate(imgs):
                        # Resize the image, then write it out
                        img = np.nan_to_num(img)
                        hdf5_dataset[cur_size+i] = normalize(cv2.resize(img, IMG_DSIZE, interpolation=cv2.INTER_AREA))
                        particle_metadata.append((f'{particle_name}_{i}', scores[i], est_res[i], class_dist[i], pixel_size))

            return particle_metadata

        
        def normalize(arr):
            mini, maxi = arr.min(), arr.max()
            if mini == maxi:
                return np.zeros_like(arr)
            return (arr - mini) / (maxi - mini)
        
        if os.path.isfile(hdf5_path):
            os.remove(hdf5_path)
            print('Removed existing HDF5 file')
        
        if not os.path.exists(os.path.dirname(hdf5_path)):
            os.makedirs(os.path.dirname(hdf5_path))

        
       
        particle_names = os.listdir(data_path)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files of size {IMG_DSIZE} to HDF5 at {hdf5_path}...\n')

        file = h5py.File(hdf5_path, 'a')
        img_group = file.create_group('data')
        img_dataset = img_group.create_dataset('images', 
                                               shape=(0,) + IMG_DSIZE, 
                                               maxshape=(None,) + IMG_DSIZE,
                                               chunks=(1,) + IMG_DSIZE,
                                               dtype='f4')


        raw_metadata = []        
        for i, particle_name in tqdm(list(enumerate(particle_names))):
            raw_metadata.append(process_particle_images(particle_name, img_dataset, i))
        file.close()

        metadata = list(itertools.chain.from_iterable(raw_metadata))

        targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).replace([np.inf, -np.inf], REPLACE_INF)
        targets.to_hdf(hdf5_path, 'targets')

        print(f'\nWrote targets to : {hdf5_path}')


if __name__ == '__main__':


    mpl.use('TkAgg')

    m = MRCImageDataset(
        mode='hdf5',
        hdf5_path='/nfs/home/khom/data120.hdf5',
        use_features=True,
    )

    img, label, feat = m[0]

    print(f'Size: {img.shape}')
    print(f'Label: {label}')
    print(f'Features: {feat}')

    plt.imshow(img, cmap='gray')
    plt.show()

    sys.exit()



    
    
    data_path = '/nfs/home/khom/data/'
    # data_path = '/nfs/home/khom/processed_data'
    # data_path = '/nfs/home/khom/data.hdf5'

    hdf5_path = '/nfs/home/khom/data120.hdf5' 
    processed_dir = '/nfs/home/khom/processed_data_120'
    start = time.time()

    # m0 = MRCImageDataset(mode='hdf5', data_path=data_path, hdf5_path=hdf5_path,
    #                     preprocess=True, use_features=True)
    # m1 = MRCImageDataset(mode='normal', data_path=data_path,processed_dir=processed_dir,
    #                     preprocess=True, use_features=True)
    m0 = MRCImageDataset(hdf5_path=hdf5_path, mode='hdf5', use_features=True)
    m1 = MRCImageDataset(processed_dir=processed_dir, mode='normal', 
                         annotations_file='targets.csv', use_features=True)
    print(f'Took {time.time() - start} seconds')

    x, label, feat = m0[0]
    print(feat.shape)
    print(x.shape)

    x, label, feat = m1[0]
    print(feat.shape)
    print(x.shape)
    