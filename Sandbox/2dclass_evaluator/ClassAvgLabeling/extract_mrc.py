# extract_mrc.py
# By Keenan Hom
# Written on Python 3.8.3
# Tested on Python 3.8.3
# 
# 
# Copyright 2023 Keenan Hom

import os
import re
import json
import argparse
import sys
import mrcfile

import numpy as np
import pandas as pd

from PIL import Image

from massest.mass_est_lib import calc_mass_stats_for_stack

''' 
Python program to extract 2D class average images from an MRC file into individual JPGs. Also 
exctracts the necessary metadata (estimated resolution, class distribution, and pixel size)
'''



class CryosparcExtractor:
    '''
    Extract images and metadata from a single job
    '''
    def __init__(self, data_dir=None, processed_dir=None):
        if data_dir is None or processed_dir is None:
            raise ValueError('both source (data_dir) and destination (processed_dir) must be non-null')
        if not os.path.isdir(data_dir):
            raise ValueError(f'ERROR: job directory `{data_dir}` is not a valid path')
        if not os.path.isdir(processed_dir):
            raise ValueError(f'ERROR: output directory `{processed_dir}` is not an existing directory! Please create it first.')

        self.data_dir = data_dir # Path to the CryoSPARC job
        self.processed_dir = processed_dir # Path to the directory to put 'images' and 'metadata' folders
        self.image_dir = os.path.join(processed_dir, 'images/') # Contains JPGs of class averages
        self.metadata_dir = os.path.join(processed_dir, 'metadata/') # Contains NPY files of metadata 

        if not os.path.exists(self.image_dir):
            os.mkdir(self.image_dir)
        if not os.path.exists(self.metadata_dir):
            os.mkdir(self.metadata_dir)
        
        # Attributes to be set in setup
        self.mrc_path = None # Path to the .mrc file to extract from 
        self.metadata_path = None # Path to the .cs metadata file
        self.particles_path = None # Path to the .cs particles metadata file
        self.processed_subdir = None # Path to uniquely named sub-folder to extract into
        self.all_metadata = None # DataFrame of all the metadata in the job

        self.setup()


    def setup(self):
        '''
        Collect and format data in preparation for writing.
        '''
        # Find the MRC file: JXX_YYY_class_averages.mrc with YYY being the highest in the folder
        pattern = re.compile(r'J\d+_(\d+)_class_averages.mrc')
        mrc_iter_dict = {int(re.search(pattern, name).group(1)): name
                     for name in os.listdir(self.data_dir)
                      if re.search(pattern, name)}
        
        if len(mrc_iter_dict) == 0:
            raise RuntimeError(f'could not find MRC file in job {self.data_dir}. Please check!')
            

        max_iter = max(mrc_iter_dict.keys())
        mrc_name = mrc_iter_dict[max_iter]

        self.mrc_path = os.path.join(self.data_dir, mrc_name)

        # Find the corresponding metadata files
        self.metadata_path = self.mrc_path.replace('.mrc', '.cs')
        self.particles_path = self.mrc_path.replace('_class_averages.mrc', '_particles.cs')

        # Create unique name of sub-folder 
        job_json_path = os.path.join(self.data_dir, 'job.json')
        job_json = json.load(open(job_json_path))

        self.unique_name = job_json['project_uid'] + '_' + job_json['uid'] + '_' + job_json['created_by_user_id']
        self.processed_subdir = os.path.join(self.image_dir, self.unique_name)

        if not os.path.isdir(self.processed_subdir):
            os.mkdir(self.processed_subdir)
        if not os.path.isfile(self.metadata_path):
            print(f'ERROR: Missing metadata file: {self.metadata_path} does not exist')
            sys.exit()
        if not os.path.isfile(self.particles_path):
            print(f'ERROR: Missing particles metadata file: {self.particles_path} does not exist')
            sys.exit()

        # Metadata will be ordered as:
        # 1. Estimated resolution in Angstroms
        # 2. Class distribution (fraction)
        # 3. Pixel size in Angstroms
        # 4. Mean mass
        # 5. Median mass
        # 6. Mode mass

        # Metadata stored in .cs files
        metadata_names = ['est_res', 'class_dist', 'pixel_size']
        metadata = [None, None, None]

        # Metadata from the mass estimator (remove estimated mass; it is useless as a parameter)
        mass_est_names = ['dmean_mass', 'dmedian_mass', 'dmode_mass']
        mass_est = pd.DataFrame.from_records(calc_mass_stats_for_stack(self.mrc_path))
        # print(mass_est['dmode'].head())
        # mass_est['dmode'] = mass_est['dmode'].apply(lambda x: x[0])
        mass_est['dmode'] = mass_est['dmode'].astype(float)  # Ensure it's float if needed

        mass_est = mass_est.drop(columns=['mass']).to_numpy()
        
        # Grab resolution and pixel size directly from the .cs averages file
        class_metadata = np.load(self.metadata_path)
        metadata[0] = class_metadata['blob/res_A']
        metadata[2] = class_metadata['blob/psize_A']

        # Calculate class distribution from the .cs particles file
        particle_metadata = np.load(self.particles_path, mmap_mode='r')
        particles_df = pd.DataFrame(particle_metadata[['uid', 'alignments2D/class']])
        class_dist = particles_df.groupby('alignments2D/class').count()
        metadata[1] = class_dist['uid'] / len(particles_df)
        metadata[1] = metadata[1].reindex(list(range(len(metadata[0])))).fillna(0.)

        # Assemble everything into a single structured array representing all class averages in the file
        metadata = np.rec.array(np.vstack(metadata), names=metadata_names).T
        self.all_metadata = np.rec.fromarrays(np.concatenate((metadata, mass_est), axis=1).T, 
                              names=metadata_names+mass_est_names)


    
    def extract(self):
        '''
        Write data to the output directory.
        '''
        def normalize(arr):
            mini, maxi = arr.min(), arr.max()
            if mini == maxi:
                return np.zeros_like(arr)
            return (arr - mini) / (maxi - mini)

        print(f'Extracting from: {self.data_dir}')
        print(f'\t{os.path.basename(self.mrc_path)}')

        with mrcfile.open(self.mrc_path) as mrc:
            imgs = mrc.data
            for i in range(len(imgs)):
                img = Image.fromarray(np.uint8(normalize(imgs[i]) * 255))
                img.save(os.path.join(self.processed_subdir, f'{self.unique_name}_{i}.jpg'))

        print(f'\t{os.path.basename(self.metadata_path)}')
        np.save(os.path.join(self.metadata_dir, self.unique_name+'.npy'), self.all_metadata)



class MultiCryosparcExtractor:
    '''
    Extract images and metadata from multiple jobs
    '''
    def __init__(self, data_dir_file=None, processed_dir=None):
        if data_dir_file is None or processed_dir is None:
            raise ValueError('both source file (data_dir_file) and destination folder (processed_dir) must be non-null')
        
        if not os.path.isfile(data_dir_file):
            raise ValueError('source text file (data_dir_list) must be a valid file')

        self.data_dir_file = data_dir_file
        self.processed_dir = processed_dir

        # Attributes to be set in setup
        self.job_dirs = None

        self.setup()

    def setup(self):
        # Get files list
        f = open(self.data_dir_file, 'r')
        self.job_dirs = [job_dir.strip() for job_dir in f.readlines()]
        f.close()

        # Check that all job directories are valid
        for job_dir in self.job_dirs:
            if not os.path.isdir(job_dir):
                raise ValueError(f'ERROR: job directory `{job_dir}` is not a valid directory. ' + \
                                 f'Please check the contents of `{self.data_dir_file}` and try again.')



    def extract_all(self):
        for job_dir in (self.job_dirs):
            extractor = CryosparcExtractor(data_dir=job_dir, processed_dir=self.processed_dir)
            extractor.extract()

        


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='See README.md for more detailed help')
    parser.add_argument('-j', '--job-dir', help='Path to the folder containing results of '+
                        '2D extraction (must be a cryoSPARC job!)')
    parser.add_argument('-l', '--job-dir-list', help='Path to a text file that contains a list of various '+
                        'job directories. Each line should contain one path to job folder (no commas).')
    parser.add_argument('-d', '--directory', help='The path to the directory to place the data and metadata into. '+
                        'The directory must exist.')
    args = parser.parse_args()


    # Users may only provide one job directory, or one file with a list of job directories
    if (args.job_dir is not None) == (args.job_dir_list is not None):
        raise ValueError('please provide either --job_dir or --job-dir-list, but not both.')
    
    # Users must provide a lab directory
    if args.directory is None:
        raise ValueError('Please provide the valid path to your lab directory with `-d` or `--directory`')
        
    if args.job_dir:
        print('Running single job extraction')
        extractor = CryosparcExtractor(data_dir=args.job_dir, processed_dir=args.directory)
        extractor.extract()
        print('done')
    else:
        print('Running multiple job extraction')
        multi_extractor = MultiCryosparcExtractor(data_dir_file=args.job_dir_list, processed_dir=args.directory)
        multi_extractor.extract_all()
        print('done')
