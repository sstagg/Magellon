import torch
import re
import os
import mrcfile
import starfile
import pandas as pd
import numpy as np

from math import ceil

from .mass_est_lib import calc_mass_stats_for_stack
from .util import resize_to_shape, unconvert_labels, normalize

REPLACE_INF = 999.

'''
Contains classes to help you make predictions on data in various formats, given a trained model.
'''

class Predictor:
    '''
    Parent class of the different kinds of predictors
    '''

    def __init__(self, model, save_path, device='cpu'):
        '''
        :param model (torch.nn.Module):
            The model with initialized paramters.
        :param save_path (str):
            Path to the trained model weights as a .pth file.
        :param device (str):
            Location of the device to load the model onto.
        '''

        self.device = device

        checkpoint = torch.load(save_path, map_location=torch.device(device))
        self.model = model.to(device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()

class DatasetPredictor(Predictor):
    '''
    Get predictions on an image or batch of images.

    Accepts an HDF5 dataset, the same kind that is used to train the model. Therefore, it is
    expected that the data has true labels as well. 
    '''

    def predict_single(self, dataset, i):
        '''
        Predict the score of a single image and return it.

        :param dataset (torch.utils.data.Dataset):
            MRCImageDataset of the data.
        :param i (int):
            The index of the image to assess.

        :return (float):
            The predicted score, along with the true score.
        '''
        img, label, feats = dataset[i]
        img = img.to(self.device).unsqueeze(0).unsqueeze(0)
        feats = feats.to(self.device).unsqueeze(0)
        
        with torch.no_grad():
            return self.model(img, feats).item(), label

    def predict_multiple(self, dataset, idxs):
        '''
        Predict the score of multiple images, and return their predicted scores and true scores.

        :param datset (torch.utils.data.Dataset):
            MRCImageDataset of the data.
        :param idxs (list or array of int):
            The indexes of the data to predict for.

        :return (tuple of (predicted scores, true scores)):
            Two arrays containing the predicted and true scores.
        '''
        batch_size = 128
        all_pred = []
        all_true = []
        for k in range(ceil(len(idxs)/batch_size)):

            imgs, labels, feats = dataset[idxs[k*batch_size : (k+1)*batch_size]]
            imgs = imgs.to(self.device).unsqueeze(1)
            feats = feats.to(self.device)

            pred = self.model(imgs, feats).cpu().detach().numpy().flatten()
            
            all_pred.append(pred)
            all_true.append(labels)

        return np.concatenate(all_pred), np.concatenate(all_true)

    

class CryosparcPredictor(Predictor):
    '''
    Get predictions on all 2D averages from a cryoSPARC job.
    '''

    def predict_single(self, job_dir, recover_labels=True, idx=None, feature_scale=None, fixed_len=None):
        '''
        Predict the scores of all images in a single 2D class averaging job.

        :param job_dir (str):
            Path to the job folder (i.e., something like /nfs/home/.../P001/J001/).
        :param recover_labels (bool):
            Whether or not to convert the "training labels", which are in the range [0,1], back
            into the "manual labels", which are either 1, 2, 3, 4, or 5 as provided by human
            labelers. The manual labels are converted to [0,1] for training purposes.
        :param idx (int, optional):
            The iteration of class averages to consider. For example, if idx=10, then the program
            will predict scores for JXXX_10_class_averages.mrc. Default is None, meaning the
            last iteration will be used.
        :param feature_scale (dict, optional): 
            Dict of {feature name : factor} that multiplies each feature by an optional factor 
            before passing it to the model. Used to reduce the magnitude of certain features 
            so they do not overpower the gradients during training.
        :param fixed_len (int or None, optional):
            Will force all images to be the same size. Images that are too small are padded with 0's.
            Images that are too large are down-scaled. (Same as in dataset.py)

        :return (array):
            1D array containing the predicted scores
        '''

        pattern = re.compile(r'J\d+_(\d+)_class_averages.mrc')
        mrc_iter_dict = {int(re.search(pattern, name).group(1)): name
                        for name in os.listdir(job_dir)
                        if re.search(pattern, name)}
        
        if idx is None:
            if len(mrc_iter_dict) == 0:
                raise RuntimeError(f'could not find any MRC files in job {job_dir}. Please check!')
            max_iter = max(mrc_iter_dict.keys())
            mrc_name = mrc_iter_dict[max_iter]
        else:
            if idx not in mrc_iter_dict:
                raise RuntimeError(f'iteration {idx} not found in {job_dir}. Only found: {list(mrc_iter_dict.keys())}')
            mrc_name = mrc_iter_dict[idx]

        mrc_path = os.path.join(job_dir, mrc_name)
        imgs, metadata = self.get_formatted_data(mrc_path, fixed_len=fixed_len)

        if feature_scale is not None:
            for col, factor in feature_scale.items():
                metadata[col] *= factor

        imgs_t = torch.Tensor(imgs).to(torch.float32).unsqueeze(1).to(self.device)
        metadata_t = torch.Tensor(metadata.to_numpy()).to(torch.float32).to(self.device)

        pred = self.model(imgs_t, metadata_t).cpu().detach().numpy().flatten()

        if recover_labels:
            est_res = metadata['est_res']
            weights = ((est_res.min() / est_res) ** 2).fillna(0.).rename('weight')

            pred = unconvert_labels(pred, weights)
            

        return pred

        


    def get_formatted_data(self, mrc_path, fixed_len=None):
        '''
        Collect and format data in preparation for passing to the model.
        Copied from extract_mrc.py
        '''
        
        fixed_len = 210
        
        mrc = mrcfile.open(mrc_path, 'r')
        imgs = []
        for img in mrc.data:
            img = normalize(img)

            if fixed_len:
                if img.shape[1] > fixed_len: 
                    img = resize_to_shape(img, (fixed_len, fixed_len))
                
                diff = fixed_len - img.shape[0]
                pad_before = diff // 2
                pad_after = pad_before + (diff%2)
                img = np.pad(img, (pad_before, pad_after))  

            imgs.append(img)

        imgs = np.array(imgs)
        

        # Find the corresponding metadata files
        metadata_path = mrc_path.replace('.mrc', '.cs')
        particles_path = mrc_path.replace('_class_averages.mrc', '_particles.cs')

        if not os.path.isfile(metadata_path):
            raise RuntimeError(f'missing metadata file: {metadata_path} does not exist')
        if not os.path.isfile(particles_path):
            raise RuntimeError(f'missing particles metadata file: {particles_path} does not exist')
            
        '''
        Metadata will be ordered as:
        1. Estimated resolution in Angstroms
        2. Class distribution (fraction)
        3. Pixel size in Angstroms
        4. Mean mass
        5. Median mass
        6. Mode mass
        '''

        # Metadata stored in .cs files
        metadata_names = ['est_res', 'class_dist', 'pixel_size']
        metadata = [None, None, None]

        # Metadata from the mass estimator (remove estimated mass; it is useless as a parameter)
        mass_est_names = ['dmean_mass', 'dmedian_mass', 'dmode_mass']
        mass_est = pd.DataFrame.from_records(calc_mass_stats_for_stack(mrc_path))
        #mass_est['dmode'] = mass_est['dmode'].apply(lambda x: x[0])
        mass_est = mass_est.drop(columns=['mass']).to_numpy()
        
        # Grab resolution and pixel size directly from the .cs averages file
        class_metadata = np.load(metadata_path)
        metadata[0] = class_metadata['blob/res_A']
        metadata[2] = class_metadata['blob/psize_A']

        # Calculate class distribution from the .cs particles file
        particle_metadata = np.load(particles_path, mmap_mode='r')
        particles_df = pd.DataFrame(particle_metadata[['uid', 'alignments2D/class']])
        class_dist = particles_df.groupby('alignments2D/class').count()
        metadata[1] = class_dist['uid'] / len(particles_df)
        metadata[1] = metadata[1].reindex(list(range(len(metadata[0])))).fillna(0.)

        # Assemble everything into a single structured array representing all class averages in the file
        raw_metadata = np.rec.array(np.vstack(metadata), names=metadata_names).T
        all_metadata = pd.DataFrame(np.rec.fromarrays(np.concatenate((raw_metadata, mass_est), axis=1).T, 
                              names=metadata_names+mass_est_names))

        return imgs, all_metadata
        




class RelionPredictor(Predictor):
    '''
    Get predictions on all 2D averages from a RELION 2D class averaging job.
    '''
    
    def predict_single(self, mrcs_path, model_path, recover_labels=True, feature_scale=None, fixed_len=None):
        '''
        Predict the scores of all images in a single 2D class averaging job.

        :param mrcs_path (str):
            Path to the MRCS file containing the class averages. It should look like 
            `run_itXXX_classes.mrcs`.
        :param model_path (str):
            Path to the model STAR file containing metadata on each class average. It should look
            like `run_itXXX_model.star`.
        :param recover_labels (bool):
            Whether or not to convert the "training labels", which are in the range [0,1], into
            the range [1,5]. RELION has a different labeling system, but this function will convert 
            them to the same range [1,5] for continuity purposes.
        :param feature_scale (dict, optional): 
            Dict of {feature name : factor} that multiplies each feature by an optional factor 
            before passing it to the model. Used to reduce the magnitude of certain features 
            so they do not overpower the gradients during training. (Same as in dataset.py)
        :param fixed_len (int or None, optional):
            Will force all images to be the same size. Images that are too small are padded with 0's.
            Images that are too large are down-scaled. (Same as in dataset.py).
        '''

        imgs, metadata = self.get_formatted_data(mrcs_path, model_path, fixed_len=fixed_len)

        if feature_scale is not None:
            for col, factor in feature_scale.items():
                metadata[col] *= factor

        imgs_t = torch.Tensor(imgs).to(torch.float32).unsqueeze(1).to(self.device)
        metadata_t = torch.Tensor(metadata.to_numpy()).to(torch.float32).to(self.device)

        pred = self.model(imgs_t, metadata_t).cpu().detach().numpy().flatten()

        if recover_labels:
            est_res = metadata['est_res']
            weights = ((est_res.min() / est_res) ** 2).fillna(0.).rename('weight')

            pred = unconvert_labels(pred, weights)

        return pred
        

    def get_formatted_data(self, mrcs_path, model_path, fixed_len=None):
        '''
        Collect and format data in preparation for passing to the model.
        Mostly copied from MRCPreprocessor in dataset.py.
        '''

        mrc = mrcfile.open(mrcs_path)

        imgs = []
        for img in mrc.data:
            img = normalize(img)

            if fixed_len:
                if img.shape[1] > fixed_len: 
                    img = resize_to_shape(img, (fixed_len, fixed_len))
                
                diff = fixed_len - img.shape[0]
                pad_before = diff // 2
                pad_after = pad_before + (diff%2)
                img = np.pad(img, (pad_before, pad_after))  

            imgs.append(img)

        imgs = np.array(imgs)
        mrc.close()

        '''
        Metadata will be ordered as:
        1. Estimated resolution in Angstroms
        2. Class distribution (fraction)
        3. Pixel size in Angstroms
        4. Mean mass
        5. Median mass
        6. Mode mass
        '''

        model_star = starfile.read(model_path, read_n_blocks=2, always_dict=False)
        model_general = pd.DataFrame(model_star['model_general'], index=[0])
        model_classes = model_star['model_classes']

        est_res = model_classes['rlnEstimatedResolution']
        class_dist = model_classes['rlnClassDistribution']
        pixel_size = model_general['rlnPixelSize'].item()
        

        mass_est = pd.DataFrame.from_records(calc_mass_stats_for_stack(mrcs_path))
        #mass_est['dmode'] = mass_est['dmode'].apply(lambda x: x[0])
        mass_est = mass_est.drop(columns=['mass']).clip(upper=1e9).add_suffix('_mass') 

        metadata = pd.DataFrame(data={
            'est_res': est_res,
            'class_dist': class_dist,
            'pixel_size': pixel_size,
        })

        metadata = pd.concat((metadata, mass_est), axis=1).replace([np.inf, -np.inf], REPLACE_INF)
        return imgs, metadata
        
