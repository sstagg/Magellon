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
import warnings
import pandas as pd
import numpy as np
import matplotlib as mpl

from tqdm import tqdm
from torch.utils.data import Dataset

from util import Timer

IMG_DSIZE = (120, 120) # Rescale all images to the same size
REPLACE_INF = 999. # Replace infinity values (inf and -inf) with this constant
PIXEL_SIZE = 4.0 # Constant pixel size to scale all images to, if desired

'''
Creates and returns the dataset for training the CNN
'''

class MRCPreprocessor:

    def __init__(self, mode=None, data_path=None, hdf5_path=None, 
                 processed_dir=None):
        '''
        Builds a preprocessor to prepare MRC image data for training from the RELION 4.0 dataset.
        Can either write all data to a single HDF5 file, or individual PNG files and a labels file.

        :param mode (required): should be either 'normal' or 'hdf5', determining the method to store outputs
                    if 'normal', the file structure is:
                                all images listed in {data_path}/data/
                                annotations stored in {data_path}/targets.csv
                    if 'hdf5', all images and annotations are stored in `data_path`.
                            Within `data.hdf5`, the file structure is:
                                all images listed in /data/images
                                annotations stored in /targets.csv

        :param data_path (required): path to the folder containing raw dataset (default named 'data') 
                            as downloaded from EMPIAR-10812. Required.
        
        :param hdf5_path (required if mode=='hdf5'): path to the resulting HDF5 file, if using mode 
                            `hdf5`. This is the path to the HDF5 file to write processed data to
        
        :param processed_dir (required if mode=='normal): path to the resulting directory of processed images and targets, if using
                        mode `normal`. This is the directory to write processed images into (in a sub-directory `data/`) 
                        and targets + metadata (in a CSV `targets.csv`)
        '''

        assert mode == 'normal' or mode == 'hdf5', 'Error: `mode` must be either "normal" or "hdf5'
        assert os.path.isdir(data_path), f'Error (param data_path): value of "{data_path}" is not a valid directory'

        print('Preparing to preprocess MRC images...')

        self.mode = mode
        self.data_path = data_path
        self.hdf5_path = hdf5_path
        self.processed_dir = processed_dir
        

    def execute(self, resize=False, min_len=None, fixed_len=None):
        '''
        In terms of padding images (after resizing or not), we can choose to:
        (1) Don't pad at all, and leave the images as their true size (min_len and fixed_len are None)
        (2) Pad only images that are too small with zero (min_len defines the minimum height and width)
        (3) Pad all images to the same size (fixed_len defines the fixed height and width) 
        '''
        assert not (min_len and fixed_len)
        
        timer = Timer()
        if resize:
            print(f'Resizing all images to {PIXEL_SIZE} angstroms per pixel')
        if min_len:
            print(f'Setting minimum image size to ({min_len}, {min_len}) with padding')
        if fixed_len:
            print(f'Fixing image size to ({fixed_len}, {fixed_len}) with {"padding" if resize else "resizing"}')
        if self.mode == 'normal':
            if not os.path.exists(self.processed_dir):
                print('Created new directory')
                os.makedirs(self.processed_dir)
            
            processed_data_dir = os.path.join(self.processed_dir, 'data')
            annotations_file = 'targets.csv'

            MRCPreprocessor.preprocess_mrc(data_path, processed_data_dir, annotations_file, resize=resize, min_len=min_len, fixed_len=fixed_len)

        else:
            if os.path.isfile(self.hdf5_path):
                os.remove(self.hdf5_path)
                print('Removed existing HDF5 file')

            if not os.path.exists(os.path.dirname(self.hdf5_path)):
                os.makedirs(os.path.dirname(self.hdf5_path))

            MRCPreprocessor.preprocess_mrc_hdf5(self.data_path, self.hdf5_path, resize=resize, min_len=min_len, fixed_len=fixed_len)

        print(f'Took {timer.get_elapsed() :.2f}s\n')
    
    
    @staticmethod
    @ray.remote(memory=1000 * 1024 * 1024)
    def process_particle_images_remote(particle_name, out_data_dir, resize=False, min_len=None, fixed_len=None):
        return MRCPreprocessor.process_particle_images(particle_name, out_data_dir=out_data_dir, 
                                                       resize=resize, min_len=min_len, fixed_len=fixed_len)


    @staticmethod
    def process_particle_images(particle_name, hdf5_dataset=None, out_data_dir=None, resize=False, min_len=None, fixed_len=None):
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
                scores = MRCPreprocessor.calculate_class_scores(os.path.join(data_path, particle_name), est_res=est_res)
                imgs = mrc.data

                if hdf5_dataset is not None:
                    # Resize the dataset to fit the new images
                    if not fixed_len:
                        cur_size, = hdf5_dataset.shape
                        hdf5_dataset.resize((cur_size+len(imgs),))
                    else:
                        cur_size, _, _ = hdf5_dataset.shape
                        hdf5_dataset.resize((cur_size+len(imgs), fixed_len, fixed_len))

                for i, img in enumerate(imgs):
                    # If resize, then scale images to fixed pixel size
                    if resize:
                        img = MRCPreprocessor.resize_img(np.nan_to_num(img), pixel_size/PIXEL_SIZE)

                    img = MRCPreprocessor.normalize(img)
                    
                    # If enforcing a minimum size
                    if min_len and img.shape[0] < min_len:
                        diff = min_len - img.shape[0]
                        pad_before = diff // 2
                        pad_after = pad_before + (diff%2)
                        img = np.pad(img, (pad_before, pad_after))
                    # If padding to fixed size
                    elif fixed_len:
                        if img.shape[0] > fixed_len: 
                            if resize:
                                print(f'Image is larger than the fixed size ({img.shape[0]} > {fixed_len}). '+
                                          f'Rescaling image to fixed size (pixel size is not preserved)')
                            img = MRCPreprocessor.resize_img(img, (fixed_len, fixed_len))
                        
                        diff = fixed_len - img.shape[0]
                        pad_before = diff // 2
                        pad_after = pad_before + (diff%2)
                        img = np.pad(img, (pad_before, pad_after))                    
                    
                    # If using HDF5, append to the dataset. If using normal, make a new NPY file
                    if hdf5_dataset is not None:
                        hdf5_dataset[cur_size+i] = img.flatten() if not fixed_len else img
                    else:
                        np.save(os.path.join(out_data_dir, f'{particle_name}_{i}.npy'), img)
                    

                    particle_metadata.append((f'{particle_name}_{i}', scores[i], est_res[i], class_dist[i], pixel_size))

        if hdf5_dataset is None:
            print(f'Finished: {particle_name} ({len(particle_metadata)} images)')
        return particle_metadata
    
    @staticmethod
    def calculate_class_scores(particle_dir, est_res=None, pixel_size=None):
        '''
        Calculates class scores (between 0 and 1) for each 2D class average
        '''

        # Taken from RELION 4.0 class_ranker.cpp. Calculates score from 0 to 1 for a given image
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

    @staticmethod
    def resize_to_shape(img, new_shape):
        '''
        Resize image to the desired shape while keeping the same zoom. The aspect ratio of the 
        image and of the new shape should match
        '''

        interpolation = cv2.INTER_AREA \
                            if img.shape[0] > new_shape[0] \
                            else cv2.INTER_CUBIC
        return cv2.resize(img, new_shape, interpolation=interpolation)

    @staticmethod
    def resize_img(img, factor):
        '''
        Rescales an image with respect to its center.

        :param img: 2D ndarray of the greyscale image
        :param factor: float representing amount to resize (e.g. factor=2.0 means double the number of
                        pixels on each side, factor=0.5 means halve the number of pixels on each side)

        :return: 2D ndarray of the resized image. The resized shape will be different according to 
        the resize factor 
        '''

        # Resize the image, and then pad it to a standard size
        new_shape = tuple(np.round(np.array(img.shape) * factor).astype(np.int32))
        new_img = MRCPreprocessor.resize_to_shape(img, new_shape)
        return new_img
    
    @staticmethod
    def normalize(arr):
        mini, maxi = arr.min(), arr.max()
        if mini == maxi:
            return np.zeros_like(arr)
        return (arr - mini) / (maxi - mini)

    @staticmethod
    def hdf5_dataset_params(fixed_len=None):
        '''
        If vlen=True, then data is variable length and must be stored as 1D arrays. Otherwise
        store data normally, in 2D fixed size
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



    @staticmethod
    def preprocess_mrc_hdf5(data_path, hdf5_path, resize=False, min_len=None, fixed_len=None):
        '''
        Does the exact same as `preprocess_mrc` but writes everything to an HDF5 file.

        :param hdf5_path: full path to the HDF5 file to write all results to
        '''

        particle_names = os.listdir(data_path)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files to HDF5 at {hdf5_path}...\n')

        file = h5py.File(hdf5_path, 'a')
        dataset_params = MRCPreprocessor.hdf5_dataset_params(fixed_len)
        img_dataset = file.create_dataset('data/images', **dataset_params)

        raw_metadata = []        
        for particle_name in tqdm(particle_names):
            raw_metadata.append(MRCPreprocessor.process_particle_images(particle_name, 
                                                                        hdf5_dataset=img_dataset, 
                                                                        resize=resize,
                                                                        min_len=min_len,
                                                                        fixed_len=fixed_len))
        file.close()

        metadata = list(itertools.chain.from_iterable(raw_metadata))

        targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).replace([np.inf, -np.inf], REPLACE_INF)
        targets.to_hdf(hdf5_path, 'targets')

        print(f'\nWrote targets to : {hdf5_path}')

    @staticmethod
    def preprocess_mrc(data_path, out_data_dir, annotations_file, resize=False, min_len=None, fixed_len=None):
        '''
        Places each 2D class average in its own PNG file, and creates the labels/metadata
        in a CSV file with each row in the form of:
             (`particle_name`_`index`, `score`, `estimated resolution`, `class distribution`) 
        with `score` calculated as done in RELION 4.0. Images are resized to by 80x80 pixels
        '''

        ray.init(ignore_reinit_error=True, num_cpus=8, object_store_memory=(10**9) * 16, 
                 include_dashboard=False)
        
        if not os.path.exists(out_data_dir):
            os.makedirs(out_data_dir)
       
        particle_names = os.listdir(data_path)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files to invididual NPY files in {out_data_dir}...\n')

        raw_metadata = []
        for particle_name in tqdm(particle_names):
            raw_metadata.append(MRCPreprocessor.process_particle_images_remote.remote(
                particle_name, out_data_dir, resize=resize, min_len=min_len, fixed_len=fixed_len
                ))
        
        metadata = list(itertools.chain.from_iterable(ray.get(raw_metadata)))

        targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).set_index('img_name').replace([np.inf, -np.inf], REPLACE_INF)
        targets.to_csv(os.path.join(os.path.dirname(out_data_dir), annotations_file))

        print(f'Wrote targets to : {os.path.join(os.path.dirname(out_data_dir), annotations_file)}')



class MRCImageDataset(Dataset):
    def __init__(self, mode=None, annotations_file=None, 
                 data_path=None, hdf5_path=None, processed_dir=None,
                 indices=None, use_features=False, vlen_data=False,
                 transform=None, target_transform=None,):
        '''
        :param mode: it should be either 'normal' or 'hdf5' signifying either
                            listing images in one large directory like normal, or storing everything
                            in an HDF5 file, respectively.
                    if 'normal', the file structure is:
                                all images listed in {data_path}/data/
                                annotations stored in {data_path}/targets.csv
                    if 'hdf5', all images and annotations are stored in `data_path`.
                            Within `data.hdf5`, the file structure is:
                                all images listed in /data/images
                                annotations stored in /targets.csv

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
        :param vlen_data: whether or not the data source contains variable sized data [CURRENTLY UNUSED]
        :param transform: as required by pyTorch
        :param target_transform: as required by pyTorch                 
        '''
        print(f'Fetching MRC image data (mode: {mode}) from {processed_dir if mode == "normal" else hdf5_path}')

        self.mode = mode
        self.transform = transform
        self.target_transform = target_transform

        self.data_path = data_path
        self.hdf5_path = hdf5_path
        self.processed_dir = processed_dir
        
        self.use_features = use_features

        self.vlen_data = vlen_data

        if mode == 'normal':
            if processed_dir is None:
                raise RuntimeError(f'out_data_dir should not be None when in `normal` mode')
            
            self.targets = pd.read_csv(os.path.join(processed_dir, annotations_file))

        elif mode == 'hdf5':
            self.img_data = h5py.File(hdf5_path, 'r')['data/images']
            self.targets = pd.read_hdf(hdf5_path, 'targets')
            
            # If the data was stored as ragged 1D arrays, make sure to reshape them when indexing data
            if len(self.img_data.shape) == 1:
                self.vlen_data = True
        else:
            raise RuntimeError(f'Invalid value for mode: {mode}. Should be one of ' + 
                               '"normal", "hdf5"')
        
        # Select a subset from `targets` if specified
        if indices:
            self.select_subset(indices)


        # print(f'Reshaping data: {self.vlen_data}')



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

            img = self.img_data[idx] if not self.vlen_data else \
                    [self.img_data[i].reshape(1, round(np.sqrt(self.img_data[i].shape[0])),
                                              round(np.sqrt(self.img_data[i].shape[0])))
                                                for i in np.atleast_1d(idx)]

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

        print(f'Selecting subset of size {len(indices)} out of {len(self)}... ', end='')

        if not hasattr(indices, '__getitem__'):
            print(f'Invalid type for indices: {type(indices)}')
        self.targets = self.targets.iloc[list(indices)]

        # Need to modify the HDF5 dataset to accomodate as well
        if self.mode == 'hdf5':
            self.img_data = self.img_data[indices]

        print('done')


    def make_collate_fn(self):
        '''
        Makes a custom collate function. Required if using variable length data, otherwise
        it returns None.
        '''

        def fn(data):
            if self.use_features:
                imgs, labels, feats = zip(*data)
                return [torch.Tensor(img) for img in imgs], torch.Tensor(labels), torch.stack(feats)
            else:
                imgs, labels = zip(*data)
                return torch.stack(imgs), torch.stack(labels)
            
        return fn if self.vlen_data else None

        


    
    
        

    


if __name__ == '__main__':


    mpl.use('TkAgg')

    data_path = '/nfs/home/khom/data/'
    hdf5_path = '/nfs/home/khom/data-vlen-same.hdf5'
    processed_dir = '/nfs/home/khom/processed_data_200'

    # MRCPreprocessor(
    #     mode='hdf5',
    #     data_path=data_path,
    #     hdf5_path=hdf5_path,
    # ).execute(resize=False)


    MRCPreprocessor(
        mode='normal',
        data_path=data_path,
        processed_dir=processed_dir,
    ).execute(fixed_len=230)

