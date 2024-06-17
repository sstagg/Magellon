import os
import torch
import time
import numpy as np

import dataset
from util import Timer

from torch import nn, optim
from torch.nn import Conv2d, Linear, Dropout, ReLU, MaxPool2d, Flatten, Sequential, BatchNorm2d, AdaptiveAvgPool2d

from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split

'''
ISSUES:
- Look for all TODOs
- Place a safeguard so that sequences that can only accept vlen data will perform a pre-check 
'''

'''
RELION 4.0's method is:

target = (a*weight + b)*job_score

where 
    weight is (min_job_resolution / resolution) ** 2
    a and b are hyperparameters depending on the manually assigned score 
        (a,b) = (0.75, 0.25) if score is 1
        (a,b) = (0.5, 0.25) is score is 5
        (a,b) = (0.25, 0.25) if score is 2
        (a,b) = (0, 0.25) is score is 3 or 4
        (a,b) = (0,0) otherwise (e.g. 0)
    job_score is a manually assigned value from 0 to 1 that quantifies the quality of 
    the 2D classification job overall. Sometimes, this value is 0, often leading to
    images of high quality that are have a target of 0.

Possible new scoring methodology:
target = (a + b)
Remove weight and job_score. This discretizes the possible targets to (1, 0.75, 0.5, 0.25, 0)
However, having only 4 target scores may not be enough to differentiate among classes.

Alternatively, we could directly manually assign target scores of 0, 0.1, 0.2,..., 1.0.


'''




'''
Architecture?

1. Double-trained CNN. First train one CNN with no metadata. Then, cut it off right before
the final classification layer, append the metadata, and train another standard FF NN
2. Residual CNN. Only needed if we need a very deep network, which is unlikely
 
TODO
    Consider allowing the network to accept input images of varying size.
    Could either:
        (1) Add AdaptiveAvgPool2D before the flattened layers
        (2) Add torch.nn.functional.interpolate at the beginning to downsample
'''



# Various types of CNN architectures to explore:
def sequence1(num_features=0, dropout=0.3):
    '''
    If using features, will return two Sequentials, where the extra features should be
    concatenated to the output of the first Sequential, then fed into the second Sequential.

    If not using features, it will return a single Sequential representing the whole network
    '''

    cnn_layers = [
        Conv2d(1, 16, 3, bias=True),
        ReLU(),
        Dropout(dropout),
        Conv2d(16, 32, 3, bias=True),
        ReLU(),

        MaxPool2d(2, stride=2),
        Dropout(dropout),

        Conv2d(32, 32, 3, bias=True),
        ReLU(),
        Dropout(dropout),
        Conv2d(32, 64, 3, bias=True),
        ReLU(),

        MaxPool2d(2, stride=2),
        Dropout(dropout),
        
        Flatten(),
        Linear(18496, 128),
        ReLU(),
        Dropout(dropout),
        # Linear(128, 1)
    ]

    feature_layers = [
        Linear(128 + num_features, 16),
        ReLU(),
        Dropout(dropout),
        Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence2(num_features=0, dropout=0.25):
    cnn_layers = [
        Conv2d(1, 16, 3, bias=True),
        ReLU(),
        Dropout(dropout),
        Conv2d(16, 32, 3, bias=True),
        ReLU(),
        Dropout(dropout),

        MaxPool2d(2, stride=2),

        Conv2d(32, 32, 3, bias=True),
        ReLU(),
        Dropout(dropout),
        Conv2d(32, 64, 3, bias=True),
        ReLU(),
        Dropout(dropout),

        MaxPool2d(2, stride=2),

        Conv2d(64, 64, 3, bias=True),
        ReLU(),
        Dropout(dropout),
        Conv2d(64, 128, 3, bias=True),
        ReLU(),
        Dropout(dropout),

        MaxPool2d(2, stride=2),
        
        Flatten(),
        Linear(15488, 4096),
        ReLU(),
        Dropout(dropout),
        Linear(4096, 128),
        ReLU(),
        Dropout(dropout),
        # Linear(128, 1)
    ]

    feature_layers = [
        Linear(128 + num_features, 16),
        ReLU(),
        Dropout(dropout),
        Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence3(num_features=0, dropout=0.25):
    cnn_layers = [
        Conv2d(1, 32, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(32, 32, 3, padding=1),
        ReLU(),
        Dropout(dropout),

        Conv2d(32, 32, 3, stride=2),
        Dropout(dropout),

        # -----

        Conv2d(32, 64, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(64, 64, 3, padding=1),
        ReLU(),
        Dropout(dropout),

        Conv2d(64, 64, 3, stride=2),

        # -----

        Conv2d(64, 128, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(128, 128, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(128, 128, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(128, 128, 3, padding=1),
        ReLU(),
        Dropout(dropout),

        Conv2d(128, 128, 3, stride=2),

        # ----


        Conv2d(128, 256, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(256, 256, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(256, 256, 3, padding=1),
        ReLU(),
        Dropout(dropout),
        Conv2d(256, 256, 3, padding=1),
        ReLU(),
        Dropout(dropout),

        Conv2d(256, 256, 3, stride=2),
        

        
        Flatten(),
        Linear(9216, 512),
        ReLU(),
        Dropout(dropout),
        Linear(512, 64),
        ReLU(),
        Dropout(dropout),

        ## Linear(64, 1)
    ]

    feature_layers = [
        Linear(64 + num_features, 16),
        ReLU(),
        Dropout(dropout),
        Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence4(fc_size, num_features=0, dropout=0.25):
    cnn_layers = [
        ResidualConvBlock(1, 16, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(16, 16, 3, downsample=True),
        Dropout(dropout),
        Conv2d(16, 16, 3, stride=2),
        Dropout(dropout),
        ResidualConvBlock(16, 32, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(32, 32, 3, downsample=True),
        Dropout(dropout),
        Conv2d(32, 32, 3, stride=2),
        
        ResidualConvBlock(32, 64, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        Dropout(dropout),
        Conv2d(64, 64, 3, stride=2),
        
        ResidualConvBlock(64, 128, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        Dropout(dropout),
        Conv2d(128, 128, 3, stride=2),

        Flatten(),
        Linear(fc_size, 64),
        ReLU(),
        Dropout(dropout),
    ]

    feature_layers = [
        Linear(64 + num_features, 16),
        ReLU(),
        Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence5(fc_size, num_features=0, dropout=0.25):
    '''
    Based on sequence 4, but designed for variable size data (must still be square) 
    THIS IS THE BEST ONE FOR VLEN DATA!!
    '''
    cnn_layers = [
        ResidualConvBlock(1, 16, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(16, 16, 3, downsample=True),
        Dropout(dropout),
        Conv2d(16, 16, 3, stride=2),
        Dropout(dropout),
        ResidualConvBlock(16, 32, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(32, 32, 3, downsample=True),
        Dropout(dropout),
        Conv2d(32, 32, 3, stride=2),
        
        ResidualConvBlock(32, 64, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        Dropout(dropout),
        Conv2d(64, 64, 3, stride=2),
        
        ResidualConvBlock(64, 128, 3, downsample=True),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        Dropout(dropout),
        Conv2d(128, 128, 3, stride=2),

        AdaptiveAvgPool2d((6,6)),
        Dropout(dropout),
        Flatten(),
        Linear(4608, 64),
        ReLU(),
        Dropout(dropout)
    ]

    feature_layers = [
        Linear(64 + num_features, 16),
        ReLU(),
        Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence6(fc_size, num_features=0, dropout=0.25):
    '''
    Based on sequence 4, but with batch normalization applied after each residual block

    THIS IS THE BEST ONE FOR SAME SHAPE DATA!!
    '''
    cnn_layers = [
        ResidualConvBlock(1, 16, 3, downsample=True, batchnorm=True), 
        BatchNorm2d(16),
        Dropout(dropout),
        ResidualConvBlock(16, 16, 3, downsample=True, batchnorm=True),
        BatchNorm2d(16),
        Dropout(dropout),
        Conv2d(16, 16, 3, stride=2),                                  # /2
        BatchNorm2d(16),
        Dropout(dropout),
        ResidualConvBlock(16, 32, 3, downsample=True, batchnorm=True),
        BatchNorm2d(32),
        Dropout(dropout),
        ResidualConvBlock(32, 32, 3, downsample=True, batchnorm=True),
        BatchNorm2d(32),
        Dropout(dropout),
        Conv2d(32, 32, 3, stride=2),                                  # /2
        BatchNorm2d(32),
        
        ResidualConvBlock(32, 64, 3, downsample=True, batchnorm=True),
        BatchNorm2d(64),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        BatchNorm2d(64),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        BatchNorm2d(64),
        Dropout(dropout),
        Conv2d(64, 64, 3, stride=2),                                  # /2
        BatchNorm2d(64),
        
        ResidualConvBlock(64, 128, 3, downsample=True, batchnorm=True),
        BatchNorm2d(128),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        BatchNorm2d(128),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        BatchNorm2d(128),
        Dropout(dropout),
        Conv2d(128, 128, 3, stride=2),                                # /2
        BatchNorm2d(128),

        Flatten(),
        Linear(fc_size, 64),
        ReLU(),
        Dropout(dropout),
    ]

    feature_layers = [
        Linear(64 + num_features, 16),
        ReLU(),
        Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence7(fc_size, num_features=0, dropout=0.25):
    '''    
    Based on sequence 6, but with designed to be trained on padded variables

    Input image dimensions must be at least 
    '''
    cnn_layers = [
        ResidualConvBlock(1, 16, 3, downsample=True, batchnorm=True), 
        BatchNorm2d(16),
        Dropout(dropout),
        ResidualConvBlock(16, 16, 3, downsample=True, batchnorm=True),
        BatchNorm2d(16),
        Dropout(dropout),
        Conv2d(16, 16, 3, stride=2),                                  # /2
        BatchNorm2d(16),
        Dropout(dropout),
        
        ResidualConvBlock(16, 32, 3, downsample=True, batchnorm=True),
        BatchNorm2d(32),
        Dropout(dropout),
        ResidualConvBlock(32, 32, 3, downsample=True, batchnorm=True),
        BatchNorm2d(32),
        Dropout(dropout),
        Conv2d(32, 32, 3, stride=2),                                  # /2
        BatchNorm2d(32),
        Dropout(dropout),
        
        ResidualConvBlock(32, 64, 3, downsample=True, batchnorm=True),
        BatchNorm2d(64),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        BatchNorm2d(64),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3),
        BatchNorm2d(64),
        Dropout(dropout),
        Conv2d(64, 64, 3, stride=2),                                  # /2
        BatchNorm2d(64),
        Dropout(dropout),
        
        ResidualConvBlock(64, 128, 3, downsample=True, batchnorm=True),
        BatchNorm2d(128),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        BatchNorm2d(128),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3),
        BatchNorm2d(128),
        Dropout(dropout),
        Conv2d(128, 128, 3, stride=2),                                # /2
        BatchNorm2d(128),
        Dropout(dropout),

        AdaptiveAvgPool2d((6,6)),
        Flatten(),
        ReLU(),
        # Linear(fc_size, 64),
        # ReLU(),
        # Dropout(dropout),
    ]

    feature_layers = [
        Linear(4608 + num_features, 1),
        # ReLU(),
        # Linear(16, 1)
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)

def sequence8(fc_size, num_features=0, dropout=0.25):
    '''    
    Based on sequence 7, but with no FC layers, and with batchnorm applied to
    each layer including inside residual blocks
    '''
    cnn_layers = [
        ResidualConvBlock(1, 16, 3, downsample=True, batchnorm=True), 
        BatchNorm2d(16),
        Dropout(dropout),
        ResidualConvBlock(16, 16, 3, downsample=True, batchnorm=True),
        BatchNorm2d(16),
        Dropout(dropout),
        Conv2d(16, 16, 3, stride=2),                                  # /2
        BatchNorm2d(16),
        Dropout(dropout),
        
        ResidualConvBlock(16, 32, 3, downsample=True, batchnorm=True),
        BatchNorm2d(32),
        Dropout(dropout),
        ResidualConvBlock(32, 32, 3, downsample=True, batchnorm=True),
        BatchNorm2d(32),
        Dropout(dropout),
        Conv2d(32, 32, 3, stride=2),                                  # /2
        BatchNorm2d(32),
        Dropout(dropout),
        
        ResidualConvBlock(32, 64, 3, downsample=True, batchnorm=True),
        BatchNorm2d(64),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3, batchnorm=True),
        BatchNorm2d(64),
        Dropout(dropout),
        ResidualConvBlock(64, 64, 3, batchnorm=True),
        BatchNorm2d(64),
        Dropout(dropout),
        Conv2d(64, 64, 3, stride=2),                                  # /2
        BatchNorm2d(64),
        Dropout(dropout),
        
        ResidualConvBlock(64, 128, 3, downsample=True, batchnorm=True),
        BatchNorm2d(128),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3, batchnorm=True),
        BatchNorm2d(128),
        Dropout(dropout),
        ResidualConvBlock(128, 128, 3, batchnorm=True),
        BatchNorm2d(128),
        Dropout(dropout),
        Conv2d(128, 128, 3, stride=2),                                # /2
        BatchNorm2d(128),
        Dropout(dropout),

        AdaptiveAvgPool2d((6,6)), # size after this layer is (N,128,6,6)
        Flatten(),
        ReLU(),

    ]

    feature_layers = [
        Linear(4608 + num_features, 1),
    ]

    return Sequential(*cnn_layers), Sequential(*feature_layers)


class ResidualConvBlock(nn.Module):
    '''
    One residual convolutional block, with a skip connection from its input to its output 
    '''
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, downsample=False, batchnorm=False):
        super().__init__()

        self.nonlinear = ReLU()

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.downsample = downsample

        self.layer1 = Sequential(
            Conv2d(in_channels, out_channels, kernel_size, stride=stride, padding=1),
            ReLU()
        )

        self.layer2 = Sequential(
            Conv2d(out_channels, out_channels, kernel_size, stride=1, padding=1),
            ReLU()
        )
        
        self.downsampler = None
        if downsample:
            self.make_downsampler()

        self.batchnorm = None
        if batchnorm:
            self.make_batchnorm()

        
    
    def forward(self, x):
        residual = x
        if self.downsample:
            residual = self.downsampler(residual)
        
        r1 = self.layer1(x)
        if self.batchnorm:
            r1 = self.batchnorm(r1)

        result = self.layer2(r1) + residual
        return self.nonlinear(result)
    
    def make_downsampler(self):
        '''
        Create a downsampler to downsample the residual to the required number of channels
        '''
        self.downsampler = Sequential(
            Conv2d(self.in_channels, self.out_channels, self.kernel_size, padding=1)
        )

    def make_batchnorm(self):
        '''
        Create a batch normalization layer in between convolutional blocks
        '''

        self.batchnorm = Sequential(
            BatchNorm2d(self.out_channels)
        )





class MRCNetwork(nn.Module):
    def __init__(self, fc_size, sequence, num_features):
        super().__init__()
        self.cnn_network, self.feat_network = sequence(fc_size, num_features)
        self.use_features = num_features > 0

    def forward(self, x, feat=None):
        x = self.cnn_network(x)
        if self.use_features:    
            x = torch.cat([x, feat], dim=1)

        return self.feat_network(x)    


class Trainer:
    '''
    A class designed to allow users to efficiently train a model.
    '''
    def __init__(self, model, loss_fn, optimizer, data_path,
                 batch_size=32, val_frac=None, device='cuda:0', parallel_device_ids=None, 
                 use_features=False, vlen_data=False,
                 save_path=None, preload=None):
        self.model = model
        self.loss_fn = loss_fn
        self.optimizer = optimizer

        self.batch_size = batch_size
        self.val_frac = val_frac
        self.device = device
        self.parallel_device_ids = parallel_device_ids
        self.use_features = use_features
        self.vlen_data = vlen_data
        self.save_path = save_path

        self.cur_epoch = 0

        print('\nTRAINING OVERVIEW\n-------------------------------')
        print('OPTIMIZER:\n', optimizer, '\n-------------------------------') 
        print('LOSS FUNCTION:\n', loss_fn, '\n-------------------------------')
        print('MODEL ARCHITECTURE:\n', model, '\n-------------------------------')
        print(f'OTHER:')
        print(f'Training with batch size of {batch_size}')
        print(f'Running on device {device}')
        if val_frac:
            print(f'Split {val_frac*100.:.2f}% of data for validation data')
        if parallel_device_ids:
            print(f'Preparing to train in parallel: main device on {self.device}, all devices on {parallel_device_ids}')
            self.init_data_parallel(parallel_device_ids)
        if save_path:
            print(f'Will save model to {save_path}')
        else:
            print('WARNING: will not save the model to a file!')
        if preload:
            print(f'Loading saved weights from {preload}')
            self.load_model(preload)

        if vlen_data:
             print('Expecting variable sized data')
             tensor_transformer = lambda arr: torch.Tensor(arr[0]).unsqueeze(0) # Use for variable size data
        else:
            print('Expecting fixed size data')
            tensor_transformer = lambda arr: torch.tensor(np.array(arr)).unsqueeze(-3) # Use for fixed size data

        print('-------------------------------\n')

        feature_scale = {'dmean_mass': 1e-5, 'dmedian_mass': 1e-5, 'dmode_mass': 1e-5}

        self.train_dataset = dataset.MRCImageDataset(
            mode='hdf5',
            hdf5_path=data_path,
            use_features=use_features,
            transform=tensor_transformer,
            feature_scale=feature_scale
        )

        self.val_dataset = dataset.MRCImageDataset(
            mode='hdf5',
            hdf5_path=data_path,
            use_features=use_features,
            transform=tensor_transformer,
            feature_scale=feature_scale
        )

        indices = list(range(len(self.train_dataset)))

        # If resuming training, then use the train/validation indices from the previous training
        # Otherwise, randomly sample train and validation sets
        if preload is None:
            if val_frac:
                train_ind, val_ind = train_test_split(indices, test_size=val_frac, shuffle=True)
            else:
                train_ind, val_ind = indices, []
            
            train_ind.sort()
            val_ind.sort()

            self.train_ind = train_ind
            self.val_ind = val_ind
        else:
            print('Using previous training validation set')
        
        # indices = list(range(1000))
        # self.train_ind, self.val_ind = train_test_split(indices, test_size=val_frac, shuffle=True)
        # self.train_ind.sort()
        # self.val_ind.sort()

        self.train_dataset.select_subset(self.train_ind)
        self.val_dataset.select_subset(self.val_ind)

        train_collate_fn = self.train_dataset.make_collate_fn()
        val_collate_fn = self.val_dataset.make_collate_fn()

        self.train_loader = DataLoader(self.train_dataset, batch_size=batch_size, shuffle=True, collate_fn=train_collate_fn)
        self.val_loader = DataLoader(self.val_dataset, batch_size=batch_size, shuffle=True, collate_fn=val_collate_fn)

        print('Ready to train\n')

    def init_data_parallel(self, device_ids):
        self.model = nn.DataParallel(self.model, device_ids=device_ids).to(self.device)

    def train_loop(self, print_freq=100):
        '''
        Trains the model for one epoch

        :param val_loader: a second data loader for validation data, which will be evaluated every
        100 batches.

        '''

        def predict_vlen(X, feat, y):

            a = torch.Tensor([self.model(
                x.to(self.device, dtype=torch.float), 
                f.unsqueeze(0),
                ).squeeze() for x,f in zip(X, feat)]).to(self.device)

            # print(a)
            # print(a.shape)
            # print(y.shape)
            # print(self.loss_fn(a, y))
            loss = self.loss_fn(a, y)
            loss.requires_grad = True
            return loss
        
        size, n_batches, batch_size = len(self.train_loader.dataset), len(self.train_loader), self.train_loader.batch_size
        timer = Timer()

        for batch, (X, y, feat) in enumerate(self.train_loader):
            # print(X.shape, y.shape, feat.shape)
            self.model.train()
            
            y = y.to(self.device, dtype=torch.float)
            feat = feat.to(self.device, dtype=torch.float)


            if type(X) == list and len(X) > 1:
                loss = predict_vlen(X, feat, y)
            else:
                if type(X) == list:
                    X = X[0]
                X = X.to(self.device, dtype=torch.float)
                pred = self.model(X, feat)
                loss = self.loss_fn(pred, y.unsqueeze(1))
            
            loss.backward()
            self.optimizer.step()
            self.optimizer.zero_grad()

            if (batch % print_freq == 0 or batch == n_batches-1) and batch > 0:
                loss, current = loss.item(), min((batch + 1) * batch_size, size)
                elapsed = timer.get_elapsed(reset=True)
                print(f'Batch {batch+1:>3d}/{n_batches}, loss: {loss:>7f}  [{current:>5d}/{size:>5d}] ({elapsed:.3f}s)', end=' ')
                if self.val_frac:
                    val_loss = self.get_val_error()
                    print(f'val loss: {val_loss:>7f}', end='')
                print('')

    def get_val_error(self):
        '''
        Returns the mean MSE for all items in the given dataset
        '''

        def predict_vlen(X, feat, y):
            a = torch.stack([self.model(
                x.to(self.device, dtype=torch.float), 
                f.unsqueeze(0),
                ).squeeze() for x,f in zip(X, feat)]).to(self.device)

            loss = self.loss_fn(a, y)
            return loss

        self.model.eval()

        n_batches = len(self.val_loader)
        total_loss = 0.
        with torch.no_grad():
            for X, y, feat in self.val_loader:
                y = y.to(self.device, dtype=torch.float)
                feat = feat.to(self.device, dtype=torch.float)
                if type(X) == list:
                    total_loss += predict_vlen(X, feat, y).item()
                else:
                    X = X.to(self.device, dtype=torch.float)
                    pred = self.model(X, feat)
                    total_loss += self.loss_fn(pred, y.unsqueeze(1)).item()
        
        return total_loss / n_batches
    
    def run_training(self, epochs=10, print_freq=100):
        main_timer, loop_timer = Timer(), Timer()
        print(f'Beginning training for {epochs} epochs (from epoch {self.cur_epoch+1})...')
        
        for e in range(epochs):
            self.cur_epoch += 1
            print(f'Epoch {self.cur_epoch}\n-------------------------------')
            self.train_loop(print_freq=print_freq)

            if self.save_path:
                self.save_model(self.cur_epoch)
                print(f'Saved to {self.save_path}')
            print(f'Took {loop_timer.get_elapsed(reset=True):.3f}s total\n-------------------------------\n')

        print(f'Took {main_timer.get_elapsed():.4f} seconds')
        print('Done!\n')

    def save_model(self, epoch, all_params=True):
        if all_params:
            torch.save({
                'epoch': epoch,
                'train_ind': self.train_ind,
                'val_ind': self.val_ind,
                'model_state_dict': self.model.module.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
            }, self.save_path)
        else:
            torch.save(self.model.module.state_dict(), self.save_path)

    def load_model(self, model_path):
        '''
        Load a previously trained model to continue training
        '''
        checkpoint = torch.load(model_path, map_location=torch.device(self.device))
        self.model.module.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        self.cur_epoch = checkpoint['epoch']
        self.val_ind = checkpoint['val_ind']

        if 'train_ind' not in checkpoint:
            # TODO don't hardcode this!!!
            self.train_ind = [i for i in range(26389) if i not in self.val_ind]
        else:
            self.train_ind = checkpoint['train_ind']



def main_old():

    use_features = True
    sequence = sequence5
    cuda_main_id = 0
    preload = '/nfs/home/khom/test_projects/CNNTraining/models/experiment_model_0.pth'

    device = (
        f'cuda:{cuda_main_id}'
        if torch.cuda.is_available()
        # else 'mps'
        # if torch.backends.mps.is_available()
        else 'cpu'
    )


    print(f'Using sequence {sequence}')
    fc_size = 4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, use_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-5, weight_decay=1e-4)

    

    device_ids = [cuda_main_id, cuda_main_id+1]
    save_path = f'/nfs/home/khom/test_projects/CNNTraining/models/experiment_model_0.pth'
    data_path = '/nfs/home/khom/data210-2.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=32,
                      save_path=save_path, use_features=use_features,
                      device=device, parallel_device_ids=device_ids,
                      preload=preload)

    trainer.run_training(epochs=100)    

def main1():
    num_features = 6
    use_features = num_features > 0
    sequence = sequence5
    cuda_main_id = 0
    preload = None

    device = (
        f'cuda:{cuda_main_id}'
        if torch.cuda.is_available()
        # else 'mps'
        # if torch.backends.mps.is_available()
        else 'cpu'
    )


    print(f'Using sequence {sequence}')
    fc_size = 4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    

    device_ids = [cuda_main_id]
    save_path = None
    data_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/alldata_vlen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=1,
                      save_path=save_path, use_features=use_features,
                      vlen_data=True, device=device, 
                      parallel_device_ids=device_ids, preload=preload)

    trainer.run_training(epochs=100, print_freq=200)    

def main2():
    num_features = 6
    use_features = num_features > 0
    sequence = sequence6
    cuda_main_id = 0
    preload = None

    device = (
        f'cuda:{cuda_main_id}'
        if torch.cuda.is_available()
        # else 'mps'
        # if torch.backends.mps.is_available()
        else 'cpu'
    )


    print(f'Using sequence {sequence}')
    fc_size = 4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    

    device_ids = [cuda_main_id]
    save_path = None
    data_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/alldata_flen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=32,
                      save_path=save_path, use_features=use_features,
                      vlen_data=False, device=device,
                      parallel_device_ids=device_ids, preload=preload)

    trainer.run_training(epochs=100, print_freq=25)    
if __name__ == '__main__':
    main2()