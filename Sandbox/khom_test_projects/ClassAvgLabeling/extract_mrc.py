import os
import re
import json
import argparse
import sys
import mrcfile

import numpy as np
import pandas as pd
# import matplotlib as mpl

# from tqdm import tqdm
from PIL import Image
# from matplotlib import pyplot as plt

''' 
Python program to extract 2D class average images from an MRC file into individual JPGs. Also 
exctracts the necessary metadata (estimated resolution, class distribution, and pixel size)
'''



class CryosparcExtractor:
    '''
    
    '''
    def __init__(self, data_dir=None, processed_dir=None):
        assert data_dir is not None and processed_dir is not None, \
            'ERROR: Both source (data_dir) and destination (processed_dir) must be non-null'
        assert os.path.isdir(data_dir), f'ERROR: job directory `{data_dir}` is not a valid path'
        assert os.path.isdir(processed_dir), f'ERROR: lab directory `{processed_dir} is not a valid path`'

        self.data_dir = data_dir
        self.processed_dir = processed_dir
        self.image_dir = os.path.join(processed_dir, 'images/')
        self.metadata_dir = os.path.join(processed_dir, 'metadata/')

        if not os.path.exists(self.image_dir):
            os.mkdir(self.image_dir)
        if not os.path.exists(self.metadata_dir):
            os.mkdir(self.metadata_dir)
        
        # Attributes to be set in setup
        self.mrc_path = None # Path to the .mrc file to extract from 
        self.metadata_path = None # Path to the .cs metadata file
        self.particles_path = None # Path to the .cs particles metadata file
        self.processed_subdir = None # Path to uniquely named sub-folder to extract into

        self.setup()


    def setup(self):
        # Find the MRC file: JXX_YYY_class_averages.mrc with YYY being the highest in the folder
        pattern = re.compile(r'J\d+_(\d+)_class_averages.mrc')
        mrc_iter_dict = {int(re.search(pattern, name).group(1)): name
                     for name in os.listdir(self.data_dir)
                      if re.search(pattern, name)}
        
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


    
    def extract(self):

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
        metadata_names = ['est_res', 'class_dist', 'pixel_size']
        metadata = [None, None, None]

        class_metadata = np.load(self.metadata_path)
        metadata[0] = class_metadata['blob/res_A']
        metadata[2] = class_metadata['blob/psize_A']

        particle_metadata = np.load(self.particles_path, mmap_mode='r')
        particles_df = pd.DataFrame(particle_metadata[['uid', 'alignments2D/class']])
        class_dist = particles_df.groupby('alignments2D/class').count()
        metadata[1] = class_dist['uid'] / len(particles_df)

        metadata = np.rec.fromarrays(metadata, names=metadata_names)
        np.save(os.path.join(self.metadata_dir, self.unique_name+'.npy'), metadata)

        



        

class MultiCryosparcExtractor:
    '''
    
    '''
    def __init__(self, data_dir_file=None, processed_dir=None):
        assert data_dir_file is not None and processed_dir is not None, \
            'ERROR: Both source file (data_dir_file) and destination folder (processed_dir) must be non-null'
        assert os.path.isfile(data_dir_file), 'ERROR: source text file (data_dir_list) must be a valid file'

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
            assert os.path.isdir(job_dir), \
                f'ERROR: job directory `{job_dir}` is not a valid directory. ' + \
                f'Please check the contents of `{self.data_dir_file}` and try again.'



    def extract_all(self):
        for job_dir in (self.job_dirs):
            extractor = CryosparcExtractor(data_dir=job_dir, processed_dir=self.processed_dir)
            extractor.extract()
            # print(f'Finished {job_dir}')

        


if __name__ == '__main__':
    # mpl.use('TkAgg')

    # TODO finish help description
    parser = argparse.ArgumentParser(description='Default help')
    parser.add_argument('-j', '--job-dir', help='Path to the folder containing results of '+
                        '2D extraction (must be a cryoSPARC job!)')
    parser.add_argument('-l', '--job-dir-list', help='Path to a text file that contains a list of various '+
                        'job directories. Each line should contain one path to job folder (no commas).')
    parser.add_argument('-d', '--directory', help='Path to the folder for your lab (e.g. LanderData), '+
					 'or any folder that you would like to store the data in.')
    args = parser.parse_args()

    # Users may only provide one job directory, or one file with a list of job directories
    assert (args.job_dir is not None) != (args.job_dir_list is not None), \
          'ERROR: Please provide either --job_dir or --job-dir-list.'
    
    # Users must provide a lab directory
    assert args.directory is not None, \
          'ERROR: Please provide the valid path to your lab directory with `-d` or `--directory`'
        
    if args.job_dir:
        print('Running single job extraction')
        extractor = CryosparcExtractor(data_dir=args.job_dir, processed_dir=args.directory)
        extractor.extract()
    else:
        print('Running multiple job extraction')
        multi_extractor = MultiCryosparcExtractor(data_dir_file=args.job_dir_list, processed_dir=args.directory)
        multi_extractor.extract_all()