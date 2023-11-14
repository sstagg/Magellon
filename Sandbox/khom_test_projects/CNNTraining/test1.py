import numpy as np
import pandas as pd
import matplotlib as mpl
import os
import mrcfile
# import starfile
# import ray
# import random
# import time
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

print('Imports done')

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
                
def print_scores(idx, model, data, display_target=True):
    # file = h5py.File(hdf5_path, 'r')
    # imgs = file['data/images']
    # targets = pd.read_hdf(hdf5_path, 'targets')

    # transformer = None#lambda arr: torch.tensor(np.array(arr)).unsqueeze(-3)
    # data = dataset.MRCImageDataset(mode='hdf5', hdf5_path=hdf5_path, use_features=True, transform=transformer)

    # model = train.MRCNetwork(4608, train.sequence8, use_features=True)
    # model.load_state_dict(torch.load(torch_path)['model_state_dict'])
    # model.eval()

    err = 0.

    shapes = []
    errors = []

    for i in tqdm(idx):
        img, label, feats = data[i]

        if not isinstance(img, np.ndarray):
            img = np.array(img)


        # diff = 230 - img.shape[-1]
        # pad_before = diff // 2
        # pad_after = pad_before + (diff%2)
        # img = np.pad(img, ((0,0), (0,0), (pad_before, pad_after), (pad_before, pad_after)))
        with torch.no_grad():
            img = torch.Tensor(img).to('cuda:0')#.unsqueeze(0).unsqueeze(0)
            feats = feats.unsqueeze(0).to('cuda:0')
            # print(img.shape)
            pred = model(img, feats).item()
            # print(label, pred, img.shape)
            # print(f'{label :.5f} -- {pred :.5f} -- {img.shape}')
            err += (label - pred)**2

            shapes.append(img.shape[-1])
            errors.append((label - pred)**2)


    # print(shapes)
    # print(errors)
    print(f'MSE: {err / len(idx)}')
    plt.scatter(shapes,errors)
    plt.show()
    

    
    
    
    # pred = model(ToTensor()(imgs[idx]).unsqueeze(0)).item()
    # print(f'Predicted score: {pred}')

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
        feat = torch.rand(1,3)
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

    # plt.xlabel('Batch number (in hundreds of batches)')
    # plt.ylabel('MSE loss')
    # plt.legend()
    # plt.show()


def display_scored_images(data, model, sort=True, clip=True, device='cpu'):


    idx = np.sort(np.random.choice(list(range(len(data))), size=100, replace=False))
    data.select_subset(idx)
    
    num_subplots = 20 # Max number of subplots per plot
    rows, cols = 4, 5
    num_plots = int(np.ceil(len(data) / num_subplots))

    scores = []
    for i in range(len(data)):
        img, score, feat = data[i]
        img = torch.Tensor(img).to(device, dtype=torch.float)
        feat = feat.to(device, dtype=torch.float)
        pred_score = model(img, feat.unsqueeze(0)).item()

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
        
        for i in range(num_subplots*d, min(num_subplots*(d+1), len(data))):
            # Display each 2D class avg in a grid
            # img, score, feat = loader[i]
            # pred_score = model(img.unsqueeze(0), feat.unsqueeze(0)).item()
            img, score, pred_score = scores[i]

            ax = axes[(i%num_subplots)//cols, (i%num_subplots)%cols]
            
            ax.axis('off')
            ax.imshow(img[0][0], cmap='gray')
            ax.set_title(f'{score:.3f} | {pred_score:.3f}', fontsize=10)
            # ax.set_xlabel(f'Index {indices[i]}')

        fig.savefig(f'scored_imgs_{d}.png')
        print(f'Finished plot {d}')


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

def display_scores_heatmap(data, model, idx=None, device='cpu'):

    if idx is None:
        idx = list(range(len(data)))

    
    # imgs, labels, feats = data[indices]
    # imgs, feats = imgs.to(device, dtype=torch.float32),feats.to(device, dtype=torch.float32)
    # imgs = imgs.unsqueeze(1)
    # print(imgs.shape)

    # data.select_subset(indices)
    # loader = DataLoader(data, batch_size=32, shuffle=False)
    
    model.eval()
    pred_scores = []
    true_scores = []

    print(f'Plotting scores heatmap')
    print(f'Calculating predictions for {len(data)} samples...')
    with torch.no_grad():
        for i in tqdm(idx):
            X, y, feats = data[i]

            if not isinstance(X, np.ndarray):
                X = np.array(X)

            X = torch.Tensor(X).to(device, dtype=torch.float32)
            feats = feats.to(device, dtype=torch.float).unsqueeze(0)

            pred = model(X, feats)
            pred_scores.extend(pred.flatten().tolist())
            true_scores.extend(y.flatten().tolist())

        err = np.mean((np.array(pred_scores) - np.array(true_scores))**2)
        arr = np.zeros((11, 11), dtype=int)


    # print(pred_scores)

    for k in range(len(data)):
        true_score = true_scores[k]
        pred_score = pred_scores[k]
        pred_score = min(1.0, max(pred_score, 0.0))
        
        i = round(10 * pred_score)
        j = round(10 * true_score)

        # print(f'{true_score :.5f}, {pred_score :.5f}')

        # if i == 10:
        #     i -= 1
        # if j == 10:
        #     j -= 1

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

    sequence = train.sequence7
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

    # display_scores_heatmap(data, model, idx=None, device=device)
    

# Test function for making a HDF5 dataset with variable size arrays
def ragged_hdf5_dataset():
    
    path = 'tmp_h5.hdf5'

    if os.path.isfile(path):
        os.remove(path)

    file = h5py.File(path, 'a')
    variable_dt = h5py.vlen_dtype(np.float32)
    img_data = file.create_dataset('data/images',
                                   shape=(2,),
                                   maxshape=(None,),
                                   chunks=(1,),
                                   dtype=variable_dt)
    
    img_data[0] = np.zeros(100)
    img_data[1] = np.zeros(445)
    # img_data[2] = np.zeros(21)

    img_data.resize((3,))

    img_data[2] = np.zeros(21)
    




    
    print(img_data.shape)
    


def main():
    
    
    # ragged_hdf5_dataset()
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
    plot_err_over_time(['/nfs/home/khom/test_projects/CNNTraining/logs/experiment_model_1.out'], ['model 1'])

    # model_path = '/nfs/home/khom/test_projects/CNNTraining/models/base_model_0.pth'
    # data_path = '/nfs/home/khom/data120.hdf5'
    # mode = 'hdf5'
    # num = 20
    # use_features = True
    # plot_scores(model_path, data_path, mode=mode, num=num, use_features=use_features)

def main1():
    mpl.use('TkAgg')
    # main()
    transform = lambda arr: torch.tensor(np.array(arr)).unsqueeze(0).unsqueeze(0)
    device = 'cpu'

    data = dataset.MRCImageDataset(
            mode='hdf5',
            hdf5_path='/nfs/home/khom/data-vlen2.hdf5',
            use_features=True,
            # transform=transform
    )
    # indices = np.random.choice(list(range(26389)), size=200, replace=False)
    indices = list(range(26389))
    indices.sort()
    model = train.MRCNetwork(4608, train.sequence5, use_features=True).to(device)

    model_path = '/nfs/home/khom/test_projects/CNNTraining/models/experiment_model_1.pth'
    saved_model = torch.load(model_path, map_location=torch.device(device))
    model.load_state_dict(saved_model['model_state_dict'])
    
    # display_scores_heatmap(data, model, idx=indices, device=device)
    # print_scores(indices, model, data, display_target=True)
    display_scored_images(data, model, indices, device=device)

if __name__ == '__main__':
    main1()

