import cv2
import os
import mrcfile
import starfile
import itertools
import h5py
import torch
import sqlite3
import pandas as pd
import numpy as np

from tqdm import tqdm
from torch.utils.data import Dataset

from .mass_est_lib import calc_mass_stats_for_stack
from .util import Timer, normalize, resize_img, resize_to_shape, hdf5_dataset_params, combine_hdf5

REPLACE_INF = 999. # Replace NaN values in estimated resolution

'''
Contains classes to manage pre-processing the data into a usable format. 

JPGPreprocessor takes data from JPGs, as outputted by `extract_mrc.py`. It writes all data to a
single HDF5 file. 2D averages are saved as 'images' under the 'data' group. Metadata and labels
are saved in a pd.DataFrame as 'targets'.

MRCPreprocessor takes in data as stored by RELION 4.0 in the EMPIAR-10812 dataset. It writes data
to a single HDF5, with the same structure and metadata as JPGPreprocessor. 

MRCImageDataset can take in one of these HDF5 files and returns images with their associated 
metadata, in accordance to torch.utils.data.Dataset formatting. This can then be passed into 
a torch.utils.data.DataLoader and used to train a deep learning model.
'''

class JPGPreprocessor:
    '''
    Builds a preprocessor to prepare MRC image data stored in JPGs for training. The data
    MUST have been formatted using extract_mrc.py! That is, `jpg_dir` needs to be the "images"
    folder, and `metadata_dir` needs to be the "metadata" folder, as created by extract_mrc.py.
    
    The image data may come from either RELION or CryoSPARC, but each image must have the 
    appropriate metadata:

    - Estimated resolution (in Angstroms) 
    - Class distribution (between 0 and 1)
    - Pixel size (in Angstroms)
    - Absolute difference in estimated mass from the mean mass
    - Absolute difference in estimated mass from the median mass
    - Absolute difference in estimated mass from the mode mass
    '''

    def __init__(self, jpg_dir=None, metadata_dir=None, label_paths=None, hdf5_path=None):
        '''
        :param jpg_dir (str):
            Path to the folder other folders, each containing JPGs of 2D averages, representing one job.
        :param metadata_dir: 
            Path to the folder containing NPY files, each one containing a matrix of metadata for one job.
        :param label_paths: 
            List of paths to the sqlite3 DB files containing labels for each image. It is recommended
            to have multiple people label each image, resulting in more DB files, to reduce bias.
        :param hdf5_path: 
            Path to the resulting HDF5 file, if using mode. This is the path 
                    to the HDF5 file to write processed data to
        '''

        if not os.path.isdir(jpg_dir):
            raise ValueError(f'value of `jpg_dir`: "{jpg_dir}" is not a valid directory')
        if not os.path.isdir(metadata_dir):
            raise ValueError(f'value of `metadata_dir`: "{metadata_dir}" is not a valid directory')
        if len(label_paths) == 0:
            raise ValueError(f'`label_paths` is empty')
        if not all([os.path.exists(label_path) for label_path in label_paths]):
            raise ValueError(f'value of `label_paths`: one of the provided paths is invalid')
        if not isinstance(hdf5_path, str):
            raise ValueError('value of param `hdf5_path` must be string when mode is "hdf5". ' + 
                             f'Got: {hdf5_path} which is type {type(hdf5_path)}')

        self.jpg_dir = jpg_dir
        self.metadata_dir = metadata_dir
        self.label_cur = sqlite3.connect(label_paths[0]).cursor()
        self.hdf5_path = hdf5_path

        # DataFrame of labels and metadata, indexed by unique image name
        self.label_df = self.collect_labels(jpg_dir, label_paths)

        print(f'Writing to {hdf5_path}')
        print('Preparing to preprocess MRC images from JPGs...')

    def collect_labels(self, jpg_dir, label_paths):
        '''
        Averages labels for each image across all people who labeled them. The averaged labels then serve
        as the target scores for the machine learning algorithm. Returns a DataFrame with the average
        scores for each image; each row representing an image.

        :param label_paths (list of str): 
            List of paths to sqlite3 DB files, one for each labeler.

        :return (pd.DataFrame): 
            DataFrame indexed by unique image name, with columns for unique job name,
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
            # Add a column to all_label_df
            label_res = cursor.execute('SELECT imageName, category_id FROM images LEFT JOIN labels ON labels.image_id = images.id')
            raw_label_df = pd.DataFrame(label_res.fetchall(), columns=['img_name', 'category_id'])
            raw_label_df['img_name'] = raw_label_df['img_name'].apply(get_img_name)
            all_label_df[get_email(path)] = raw_label_df.drop_duplicates(subset=['img_name'], keep='first') \
                                            .set_index('img_name')['category_id'].clip(lower=1., upper=5.)
            
        
        # Average the labels across all labelers, ignoring nulls 
        label_df['label'] = all_label_df.mean(axis=1)
        return label_df

    def collect_images(self, job_img_dir):
        '''
        Collects the JPG images in the given directory into a single 3D numpy array, of shape
        (number of images, image height, image width)

        :param job_img_dir (str): 
            Path to the directory containing the job's 2D average images as JPGs.

        :return (np.array): 
            3D numpy array of the images stacked into one object.
        '''
        img_names = os.listdir(job_img_dir)
        imgs = [None] * len(img_names)
        sorted_names = [None] * len(img_names)
        for img_name in img_names:
            img_ind = int(img_name.strip('.jpg').split('_')[-1])
            img = cv2.imread(os.path.join(job_img_dir, img_name), cv2.IMREAD_GRAYSCALE)
            imgs[img_ind] = img
            sorted_names[img_ind] = img_name.split('.')[0]
        
        return np.array(imgs), sorted_names


    def execute(self, resize=None, min_len=None, fixed_len=None):
        '''
        Process the images and save them to the HDF5 file.

        Set `resize` to the desired number of Angstroms per pixel, or leave as None to leave
        all images as their original size. Additionally, set either `min_len` or `fixed_len` to 
        enforce all images to either a minimum size or a fixed size, with 0-padding.

        In terms of padding images (after choosing to resize or not), we can choose to:
        (1) Don't pad at all, and leave the images as their true size (min_len and fixed_len are None)
        (2) Pad only images that are too small with zeros (min_len defines the minimum height and width)
        (3) Pad all images to the same size (fixed_len defines the fixed height and width) 

        :param resize (float or None, optional): 
            Size to reshape images to; default is None (no reshaping). Reshaping is done through
            up/down-scaling and re-sampling.
        :param min_len (int or None, optional):
            Minimum size to enforce. Images that are too small will be enlarged by padding with 0's.
        :param fixed_len (int or None, optional):
            Will force all images to be the same size. Images that are too small are padded with 0's.
            Images that are too large are down-scaled.

        :return None:
        '''
        if (min_len and fixed_len):
            raise ValueError('only one of `min_len` or `fixed_len` may be specified! (or neither)')
        
        timer = Timer()

        if resize:
            print(f'Resizing all images to {resize} angstroms per pixel')
        if min_len:
            print(f'Setting minimum image size to ({min_len}, {min_len}) with padding')
        if fixed_len:
            print(f'Fixing image size to ({fixed_len}, {fixed_len}) with padding.')
  
        if os.path.isfile(self.hdf5_path):
            os.remove(self.hdf5_path)
            print('Replaced existing HDF5 file')

        if not os.path.exists(os.path.dirname(self.hdf5_path)):
            os.makedirs(os.path.dirname(self.hdf5_path))
            print('Created new HDF5 file')

        self.preprocess_mrc(resize=resize, min_len=min_len, fixed_len=fixed_len)

        print(f'Took {timer.get_elapsed() :.2f}s\n')


    def preprocess_mrc(self, resize=None, min_len=None, fixed_len=None):
        '''
        Process all MRC files in all jobs, as well as all metadata and labels. Writes them all to the given
        HDF5 file.

        Images are saved as 'images' under the 'data' group. Metadata and labels are saved as a pd.DataFrame
        as 'targets'.

        :param resize (float or None, optional): 
            As required by the JPGPreprocessor.execute method.
        :param min_len (int or None, optional):
            As required by the JPGPreprocessor.execute method.
        :param fixed_len (int or None, optional):
            As required by the JPGPreprocessor.execute method.

        :return None:
        '''
        job_ids = os.listdir(self.jpg_dir)

        file = h5py.File(self.hdf5_path, 'a')
        dataset_params = hdf5_dataset_params(fixed_len)
        img_dataset = file.create_dataset('data/images', **dataset_params)

        raw_metadata = []
        for job_id in tqdm(job_ids):
            raw_metadata.append(self.process_particle_images(img_dataset,
                                                             job_id,
                                                             resize=resize,
                                                             min_len=min_len,
                                                             fixed_len=fixed_len))
        file.close()

        metadata = pd.concat(raw_metadata, axis=0).fillna(REPLACE_INF)
        metadata.to_hdf(self.hdf5_path, 'targets')

        print(f'Wrote targets to : {self.hdf5_path}')


    def process_particle_images(self, hdf5_dataset, job_id, resize=None, min_len=None, fixed_len=None):
        '''
        Process the 2D average images and metadata from a single job. Writes the images to the HDF5 file,
        expanding the dataset as needed. Returns the metadata as a pd.DataFrame.

        Writes all images in chunks (one chunk per image) to the HDF5 file. The file
        must be open already.

        :param hdf5_dataset (h5py.Dataset): 
            A HDF5 Dataset object to write the images to. Must be in a file that is already open.
        :param job_id (str):
            The unique ID of the job. These will be the names of folders under the `jpg_dir` folder.
        :param resize (float or None, optional): 
            Size to reshape images to; default is None (no reshaping). Reshaping is done through
            up/down-scaling and re-sampling.
        :param min_len (int or None, optional):
            Minimum size to enforce. Images that are too small will be enlarged by padding with 0's.
        :param fixed_len (int or None, optional):
            Will force all images to be the same size. Images that are too small are padded with 0's.
            Images that are too large are down-scaled.
        
        :return None:
        '''

        job_img_dir = os.path.join(self.jpg_dir, job_id)
        job_mdata_path = os.path.join(self.metadata_dir, job_id+'.npy')

        if not os.path.exists(job_mdata_path):
            raise ValueError(f'cannot extract job: the job {job_id} does not have a metadata NPY file!')
        
        metadata = pd.DataFrame(np.load(job_mdata_path))
        scores = self.calculate_class_scores(metadata, job_id)
        imgs, img_names = self.collect_images(job_img_dir)

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
            
            # Append the image to the dataset
            hdf5_dataset[cur_size+i] = img.flatten() if not fixed_len else img

        return metadata


    def calculate_class_scores(self, metadata, job_id):
        '''
        Calculates class scores (between 0 and 1) for each 2D class average in the job.
        0 is the worst, 1 is the best.

        :param metadata (pd.DataFrame):
            Metadata of the job's class averages (as created by extract_mrc.py). 
        :param job_id (str):
            Unique ID (not the path) of the job to calculate scores for.

        :return (pd.Series):
            Scores for each 2D class average, indexed by the image's index in the job.
        '''

        # Score calculation is based on RELION's method
        calculate_score = lambda r: (
            (5-r['label'])*0.2 + r['weight']*0.2
        )

        est_res = metadata['est_res']
        weight = ((est_res.min() / est_res) ** 2).fillna(0.).rename('weight')
        job_label_df = (self.label_df[self.label_df['job_id'] == job_id]
                        .reset_index()
                        .groupby(['img_name', 'job_id', 'img_index'])
                        .mean()
                        .reset_index())
        
        job_label_df = pd.merge(job_label_df, weight, left_on='img_index', right_index=True) \
                        .reset_index().set_index('img_index')
        
        return job_label_df.apply(calculate_score, axis=1)
        # return (5-job_label_df['label']) / 4

class MRCPreprocessor:
    '''
    Builds a preprocessor to prepare MRC image data for training from the RELION 4.0 dataset, stored
    in EMPIAR-10812.
    
    Writes all data to an HDF5 file. Images are saved as 'images' under the 'data' group. Metadata
    and labels are saved in a pd.DataFrame as 'targets'.
    '''

    def __init__(self, data_dir=None, hdf5_path=None):
        '''
        :param data_dir (str): 
            Path to the folder containing raw dataset (default named 'data') as downloaded from 
            EMPIAR-10812.
        :param hdf5_path (str): 
            Path to the resulting HDF5 file, if using mode `hdf5`. This is the
            path to the HDF5 file to write processed data to.
        '''
        
        if not os.path.isdir(data_dir):
            raise ValueError(f'value of param `data_dir`: "{data_dir}" is not a valid directory')
        if not isinstance(hdf5_path, str):
            raise ValueError('value of param `hdf5_path` must be string when mode is "hdf5". ' + 
                             f'Got: {hdf5_path} which is type {type(hdf5_path)}')

        self.data_dir = data_dir
        self.hdf5_path = hdf5_path

        print('Preparing to preprocess MRC images from EMPIAR-10812...')
        

    def execute(self, resize=None, min_len=None, fixed_len=None):
        '''
        Process the images and save them to the HDF5 file.

        Set `resize` to the desired number of Angstroms per pixel, or leave as None to leave
        all images as their original size. Additionally, set either `min_len` or `fixed_len` to 
        enforce all images to either a minimum size or a fixed size, with zero-padding.

        In terms of padding images (after choosing to resize or not), we can choose to:
        (1) Don't pad at all, and leave the images as their true size (min_len and fixed_len are None)
        (2) Pad only images that are too small with zeros (min_len defines the minimum height and width)
        (3) Pad all images to the same size (fixed_len defines the fixed height and width; images
            that are too large will be downscaled) 

        :param resize (float or None, optional): 
            Size to re-scale images to; default is None (no re-scaling). Re-scaling done through
            up/down-scaling with interpolation techniques.
        :param min_len (int or None, optional):
            Minimum size to enforce. Images that are too small will be enlarged by padding with 0's.
        :param fixed_len (int or None, optional):
            Will force all images to be the same size. Images that are too small are padded with 0's.
            Images that are too large are down-scaled.

        :return None:
        '''
        if (min_len and fixed_len):
            raise ValueError('only one of `min_len` or `fixed_len` may be specified! (or neither)')
        
        timer = Timer()
        if resize:
            print(f'Resizing all images to {resize} angstroms per pixel with re-scaling.')
        if min_len:
            print(f'Setting minimum image size to ({min_len}, {min_len}) with padding.')
        if fixed_len:
            print(f'Fixing image size to ({fixed_len}, {fixed_len}) with padding.')
        
        if os.path.isfile(self.hdf5_path):
            os.remove(self.hdf5_path)
            print('Replacing existing HDF5 file')

        if not os.path.exists(os.path.dirname(self.hdf5_path)):
            os.makedirs(os.path.dirname(self.hdf5_path))
            print('Created new HDF5 file')

        self.preprocess_mrc(resize=resize, min_len=min_len, fixed_len=fixed_len)

        print(f'Took {timer.get_elapsed() :.2f}s\n')
    

    def preprocess_mrc(self, resize=None, min_len=None, fixed_len=None):
        '''
        Process all MRC files in all jobs, as well as all metadata and labels. Writes them all to
        the given HDF5 file.

        Images are saved as 'images' under the 'data' group. Metadata and labels are saved as a
        pd.DataFrame as 'targets'.

        :param resize (float or None, optional): 
            As required by the MRCPreprocessor.execute method.
        :param min_len (int or None, optional):
            As required by the MRCPreprocessor.execute method.
        :param fixed_len (int or None, optional):
            As required by the MRCPreprocessor.execute method.

        :return None:
        '''

        particle_names = os.listdir(self.data_dir)
        dtypes = [('img_name', 'U25'), ('score', 'f4'), ('est_res', 'f4'), ('class_dist', 'f4'), ('pixel_size', 'f4'),
                  ('dmean_mass', 'f4'), ('dmedian_mass', 'f4'), ('dmode_mass', 'f4')]

        print(f'Preprocessing {len(particle_names)} MRC files to HDF5 at {self.hdf5_path}...\n')

        file = h5py.File(self.hdf5_path, 'a')
        dataset_params = hdf5_dataset_params(fixed_len)
        img_dataset = file.create_dataset('data/images', **dataset_params)

        raw_metadata = []        
        for particle_name in tqdm(particle_names):
            raw_metadata.append(self.process_particle_images(particle_name, 
                                                             hdf5_dataset=img_dataset, 
                                                             resize=resize,
                                                             min_len=min_len,
                                                             fixed_len=fixed_len))
        file.close()

        metadata = list(itertools.chain.from_iterable(raw_metadata))
        targets = pd.DataFrame(np.array(metadata, dtype=dtypes)).replace([np.inf, -np.inf], REPLACE_INF)
        targets.to_hdf(self.hdf5_path, 'targets')

        print(f'\nWrote targets to : {self.hdf5_path}')


    def process_particle_images(self, particle_name, hdf5_dataset=None, resize=None, min_len=None, fixed_len=None):
        '''
        Process the 2D average images and metadata from a single job. Writes the images to the HDF5 file,
        expanding the dataset as needed. Returns the metadata as a pd.DataFrame.

        Writes all images in chunks (one chunk per image) to the HDF5 file. The file
        must be open already.

        :param particle_name (str):
            Name of the folder (not the path) containing the STAR files for the particle.
        :param hdf5_dataset (h5py.Dataset): 
            A HDF5 Dataset object to write the images to. Must be in a file that is already open.
        :param resize (float or None, optional): 
            Size to reshape images to; default is None (no reshaping). Reshaping is done through
            up/down-scaling and re-sampling.
        :param min_len (int or None, optional):
            Minimum size to enforce. Images that are too small will be enlarged by padding with 0's.
        :param fixed_len (int or None, optional):
            Will force all images to be the same size. Images that are too small are padded with 0's.
            Images that are too large are down-scaled.

        :return None:
        '''

        mrc_full_path = os.path.join(self.data_dir, particle_name, 'run_classes.mrcs')
        model_full_path = os.path.join(self.data_dir, particle_name, 'run_model.star')
        particle_metadata = []

        if os.path.isdir(os.path.dirname(mrc_full_path)):
            with mrcfile.open(mrc_full_path) as mrc:
                # Fetch and calculate metadata to include in the targets file
                model_star = starfile.read(model_full_path, read_n_blocks=2, always_dict=False)
                model_general = pd.DataFrame(model_star['model_general'], index=[0])
                model_classes = model_star['model_classes']

                class_dist = model_classes['rlnClassDistribution']
                if ('rlnEstimatedResolution' not in model_classes.columns) or \
                    ('rlnPixelSize' not in model_general.columns):
                    # If neccessary metadata is not present, then skip this particle
                    return []    
                
                est_res = model_classes['rlnEstimatedResolution']
                pixel_size = model_general['rlnPixelSize'].item()
                # Calculate scores in [0, 1], using manual labels other metadata
                scores = self.calculate_class_scores(os.path.join(self.data_dir, particle_name), est_res=est_res)
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
                    if resize is not None:
                        img = resize_img(img, pixel_size/resize)
                    
                    # If padding to a minimum size
                    if min_len and img.shape[0] < min_len:
                        diff = min_len - img.shape[0]
                        pad_before = diff // 2
                        pad_after = pad_before + (diff%2)
                        img = np.pad(img, (pad_before, pad_after))

                    # If padding to fixed size
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
                    
                    # Append the image to the dataset
                    hdf5_dataset[cur_size+i] = img.flatten() if not fixed_len else img
                    particle_metadata.append((f'{particle_name}_{i}', scores[i], est_res[i], class_dist[i], pixel_size) + 
                                             tuple(mass_est.iloc[i].to_list()))

        return particle_metadata
    
    def calculate_class_scores(self, particle_dir, est_res=None, pixel_size=None):
        '''
        Calculates class scores (between 0 and 1) for each 2D class average in the job.
        0 is the worst, 1 is the best.

        :param particle_dir (str):
            Path to the directory containing the STAR and MRC files for the job.
        :param est_res (pd.Series, optional)
            Series of estimated resolutions for each particle in the job. Will be fetched
            by this method if not provided.
        :param pixel_size (float, optional):
            Number of Angstroms per pixel. Will be fetched by this method if not provided.

        :return (pd.Series):
            Scores for each 2D class average, in the same order as 2D averages appear in the
            MRC file. 
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
            pixel_size = starfile.read(model_path, read_n_blocks=1, always_dict=True)['model_general']['rlnPixelSize']
        targets = starfile.read(targets_path)['rlnSelected']
        job_score = float(open(job_score_path).read().strip())

        # Calculate scores for each class, exactly how RELION 4.0 does
        weights = ((est_res.min() / est_res) ** 2).rename('weight')
        df = pd.concat([targets, weights, est_res], axis=1)
        
        return df.apply(calculate_score, axis=1)



class MRCImageDataset(Dataset):
    def __init__(self, hdf5_path=None, targets_name=None, 
                 indices=None, use_features=False, feature_scale=None,
                 verbose=True, load_mem=True, transform=None, target_transform=None):
        '''
        Creates a pytorch.utils.data.Dataset to return data, metadata, and labels for use
        in a DataLoader to train a deep learning model.
        
        :param hdf5_path (str): 
            Path to the HDF5 file to read from.
        :param targets_name (str): 
            The name of the DataFrame containing labels and metadata in the HDF5 file.
        :param indices (list, optional): 
            List of indices used to include only a subset of the data in this Dataset.
        :param use_features (bool): 
            Whether or not to include metadata as extra input features
        :param feature_scale (dict, optional): 
            Dict of {feature name : factor} that multiplies each feature by an optional factor 
            before passing it to the model. Used to reduce the magnitude of certain features 
            so they do not overpower the gradients during training.
        :param verbose (bool):
            Whether to print info and updates while loading data. Default is True.   
        :param load_mem (bool):
            Whether to load the data into memory beforehand, or leave it on disk. Setting
            to True has large overhead demand, but subsequent data access will be dast. Set to
            True when training or making large batch predictions. Default is True 
        :param transform (callable): 
            As required by pyTorch
        :param target_transform (callable): 
            As required by pyTorch             
        '''

        self.metadata_names = ['est_res', 'class_dist', 'pixel_size', 'dmean_mass', 'dmedian_mass', 'dmode_mass']
        
        self.hdf5_path = hdf5_path          
        self.use_features = use_features
        self.feature_scale = feature_scale
        self.verbose = verbose
        self.load_mem = load_mem
        self.transform = transform
        self.target_transform = target_transform

        self.print(f'Fetching MRC image data from {hdf5_path}')

        self.img_data = h5py.File(hdf5_path, 'r')['data/images']
        self.targets = pd.read_hdf(hdf5_path, targets_name)
        
        # If the data was stored as ragged 1D arrays, make sure to reshape them when indexing data
        if len(self.img_data.shape) == 1:
            self.vlen_data = True
        else:
            self.vlen_data = False
        
        # Select a subset from `targets` if specified
        if indices:
            self.select_subset(indices)

        self.print(f'Found {"variable" if self.vlen_data else "fixed"} length data')
        

    def __len__(self):
        return self.targets.shape[0]


    def __getitem__(self, idx):
        item = self.targets.iloc[idx].copy()
        if self.feature_scale is not None:
            for col, factor in self.feature_scale.items():
                item[col] *= factor

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
        Selects a subset of the data contained in this Dataset in-place. Same operation as
        providing `indices` in the constructor.

        :param indices (iterable):
            List or array of indices in the data to select. The order of the data is preserved
            from the HDF5 file.
        
        :return None:
        '''

        if not hasattr(indices, '__getitem__'):
            raise ValueError(f'invalid type for indices: {type(indices)}. '+
                             'Should be a list or array')

        self.print(f'Selecting subset of size {len(indices)} out of {len(self)}... ', end='')
        self.targets = self.targets.iloc[list(indices)]
        self.img_data = self.img_data[list(indices)]

        self.print('done')


    def make_collate_fn(self):
        '''
        Makes a custom collate function. Required to pass into the DataLoader if using variable
        length data, otherwise it returns None.

        :return (callable): The function to pass as `collate_fn` to the DataLoader.
        '''

        def fn(data):
            if self.use_features:
                imgs, labels, feats = zip(*data)
                return [torch.Tensor(img) for img in imgs], torch.Tensor(labels), torch.stack(feats)
            else:
                imgs, labels = zip(*data)
                return torch.stack(imgs), torch.stack(labels)
            
        return fn if self.vlen_data else None

    def print(self, *s, end='\n'):
        '''
        Helper print function that only prints if verbose is true
        '''

        if self.verbose:
            print(*s, end=end)


if __name__ == '__main__':

    # fixed_len = 210

    pass

    # relion_data_dir = '../data/'
    # relion_hdf5_path = '../ClassAvgLabeling/ProcessedData/relion_data_flen.hdf5'
    # MRCPreprocessor(
    #     data_dir=relion_data_dir,
    #     hdf5_path=relion_hdf5_path,
    # ).execute(fixed_len=fixed_len)

    # jpg_dir = '../ClassAvgLabeling/ExtractedData/StaggLabelling/images'
    # metadata_dir = '../ClassAvgLabeling/ExtractedData/StaggLabelling/metadata'
    # label_paths = ['../ClassAvgLabeling/ExtractedData/StaggLabelling/storage_sstagg@fsu.edu.db', 
    #                '../ClassAvgLabeling/ExtractedData/StaggLabelling/storage_rpeng@fsu.edu.db', 
    #                '../ClassAvgLabeling/ExtractedData/StaggLabelling/storage_nbogdanovic@fsu.edu.db']
    # hdf5_path = '../ClassAvgLabeling/ProcessedData/processed_stagg_flen.hdf5'

    # JPGPreprocessor(
    #     jpg_dir=jpg_dir,
    #     metadata_dir=metadata_dir,
    #     label_paths=label_paths,
    #     hdf5_path=hdf5_path
    # ).execute(fixed_len=fixed_len)

    # jpg_dir = '../ClassAvgLabeling/ExtractedData/LanderData/images'
    # metadata_dir = '../ClassAvgLabeling/ExtractedData/LanderData/metadata'
    # label_paths = [
    #                 '../ClassAvgLabeling/ExtractedData/LanderData/storage_mcianfro@umich.edu.db',
    #                 '../ClassAvgLabeling/ExtractedData/LanderData/storage_nbogdanovic@fsu.edu.db',
    #                '../ClassAvgLabeling/ExtractedData/LanderData/storage_rpeng@fsu.edu.db',
    #                '../ClassAvgLabeling/ExtractedData/LanderData/storage_sstagg@fsu.edu.db'
    #             ]
    # hdf5_path = '../ClassAvgLabeling/ProcessedData/processed_lander_flen.hdf5'

    # JPGPreprocessor(
    #     jpg_dir=jpg_dir,
    #     metadata_dir=metadata_dir,
    #     label_paths=label_paths,
    #     hdf5_path=hdf5_path
    # ).execute(fixed_len=fixed_len)

    # jpg_dir = '../ClassAvgLabeling/ExtractedData/CianfroccoData/images'
    # metadata_dir = '../ClassAvgLabeling/ExtractedData/CianfroccoData/metadata'
    # label_paths = ['../ClassAvgLabeling/ExtractedData/CianfroccoData/storage_mcianfro@umich.edu.db',
    #                '../ClassAvgLabeling/ExtractedData/CianfroccoData/storage_rpeng@fsu.edu.db',
    #                '../ClassAvgLabeling/ExtractedData/CianfroccoData/storage_sstagg@fsu.edu.db']

    # hdf5_path = '../ClassAvgLabeling/ProcessedData/processed_cianfrocco_flen.hdf5'

    # JPGPreprocessor(
    #     jpg_dir=jpg_dir,
    #     metadata_dir=metadata_dir,
    #     label_paths=label_paths,
    #     hdf5_path=hdf5_path
    # ).execute(fixed_len=fixed_len)

    # paths = [
    #     '../ClassAvgLabeling/ProcessedData/processed_lander_flen.hdf5',
    #     '../ClassAvgLabeling/ProcessedData/processed_stagg_flen.hdf5',
    #     '../ClassAvgLabeling/ProcessedData/processed_cianfrocco_flen.hdf5'
    # ]
    # combine_hdf5(paths, '../ClassAvgLabeling/ProcessedData/csparc_data_flen.hdf5', fixed_len=fixed_len)

    # paths = [
    #     '../ClassAvgLabeling/ProcessedData/csparc_data_flen.hdf5',
    #     '../ClassAvgLabeling/ProcessedData/relion_data_flen.hdf5'
    # ]
    # combine_hdf5(paths, '../ClassAvgLabeling/ProcessedData/combined_data_flen.hdf5', fixed_len=fixed_len)

