import cv2
import os
import sys
import mrcfile
import starfile
import ray
import itertools
import h5py
import torch
import sqlite3
import pandas as pd
import numpy as np
import matplotlib as mpl

from tqdm import tqdm
from torch.utils.data import Dataset

from massest.mass_est_lib import calc_mass_stats_for_stack
from util import Timer, normalize, resize_img, resize_to_shape, hdf5_dataset_params, combine_hdf5

# IMG_DSIZE = (120, 120) # Rescale all images to the same size
REPLACE_INF = 999. # Replace NaN values in estimated resolution
PIXEL_SIZE = 4.0 # Constant pixel size to scale all images to, if desired

'''
Creates and returns the dataset for training the CNN
'''

class JPGPreprocessor:
    '''
    Builds a preprocessor to prepare MRC image data stored in JPGs for training. The image data may
    come from either RELION or CryoSPARC, but each image must have the appropriate metadata:

    - Estimated resolution (in Angstroms) 
    - Class distribution (between 0 and 1)
    - Pixel size (in Angstroms)
    OPTIONALLY:
    - Absolute difference in estimated mass from the mean mass
    - Absolute difference in estimated mass from the median mass
    - Absolute difference in estimated mass from the mode mass

    If the last 3 parameters are not present, they will be calculated using mass_est_lib.
    '''

    def __init__(self, mode=None, jpg_dir=None, metadata_dir=None, label_paths=None, hdf5_path=None, 
                 processed_dir=None):
        '''
        :param mode (required): should be either 'normal' or 'hdf5', determining the method to store outputs
                    if 'normal', the file structure is:
                                all images listed in {data_dir}/data/
                                annotations stored in {data_dir}/targets.csv
                    if 'hdf5', all images and annotations are stored in `data_dir`.
                            Within `data.hdf5`, the file structure is:
                                all images listed in /data/images
                                annotations stored in /targets.csv

        :param jpg_dir (required): path to the folder other folders, each containing JPGs of 2D averages, 
                    representing one job.

        :param metadata_dir (required): path to the folder containing NPY files, each one containing
                    a matrix of metadata for one job.

        :param label_paths (required): List of paths to the sqlite3 DB files containing labels for each image.
                    It is recommended to have multiple people label each image, resulting in more DB files,
                    to reduce bias.

        :param hdf5_path (required if mode=='hdf5'): path to the resulting HDF5 file, if using mode 
                            `hdf5`. This is the path to the HDF5 file to write processed data to
        
        :param processed_dir (required if mode=='normal): path to the resulting directory of processed images and targets, if using
                        mode `normal`. This is the directory to write processed images into (in a sub-directory `data/`) 
                        and targets + metadata (in a CSV `targets.csv`)
        '''

        if not (mode == 'normal' or mode == 'hdf5'):
            raise ValueError('`mode` must be either "normal" or "hdf5')
        if not os.path.isdir(jpg_dir):
            raise ValueError(f'value of `jpg_dir`: "{jpg_dir}" is not a valid directory')
        if not os.path.isdir(metadata_dir):
            raise ValueError(f'value of `metadata_dir`: "{metadata_dir}" is not a valid directory')
        if len(label_paths) == 0:
            raise ValueError(f'`label_paths` is empty')
        if not all([os.path.exists(label_path) for label_path in label_paths]):
            raise ValueError(f'value of `label_paths`: one of the provided paths is invalid')
        
        if mode == 'normal' and not isinstance(processed_dir, str):
            raise ValueError('value of param `processed_dir` must be a string when mode is "normal". ' +
                             f'Got: {processed_dir}, which is type {type(processed_dir)}')
        elif mode == 'hdf5' and not isinstance(hdf5_path, str):
            raise ValueError('value of param `hdf5_path` must be string when mode is "hdf5". ' + 
                             f'Got: {processed_dir} which is type {type(processed_dir)}')

        self.mode = mode
        self.jpg_dir = jpg_dir
        self.metadata_dir = metadata_dir
        self.label_cur = sqlite3.connect(label_paths[0]).cursor()
        self.hdf5_path = hdf5_path
        self.processed_dir = processed_dir

        self.label_df = self.collect_labels(jpg_dir, label_paths)

        print('Preparing to preprocess MRC images from JPGs...')

        if mode == 'hdf5':
            print(f'Writing to HDF5 file {hdf5_path}')
        elif mode == 'normal':
            print(f'Writing to folder {processed_dir}')

    def collect_labels(self, jpg_dir, label_paths):
        '''
        Averages labels for each image across all people who labeled them. The averaged labels then serve
        as the target scores for the machine learning algorithm. Returns a DataFrame with the average
        scores for each image; each row representing an image.

        :param label_paths: list of paths to sqlite3 DB files, one for each labeler.

        :return: pandas DataFrame indexed by unique image name, with columns for unique job name,
                index of each image (within that image's job), and the averaged score.
        '''
        # Function to get the unique name of an image from its absolute path
        get_img_name = lambda path: os.path.basename(path).strip('.jpg')
        # Function to get the unique email of a labeller
        get_email = lambda path: os.path.basename(path).strip('.db')
        # Function to get the index of each image within its job
        get_img_index = lambda path: int(os.path.basename(path).strip('.jpg').split('_')[-1])

        
        # Contains many columns; one column of labels for each labeler
        imgs = pd.Series(list(itertools.chain.from_iterable([
            os.listdir(os.path.join(jpg_dir, job_name)) for job_name in os.listdir(jpg_dir)
        ]))).apply(get_img_name)

        label_df = pd.DataFrame(data={'job_id': imgs.str.extract(r'(.+)_\d+$', expand=False).tolist(), 
                                          'img_index': imgs.apply(get_img_index).tolist()},
                                    index=imgs.apply(get_img_name).rename('img_name'))
        # Will contain the final averaged scores from each labeler
        all_label_df = pd.DataFrame(index=label_df.index)


        for path in label_paths:
            cursor = sqlite3.connect(path).cursor()
            # if i == -1:
            #     # Upon first iteration, create label_df and all_label_df
            #     label_res = cursor.execute('SELECT * FROM images LEFT JOIN labels ON labels.image_id = images.id')
            #     raw_label_df = pd.DataFrame(label_res.fetchall(), columns=['id', 'dataSet_id', 'img_name',
            #                                                                'img_path', 'category_id', 'image_id'])
            #     raw_label_df['img_name'] = raw_label_df['img_name'].apply(get_img_name) # unique image name
            #     raw_label_df['job_id'] = raw_label_df['img_name'].str.extract(r'(.+)_\d+$') # unique job name
            #     raw_label_df['img_index'] = raw_label_df['img_name'].apply(get_img_index) # index of each image within its job
            #     raw_label_df = raw_label_df.set_index('img_name')

            #     label_df = raw_label_df[['job_id', 'img_index']]

            #     all_label_df = pd.DataFrame(index=raw_label_df.index)
            #     all_label_df[get_email(path)] = raw_label_df['category_id']
            
            # Add a column to all_label_df
            label_res = cursor.execute('SELECT imageName, category_id FROM images LEFT JOIN labels ON labels.image_id = images.id')
            raw_label_df = pd.DataFrame(label_res.fetchall(), columns=['img_name', 'category_id'])
            raw_label_df['img_name'] = raw_label_df['img_name'].apply(get_img_name)
            all_label_df[get_email(path)] = raw_label_df.drop_duplicates(subset=['img_name'], keep='first') \
                                            .set_index('img_name')['category_id'].clip(lower=1., upper=5.)
            
        
        # Average the labels across all labelers, ignoring nulls 
        label_df['label'] = all_label_df.mean(axis=1)
        
        # print(label_df.reset_index())
        # print(all_label_df.reset_index()[all_label_df.index == 'P175_J66_5da4da769e704919b5c60493_13'])
        return label_df


    def execute(self, resize=None, min_len=None, fixed_len=None):
        '''
        Process the images and save them to the desired format.

        Set resize to the desired number of Angstroms per pixel, or leave as None to leave
        all images as their original size.

        In terms of padding images (after choosing to resize or not), we can choose to:
        (1) Don't pad at all, and leave the images as their true size (min_len and fixed_len are None)
        (2) Pad only images that are too small with zeros (min_len defines the minimum height and width)
        (3) Pad all images to the same size (fixed_len defines the fixed height and width) 
        '''
        if (min_len and fixed_len):
            raise ValueError('only one of `min_len` or `fixed_len` may be specified! (or neither)')
        
        timer = Timer()

        if resize:
            print(f'Resizing all images to {resize} angstroms per pixel')
        if min_len:
            print(f'Setting minimum image size to ({min_len}, {min_len}) with padding')
        if fixed_len:
            print(f'Fixing image size to ({fixed_len}, {fixed_len}) with {"padding" if resize is None else "resizing"}')

        if self.mode == 'normal':
            print('TODO: Implement this dataset to optionally store data as NPY files')
        else:
            if os.path.isfile(self.hdf5_path):
                os.remove(self.hdf5_path)
                print('Removed existing HDF5 file')

            if not os.path.exists(os.path.dirname(self.hdf5_path)):
                os.makedirs(os.path.dirname(self.hdf5_path))
                print('Created new HDF5 file')

            JPGPreprocessor.preprocess_mrc_hdf5(self.jpg_dir, self.metadata_dir, self.label_df, 
                                                self.hdf5_path, resize=resize, min_len=min_len,
                                                fixed_len=fixed_len)
            
        print(f'Took {timer.get_elapsed() :.2f}s\n')


    @staticmethod
    def preprocess_mrc_hdf5(jpg_dir, metadata_dir, label_df, hdf5_path, resize=None, min_len=None, fixed_len=None):
        job_ids = os.listdir(jpg_dir)

        file = h5py.File(hdf5_path, 'a')
        dataset_params = hdf5_dataset_params(fixed_len)
        img_dataset = file.create_dataset('data/images', **dataset_params)

        raw_metadata = []
        for job_id in tqdm(job_ids):
            raw_metadata.append(JPGPreprocessor.process_particle_images(jpg_dir, 
                                                                        metadata_dir,
                                                                        job_id,
                                                                        label_df,
                                                                        hdf5_dataset=img_dataset,
                                                                        resize=resize,
                                                                        min_len=min_len,
                                                                        fixed_len=fixed_len))
        file.close()

        metadata = pd.concat(raw_metadata, axis=0).fillna(REPLACE_INF)
                # targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).replace([np.inf, -np.inf], REPLACE_INF)

        metadata.to_hdf(hdf5_path, 'targets')

        print(f'Wrote targets to : {hdf5_path}')

    @staticmethod
    def process_particle_images(jpg_dir, metadata_dir, job_id, label_df, hdf5_dataset=None, out_data_dir=None, resize=None, min_len=None, fixed_len=None):
        '''
        Process the 2D average images and metadata from a single job.

        If writing images to individual NPY files: writes all images one by one.
        If using an HDF5 file: writes all images in chunks (one chunk per image) to the HDF5 file (the file
        must be open already).

        :param hdf5_dataset: a HDF5 Dataset object to write the images to.
        '''

        job_img_dir = os.path.join(jpg_dir, job_id)
        job_mdata_path = os.path.join(metadata_dir, job_id+'.npy')

        if not os.path.exists(job_mdata_path):
            raise ValueError(f'cannot extract job: the job {job_id} does not have a metadata NPY file!')
        
        metadata = pd.DataFrame(np.load(job_mdata_path))
        scores = JPGPreprocessor.calculate_class_scores(label_df, metadata, job_id)
        imgs, img_names = JPGPreprocessor.collect_images(job_img_dir)

        metadata.insert(0, 'score', scores)
        metadata.insert(0, 'img_name', img_names)       

        pixel_size = metadata['pixel_size'][0].item()

        if hdf5_dataset is not None:
            # Resize the dataset to fit the new images
            if not fixed_len:
                # If not fixing the size
                cur_size, = hdf5_dataset.shape
                hdf5_dataset.resize((cur_size+len(imgs),))
            else:
                # If fixing the size
                cur_size, _, _ = hdf5_dataset.shape
                hdf5_dataset.resize((cur_size+len(imgs), fixed_len, fixed_len))

        for i, img in enumerate(imgs):

            img = normalize(img).astype(np.float32)
            # If resizing to fixed pixel size, then scale images to fixed pixel size
            if resize is not None:
                img = resize_img(img, pixel_size/resize)

            

            # If enforcing a minimum size (pad images that are too small with 0's)
            if min_len and img.shape[0] < min_len:
                diff = min_len - img.shape[0]
                pad_before = diff // 2
                pad_after = pad_before + (diff%2)
                img = np.pad(img, (pad_before, pad_after))

            # If padding to fixed size (pad images that are too small with 0's)
            elif fixed_len:
                if img.shape[0] > fixed_len: 
                    if resize is not None:
                        print(f'Image is larger than the fixed size ({img.shape[0]} > {fixed_len}). '+
                                    f'Rescaling image to fixed size (pixel size is not preserved)')
                    img = resize_to_shape(img, (fixed_len, fixed_len))

                diff = fixed_len - img.shape[0]
                pad_before = diff // 2
                pad_after = pad_before + (diff%2)
                img = np.pad(img, (pad_before, pad_after))   
            
            # If using HDF5, append to the dataset. If using normal, make a new NPY file
            if hdf5_dataset is not None:
                hdf5_dataset[cur_size+i] = img.flatten() if not fixed_len else img
            else:
                np.save(os.path.join(out_data_dir, f'{job_id}_{i}.npy'), img)
        
        if hdf5_dataset is None:
            print(f'Finished: {job_id} ({len(metadata)} images)')
        return metadata
        

    @staticmethod
    def collect_images(job_img_dir):
        '''
        Collects the JPG images in the given directory into a single 3D numpy array, of shape
        (number of images, image height, image width)

        :param job_img_dir (required): path to the directory containing the job's 2D average images.

        :return: 3D numpy array of the images stacked into one object.  
        '''
        img_names = os.listdir(job_img_dir)
        imgs = [None] * len(img_names)
        sorted_names = [None] * len(img_names)
        for img_name in img_names:
            img_ind = int(img_name.strip('.jpg').split('_')[-1])
            img = cv2.imread(os.path.join(job_img_dir, img_name), cv2.IMREAD_GRAYSCALE)
            imgs[img_ind] = img
            sorted_names[img_ind] = img_name.split('.')[0]
        
        # print(f'Max size: {max([i.shape[0] for i in imgs])}')
        return np.array(imgs), sorted_names


    @staticmethod
    def calculate_class_scores(label_df, metadata, job_id):
        '''
        Calculates class scores (between 0 and 1) for each 2D class average in the job.
        0 is the worst, 1 is the best.

        :param label_df: pd.DataFrame created by the `collect_labels` function.
        :param job_id: unique ID of the job (string) to calculate scores for.
        :param duplicate: what to do in the case of duplicate scores for the same image.
                            Choices are 'mean', 'max', 'min', 'drop', 'keep_first'.
                            Default is 'mean'.
        '''
        
        # print('Reduced labels:')
        # print(job_label_df.reset_index().groupby(['img_name', 'job_id', 'img_index']).mean().reset_index())

        # calculate_score = lambda r: (
        #     (0.75+r[1]*0.25) if r[0] == 1 else
        #     (0.5+r[1]*0.25) if r[0] == 2 else
        #     (0.25+r[1]*0.25) if r[0] == 3 else
        #     (0.0+r[1]*0.25) if r[0] == 4 else 
        #     0
        # )

        calculate_score = lambda r: (
            ((5-r['label'])*0.2 + r['weight']*0.2)
        )

        est_res = metadata['est_res']
        weight = ((est_res.min() / est_res) ** 2).fillna(0.).rename('weight')
        job_label_df = (label_df[label_df['job_id'] == job_id]
                        .reset_index()
                        .groupby(['img_name', 'job_id', 'img_index'])
                        .mean()
                        .reset_index())
        
        job_label_df = pd.merge(job_label_df, weight, left_on='img_index', right_index=True) \
                        .reset_index().set_index('img_index')

        # print(job_label_df)
        # print(weight)
        # print(weight)
        # print(pd.merge(job_label_df, weight, left_on='img_index', right_index=True))
        
        # print(job_label_df.apply(calculate_score, axis=1))
        
        return job_label_df.apply(calculate_score, axis=1)
        # return (5-job_label_df['label']) / 4

class MRCPreprocessor:
    '''
    Builds a preprocessor to prepare MRC image data for training from the RELION 4.0 dataset.
    Can either write all data to a single HDF5 file, or individual PNG files and a labels file.

    TODO Calculate estimated mass as metadata

    '''
    def __init__(self, mode=None, data_dir=None, hdf5_path=None, 
                 processed_dir=None):
        '''
        :param mode (required): should be either 'normal' or 'hdf5', determining the method to store outputs
                    if 'normal', the file structure is:
                                all images listed in {data_dir}/data/
                                annotations stored in {data_dir}/targets.csv
                    if 'hdf5', all images and annotations are stored in `data_dir`.
                            Within `data.hdf5`, the file structure is:
                                all images listed in /data/images
                                annotations stored in /targets.csv

        :param data_dir (required): path to the folder containing raw dataset (default named 'data') 
                            as downloaded from EMPIAR-10812. Required.
        
        :param hdf5_path (required if mode=='hdf5'): path to the resulting HDF5 file, if using mode 
                            `hdf5`. This is the path to the HDF5 file to write processed data to
        
        :param processed_dir (required if mode=='normal): path to the resulting directory of processed images and targets, if using
                        mode `normal`. This is the directory to write processed images into (in a sub-directory `data/`) 
                        and targets + metadata (in a CSV `targets.csv`)
        '''
        
        if not (mode == 'normal' or mode == 'hdf5'):
            raise ValueError('`mode` must be either "normal" or "hdf5')
        if not os.path.isdir(data_dir):
            raise ValueError(f'value of param `data_dir`: "{data_dir}" is not a valid directory')
        if mode == 'normal' and not isinstance(processed_dir, str):
            raise ValueError('value of param `processed_dir` must be a string when mode is "normal". ' +
                             f'Got: {processed_dir}, which is type {type(processed_dir)}')
        elif mode == 'hdf5' and not isinstance(hdf5_path, str):
            raise ValueError('value of param `hdf5_path` must be string when mode is "hdf5". ' + 
                             f'Got: {processed_dir} which is type {type(processed_dir)}')

        print('Preparing to preprocess MRC images from EMPIAR-10812...')

        self.mode = mode
        self.data_dir = data_dir
        self.hdf5_path = hdf5_path
        self.processed_dir = processed_dir
        

    def execute(self, resize=False, min_len=None, fixed_len=None):
        '''
        Process the images and save them to the desired format.

        In terms of padding images (after resizing or not), we can choose to:
        (1) Don't pad at all, and leave the images as their true size (min_len and fixed_len are None)
        (2) Pad only images that are too small with zeros (min_len defines the minimum height and width)
        (3) Pad all images to the same size (fixed_len defines the fixed height and width) 
        '''
        if (min_len and fixed_len):
            raise ValueError('only one of `min_len` or `fixed_len` may be specified! (or neither)')
        
        timer = Timer()
        if resize:
            print(f'Resizing all images to {PIXEL_SIZE} angstroms per pixel')
        if min_len:
            print(f'Setting minimum image size to ({min_len}, {min_len}) with padding')
        if fixed_len:
            print(f'Fixing image size to ({fixed_len}, {fixed_len}) with {"padding" if resize else "resizing"}')
        if self.mode == 'normal':
            if not os.path.exists(self.processed_dir):
                os.makedirs(self.processed_dir)
                print('Created new directory')
            
            processed_data_dir = os.path.join(self.processed_dir, 'data')
            annotations_file = 'targets.csv'

            MRCPreprocessor.preprocess_mrc(self.data_dir, processed_data_dir, annotations_file, 
                                           resize=resize, min_len=min_len, fixed_len=fixed_len)

        else:
            if os.path.isfile(self.hdf5_path):
                os.remove(self.hdf5_path)
                print('Removed existing HDF5 file')

            if not os.path.exists(os.path.dirname(self.hdf5_path)):
                os.makedirs(os.path.dirname(self.hdf5_path))

            MRCPreprocessor.preprocess_mrc_hdf5(self.data_dir, self.hdf5_path, resize=resize, min_len=min_len, fixed_len=fixed_len)

        print(f'Took {timer.get_elapsed() :.2f}s\n')
    
    
    @staticmethod
    @ray.remote(memory=1000 * 1024 * 1024)
    def process_particle_images_remote(particle_name, data_dir, out_data_dir, resize=False, min_len=None, fixed_len=None):
        return MRCPreprocessor.process_particle_images(particle_name, data_dir, out_data_dir=out_data_dir, 
                                                       resize=resize, min_len=min_len, fixed_len=fixed_len)


    @staticmethod
    def process_particle_images(particle_name, data_dir, hdf5_dataset=None, out_data_dir=None, resize=False, min_len=None, fixed_len=None):
        '''
        If writing images to individual NPY files: writes all images one by one.
        If using an HDF5 file: writes all images in chunks (one chunk per image) to the HDF5 file (the file
        must be open already).

        :param hdf5_dataset: a HDF5 Dataset object to write the images to.
        '''
        mrc_full_path = os.path.join(data_dir, particle_name, 'run_classes.mrcs')
        model_full_path = os.path.join(data_dir, particle_name, 'run_model.star')
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
                scores = MRCPreprocessor.calculate_class_scores(os.path.join(data_dir, particle_name), est_res=est_res)
                imgs = mrc.data

                mass_est = pd.DataFrame.from_records(calc_mass_stats_for_stack(mrc_full_path))
                mass_est['dmode'] = mass_est['dmode'].apply(lambda x: x[0])
                mass_est = mass_est.drop(columns=['mass']).clip(upper=1e9)

                if hdf5_dataset is not None:
                    # Resize the dataset to fit the new images
                    if not fixed_len:
                        cur_size, = hdf5_dataset.shape
                        hdf5_dataset.resize((cur_size+len(imgs),))
                    else:
                        cur_size, _, _ = hdf5_dataset.shape
                        hdf5_dataset.resize((cur_size+len(imgs), fixed_len, fixed_len)) 

                for i, img in enumerate(imgs):

                    img = normalize(np.nan_to_num(img))
                    # If resize, then scale images to fixed pixel size
                    if resize:
                        img = resize_img(img, pixel_size/PIXEL_SIZE)
                    
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
                            img = resize_to_shape(img, (fixed_len, fixed_len))
                        
                        diff = fixed_len - img.shape[0]
                        pad_before = diff // 2
                        pad_after = pad_before + (diff%2)
                        img = np.pad(img, (pad_before, pad_after))                    
                    
                    # If using HDF5, append to the dataset. If using normal, make a new NPY file
                    if hdf5_dataset is not None:

                        hdf5_dataset[cur_size+i] = img.flatten() if not fixed_len else img
                    else:
                        np.save(os.path.join(out_data_dir, f'{particle_name}_{i}.npy'), img)
                    

                    particle_metadata.append((f'{particle_name}_{i}', scores[i], est_res[i], class_dist[i], pixel_size) + 
                                             tuple(mass_est.iloc[i].to_list()))

        if hdf5_dataset is None:
            print(f'Finished: {particle_name} ({len(particle_metadata)} images)')
        return particle_metadata
    
    @staticmethod
    def calculate_class_scores(particle_dir, est_res=None, pixel_size=None):
        '''
        Calculates class scores (between 0 and 1) for each 2D class average
        '''

        # Score calculation function
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
    def preprocess_mrc_hdf5(data_dir, hdf5_path, resize=False, min_len=None, fixed_len=None):
        '''
        Does the exact same as `preprocess_mrc` but writes everything to an HDF5 file.

        :param hdf5_path: full path to the HDF5 file to write all results to.
        '''

        particle_names = os.listdir(data_dir)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4'),
                  ('dmean_mass', 'f4'), ('dmedian_mass', 'f4'), ('dmode_mass', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files to HDF5 at {hdf5_path}...\n')

        file = h5py.File(hdf5_path, 'a')
        dataset_params = hdf5_dataset_params(fixed_len)
        img_dataset = file.create_dataset('data/images', **dataset_params)

        raw_metadata = []        
        for particle_name in tqdm(particle_names):
            raw_metadata.append(MRCPreprocessor.process_particle_images(particle_name, 
                                                                        data_dir,
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
    def preprocess_mrc(data_dir, out_data_dir, annotations_file, resize=False, min_len=None, fixed_len=None):
        '''
        Places each 2D class average in its own NPY file, and creates the labels/metadata
        in a CSV file with each row in the form of:
             (`particle_name`_`index`, `score`, `estimated resolution`, `class distribution`, `dmean`, `dmedian`, `dmode`) 
        with `score` calculated as done in RELION 4.0. Images are resized according to min_len,
        fixed_len, and resize.
        '''

        ray.init(ignore_reinit_error=True, num_cpus=8, object_store_memory=(10**9) * 16, 
                 include_dashboard=False)
        
        if not os.path.exists(out_data_dir):
            os.makedirs(out_data_dir)
       
        particle_names = os.listdir(data_dir)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files to invididual NPY files in {out_data_dir}...\n')

        raw_metadata = []
        for particle_name in tqdm(particle_names):
            raw_metadata.append(MRCPreprocessor.process_particle_images_remote.remote(
                particle_name, data_dir, out_data_dir, resize=resize, min_len=min_len, fixed_len=fixed_len
                ))
        
        metadata = list(itertools.chain.from_iterable(ray.get(raw_metadata)))

        targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).replace([np.inf, -np.inf], REPLACE_INF)
        targets.to_csv(os.path.join(os.path.dirname(out_data_dir), annotations_file))

        print(f'Wrote targets to : {os.path.join(os.path.dirname(out_data_dir), annotations_file)}')



class MRCImageDataset(Dataset):
    def __init__(self, mode=None, annotations_file=None, 
                 data_path=None, hdf5_path=None, processed_dir=None,
                 indices=None, use_features=False, feature_scale=None, vlen_data=False,
                 transform=None, target_transform=None):
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
        :param feature_scale: dict of {feature name : factor} that multiplies each feature by an
                        optional factor before passing it to the model. Used to reduce the magnitude
                        of certain features so they do not overpower the gradients during training.
        :param vlen_data: whether or not the data source contains variable sized data
        :param transform: as required by pyTorch
        :param target_transform: as required by pyTorch                 
        '''
        print(f'Fetching MRC image data (mode: {mode}) from {processed_dir if mode == "normal" else hdf5_path}')

        self.metadata_names = ['est_res', 'class_dist', 'pixel_size', 'dmean_mass', 'dmedian_mass', 'dmode_mass']
                               
        self.mode = mode
        self.transform = transform
        self.target_transform = target_transform

        self.data_path = data_path
        self.hdf5_path = hdf5_path
        self.processed_dir = processed_dir
        
        self.use_features = use_features
        self.feature_scale = feature_scale
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
                self.vlen_data = False
        else:
            raise RuntimeError(f'Invalid value for mode: {mode}. Should be either ' + 
                               '"normal", "hdf5"')
        
        # Select a subset from `targets` if specified
        if indices:
            self.select_subset(indices)

        print(f'Found {"variable" if self.vlen_data else "fixed"} length data')
        

    def __len__(self):
        return self.targets.shape[0]
    

    def __getitem__(self, idx):
        item = self.targets.iloc[idx].copy()
        for col, factor in self.feature_scale.items():
            item[col] *= factor

        if self.mode != 'hdf5':
            img_path = os.path.join(self.processed_dir, 'data/', f'{item["img_name"]}.npy')
            img = np.load(img_path)
        else:

            img = self.img_data[idx] if not self.vlen_data else \
                    [self.img_data[i].reshape(1, round(np.sqrt(self.img_data[i].shape[0])),
                                              round(np.sqrt(self.img_data[i].shape[0])))
                                                for i in np.atleast_1d(idx)]
        img = torch.Tensor(img).to(torch.float32)
        label = item['score']
        feats = torch.Tensor(item[self.metadata_names].to_numpy(dtype=np.float32)).to(torch.float32)

        


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

    # from matplotlib import pyplot as plt
    # mpl.use('TkAgg')

    fixed_len = 210



    # relion_data_dir = '/nfs/home/khom/data/'
    # relion_hdf5_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/relion_data_flen.hdf5'
    # MRCPreprocessor(
    #     mode='hdf5',
    #     data_dir=relion_data_dir,
    #     hdf5_path=relion_hdf5_path,
    # ).execute(fixed_len=fixed_len)

    # jpg_dir = '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/StaggLabelling/images'
    # metadata_dir = '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/StaggLabelling/metadata'
    # label_paths = ['/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/StaggLabelling/storage_sstagg@fsu.edu.db', 
    #                '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/StaggLabelling/storage_rpeng@fsu.edu.db', 
    #                '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/StaggLabelling/storage_nbogdanovic@fsu.edu.db']
    # hdf5_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/processed_stagg_flen.hdf5'

    # JPGPreprocessor(
    #     mode='hdf5',
    #     jpg_dir=jpg_dir,
    #     metadata_dir=metadata_dir,
    #     label_paths=label_paths,
    #     hdf5_path=hdf5_path
    # ).execute(fixed_len=fixed_len)

    # jpg_dir = '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/LanderData/images'
    # metadata_dir = '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/LanderData/metadata'
    # label_paths = [
    #                 '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/LanderData/storage_mcianfro@umich.edu.db',
    #                 '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/LanderData/storage_nbogdanovic@fsu.edu.db',
    #                '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/LanderData/storage_rpeng@fsu.edu.db',
    #                '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/LanderData/storage_sstagg@fsu.edu.db'
    #             ]
    # hdf5_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/processed_lander_flen.hdf5'

    # JPGPreprocessor(
    #     mode='hdf5',
    #     jpg_dir=jpg_dir,
    #     metadata_dir=metadata_dir,
    #     label_paths=label_paths,
    #     hdf5_path=hdf5_path
    # ).execute(fixed_len=fixed_len)

    # jpg_dir = '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/CianfroccoData/images'
    # metadata_dir = '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/CianfroccoData/metadata'
    # label_paths = ['/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/CianfroccoData/storage_mcianfro@umich.edu.db',
    #                '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/CianfroccoData/storage_rpeng@fsu.edu.db',
    #                '/nfs/home/khom/test_projects/ClassAvgLabeling/ExtractedData/CianfroccoData/storage_sstagg@fsu.edu.db']

    # hdf5_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/processed_cianfrocco_flen.hdf5'

    # JPGPreprocessor(
    #     mode='hdf5',
    #     jpg_dir=jpg_dir,
    #     metadata_dir=metadata_dir,
    #     label_paths=label_paths,
    #     hdf5_path=hdf5_path
    # ).execute(fixed_len=fixed_len)

    # paths = [
    #     '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/processed_lander_flen.hdf5',
    #     '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/processed_stagg_flen.hdf5',
    #     '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/processed_cianfrocco_flen.hdf5'
    # ]
    # combine_hdf5(paths, '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/alldata_flen.hdf5', fixed_len=fixed_len)

    paths = [
        '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/alldata_flen.hdf5',
        '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/relion_data_flen.hdf5'
    ]
    combine_hdf5(paths, '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/combined_data_flen.hdf5', fixed_len=fixed_len)

    # d = MRCImageDataset(
    #     mode='hdf5',
    #     hdf5_path=hdf5_path,
    #     use_features=True
    # )

    # print(len(d))
    # img, label, feat = d[3]

    # print(img)
    # print(label)
    # print(feat)

    # plt.imshow(np.array(img).squeeze(), cmap='gray')
    # plt.show()

    # data_dir = '/nfs/home/khom/data/'
    # hdf5_path = '/nfs/home/khom/data-vlen-same.hdf5'
    # processed_dir = '/nfs/home/khom/processed_data_200'

    # MRCPreprocessor(
    #     mode='hdf5',
    #     data_dir=data_dir,
    #     hdf5_path=hdf5_path,
    # ).execute(resize=False)



