import numpy as np
import pandas as pd
import matplotlib as mpl
import os
import mrcfile
import starfile
import ray
import random
import time
import h5py
import torch
import seaborn as sns

from tqdm import tqdm
from torchvision.transforms import ToTensor
from torch import nn, optim
from torch.utils.data import DataLoader
from matplotlib import pyplot as plt
from matplotlib.patches import Circle

import train
import dataset

# ray.init(ignore_reinit_error=True, num_cpus=4)

DATA_PATH = '/nfs/home/khom/data'





def print_image_sizes():
    sizes = []
    names = os.listdir(DATA_PATH)

    print('Getting image size of each sub-dataset')
    print(f'{len(names)} particles total\n')

    for particle_name in tqdm(names):
        mrc_full_path = os.path.join(DATA_PATH, particle_name, 'run_classes.mrcs')
        if os.path.isdir(os.path.dirname(mrc_full_path)):
            with mrcfile.open(mrc_full_path) as mrc:
                size = mrc.header.tolist()[0]
                sizes.append(size)

    print('Image sizes:')
    print(sizes)

def count_num_images():
    n = 0
    names = os.listdir(DATA_PATH)

    print('Counting total number of 2D class averages')
    print(f'{len(names)} particles total\n')

    for particle_name in tqdm(names):
        mrc_full_path = os.path.join(DATA_PATH, particle_name, 'run_classes.mrcs')
        if os.path.isdir(os.path.dirname(mrc_full_path)):
            with mrcfile.open(mrc_full_path) as mrc:
                n += mrc.header.tolist()[2]

    print(f'\n{n} images total')
                
def print_score(idx, torch_path, hdf5_path, display_target=False):
    file = h5py.File(hdf5_path, 'r')
    imgs = file['data/images']
    targets = pd.read_hdf(hdf5_path, 'targets')

    model = train.MRCNetwork()
    model.load_state_dict(torch.load(torch_path))
    model.eval()

    if display_target:
        target = targets.iloc[idx]['score']
        print(f'Target score: {target}')

    
    
    pred = model(ToTensor()(imgs[idx]).unsqueeze(0)).item()
    print(f'Predicted score: {pred}')

def get_output_shape(model, shape, subnet=None):
    '''
    Prints the shape of the output for a given neural network. Useful since pyTorch
    does not tell you this.
    '''

    t = torch.rand(*shape)
    print(model, '\n\n')

    if subnet == 'cnn':
        print(f'Output shape: {model.cnn_network(t).shape}')


    else:
        feat = torch.rand(1,2)
        print(f'Output shape: {model(t, feat).shape}')


def plot_err_over_time(files, titles):
    threshold = 0.10
    min_ind, max_ind = 10, 1250

    for n, log_filename in enumerate(files):
        with open(log_filename, 'r') as f:
            val_errors = []
            
            for i, line in enumerate(f.readlines()):
                if line.startswith('Batch') and not line.startswith('Batch 101') and (min_ind <= i <= max_ind):
                    try:
                        val = float(line.split(': ')[-1].strip())
                        if val < threshold:
                            val_errors.append(val)
                    except:
                        pass
            
            epoch_start = min_ind
            epoch_end = min(max_ind, len(val_errors) + epoch_start)
            plt.plot(list(range(epoch_start, epoch_end)), val_errors, label=titles[n])

    plt.xlabel('Batch number (in hundreds of batches)')
    plt.ylabel('MSE loss')
    plt.legend()
    plt.show()


def display_scored_images(loader, model, indices, sort=True, clip=True):

    
    num_subplots = 20 # Max number of subplots per plot
    rows, cols = 4, 5
    num_plots = int(np.ceil(len(loader) / num_subplots))
    

    print(f'Data shape: {loader[0][0].shape}')

    scores = []
    for i in range(len(loader)):
        img, score, feat = loader[i]
        pred_score = model(img.unsqueeze(0), feat.unsqueeze(0)).item()

        if clip:
            pred_score = min(1.0, max(pred_score, 0.0))
        scores.append((img, score, pred_score))

    if sort:
        scores.sort(key=lambda x: np.abs(x[1] - x[2]))
    
    for d in range(num_plots):
        fig, axes = plt.subplots(rows, cols)
        fig.suptitle(f'Images {num_subplots*d+1} to {num_subplots*(d+1)}')
        fig.subplots_adjust(hspace=0.4)
        fig.subplots_adjust(wspace=0.4)
        
        for i in range(num_subplots*d, min(num_subplots*(d+1), len(loader))):
            # Display each 2D class avg in a grid
            # img, score, feat = loader[i]
            # pred_score = model(img.unsqueeze(0), feat.unsqueeze(0)).item()
            img, score, pred_score = scores[i]

            ax = axes[(i%num_subplots)//cols, (i%num_subplots)%cols]
            
            ax.axis('off')
            ax.imshow(img[0], cmap='gray')
            ax.set_title(f'{score:.3f} | {pred_score:.3f}', fontsize=10)
            # ax.set_xlabel(f'Index {indices[i]}')

    plt.show()

def display_single_scored_images(data, model, indices):

    for index in indices:
        plt.figure()
        ax = plt.subplot()
        img, score, feat = data[index]
        pred_score = model(img.unsqueeze(0), feat.unsqueeze(0)).item()
        
        ax.imshow(img[0], cmap='gray')
        ax.set_title(f'{score:.3f} | {pred_score:.3f}')
        ax.set_xlabel(f'Index {index}')

    plt.show()

def display_window_radius(data, model, index):
    
    ax = plt.subplot()
    img, score, feat = data[index]
    pred_score = model(img.unsqueeze(0), feat.unsqueeze(0)).item()

    ax.imshow(img[0], cmap='gray')
    ax.set_title(f'{score:.3f} | {pred_score:.3f}')
    ax.set_xlabel(f'Index {index}')

    size = img[0].shape[0]
    print(f'Size: {size}')
    circle = Circle((size//2, size//2), radius=0.85*size/2, fill=False, color='g')
    ax.add_patch(circle)

    plt.show()

def display_scores_heatmap(data, model, indices=None, device='cpu'):

    if indices is None:
        indices = list(range(len(data)))

    
    # imgs, labels, feats = data[indices]
    # imgs, feats = imgs.to(device, dtype=torch.float32),feats.to(device, dtype=torch.float32)
    # imgs = imgs.unsqueeze(1)
    # print(imgs.shape)

    data.select_subset(indices)

    loader = DataLoader(data, batch_size=256, shuffle=False)
    model.eval()
    pred_scores = []
    true_scores = []

    print(f'Calculating predictions for {len(data)} samples...')
    for X, y, feat in tqdm(loader):
        X, y = X.to(device, dtype=torch.float32), y.to(device, dtype=torch.float32)
        feat = feat.to(device, dtype=torch.float)

        pred = model(X.unsqueeze(1), feat)
        pred_scores.extend(pred.flatten().tolist())
        true_scores.extend(y.flatten().tolist())

    err = np.mean((np.array(pred_scores) - np.array(true_scores))**2)
    arr = np.zeros((10, 10), dtype=int)

    # print(pred_scores)

    for k in range(len(data)):
        true_score = true_scores[k]
        pred_score = pred_scores[k]
        pred_score = min(1.0, max(pred_score, 0.0))
        
        i = int(10 * pred_score)
        j = int(10 * true_score)

        if i == 10:
            i -= 1
        if j == 10:
            j -= 1

        arr[i][j] += 1
    
    arr = np.nan_to_num(np.log(arr), neginf=0) 
    print(f'Total MSE of {err}')
    sns.heatmap(arr)
    plt.show()



    # for ind in indices:
    #     img, label, feat = data[ind]
    #     pred_score = model(img.unsqueeze(0), feat.unsqueeze(0)).item()
    #     min(1.0, max(pred_score, 0.0))

    #     i = int(10 * pred_score)
    #     j = int(10 * label)
    #     print(pred_score)
    #     print(label)
    #     print()
    #     if i == 10:
    #         i -= 1
    #     if j == 10:
    #         j -= 10

    #     arr[i][j] += 1
    
    # print(arr)



def plot_scores(model_path, data_path, mode, num=20, use_features=False):
    cuda_main_id = 0
    device = (
        f'cuda:{cuda_main_id}'
        if torch.cuda.is_available()
        # else 'mps'
        # if torch.backends.mps.is_available()
        else 'cpu'
    )
    print(f'Using device {device}')

    device_ids = [cuda_main_id, cuda_main_id+1]

    sequence = train.sequence6
    model = train.MRCNetwork(sequence, use_features=use_features).to(device)
    
    checkpoint = torch.load(model_path, map_location=torch.device(device))
    
    model.load_state_dict(checkpoint['model_state_dict'])
    # model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))
    model = nn.DataParallel(model, device_ids=device_ids).to(device)
    model.eval()

    tensor_transformer = lambda arr: torch.tensor(np.array(arr))

    if mode == 'hdf5':
        data = dataset.MRCImageDataset(
            mode=mode,
            hdf5_path=data_path,
            use_features=use_features,
            transform=tensor_transformer
        )
    else:
        data = dataset.MRCImageDataset(
            mode=mode,
            processed_dir=data_path,
            use_features=use_features,
            transform=tensor_transformer
        )

    # ind = np.random.choice(list(range(len(data))), size=num, replace=False)
    # ind.sort()
    # data.select_subset(ind)
    # print(f'Selected random subset of {num} images')
    # display_scored_images(data, model, ind, sort=True)

    # notable = [23067, 22825, 8478, 16111, 19952]
    # notable.sort()
    # display_single_scored_images(data, model, notable)

    # display_window_radius(data, model, 0)

    display_scores_heatmap(data, model, indices=None, device=device)
    






    

    


def main():
    
    
    # shape = (1, 1, 120, 120)
    # sequence = train.sequence4
    # get_output_shape(train.MRCNetwork(sequence, use_features=True), shape, subnet='cnn')

    logs = [
        '/nfs/home/khom/test_projects/CNNTraining/logs/output_model_0.out',
        '/nfs/home/khom/test_projects/CNNTraining/logs/output_model_1.out',
        '/nfs/home/khom/test_projects/CNNTraining/logs/output_model_2.out',
        '/nfs/home/khom/test_projects/CNNTraining/logs/output_model_3.out'
    ]

    log_titles = [
        'dropout, batch norm',
        'dropout only',
        'dropout, early stop',
        'dropout, batch norm, early stop'
        
    ]
    plot_err_over_time(['/nfs/home/khom/test_projects/CNNTraining/logs/output_model_2.out'], ['model 2'])

    # model_path = '/nfs/home/khom/test_projects/CNNTraining/models/base_model_0.pth'
    # data_path = '/nfs/home/khom/data120.hdf5'
    # mode = 'hdf5'
    # num = 20
    # use_features = True
    # plot_scores(model_path, data_path, mode=mode, num=num, use_features=use_features)



if __name__ == '__main__':
    mpl.use('TkAgg')
    main()