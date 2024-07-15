import os
import torch

import dataset
from util import Timer

from torch import nn, optim
from torch.nn import Conv2d, Linear, Dropout, ReLU, MaxPool2d, Flatten, Sequential, BatchNorm2d, AdaptiveAvgPool2d

from torch.utils.data import DataLoader
from sklearn.model_selection import train_test_split


'''
RELION 4.0's method for assign scores to class averages is:

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

New manual scoring methodology based on RELION's:

target = (5 - label)*0.2 + (weight*0.2)

Where weight is defined the same way, and label is the average manually assigned score 
from 1 to 5.

Both methodologies result in scores between 0 and 1.
'''

class Sequences:
    '''
    Contains various types of CNN architectures for experimentation and development.

    sequence8 is best suited for fixed length data, when the data is padded to 210x210 pixels.
    Not enough testing has been done to determine which sequence is best for variable length data,
    but either sequence8 or sequence5 could do well.

    Create an MRCNetwork with a given sequence: 
        network = MRCNetwork(fc_size, Sequences.sequence8, num_features)
    '''

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def sequence5(fc_size, num_features=0, dropout=0.25):
        '''
        Based on sequence 4, but designed for variable size data (must still be square) 
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

    @staticmethod
    def sequence6(fc_size, num_features=0, dropout=0.25):
        '''
        Based on sequence 4, but with batch normalization applied after each residual block

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

    @staticmethod
    def sequence7(fc_size, num_features=0, dropout=0.25):
        '''    
        Based on sequence 6, but with designed to be trained on padded variables

        Input image dimensions must be at least 31x31.
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

            AdaptiveAvgPool2d((6,6)),
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

    @staticmethod
    def sequence8(fc_size, num_features=0, dropout=0.25):
        '''    
        Based on sequence 7, but with no FC layers, and with batchnorm applied to
        each layer including inside residual blocks.
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
    One residual convolutional block, with a skip connection from its input to its output. Each
    block expects data in the format (N, C, H, W).
    '''

    def __init__(self, in_channels, out_channels, kernel_size, stride=1, downsample=False, batchnorm=False):
        '''
        :param in_channels (int):
            Number of channels in the input.
        :param out_channels (int):
            Number of channels to have in the output.
        :param kernel_size (int): 
            The size of the square convolutional kernel (filter).
        :param stride (int):
            Stride of the kernel.
        :param downsample (bool):
            Whether to downsample or not; should always be true if in_channels != out_channels. 
            (Should deprecate in the future)
        :param batchnorm (bool):
            Whether to apply batch normalization in the middle of the residual block. Only possible
            if batch size is greater than 1.
        '''

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
        '''
        As required by pyTorch.
        '''
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
    '''
    A deep convolutional neural network (CNN) for predicting scores of 2D averages.
    '''

    def __init__(self, fc_size, sequence, num_features):
        '''
        :param fc_size (int or None): 
            Size of the fully-connected dense layer. Not always required, depending on which
            sequence is used; can be left as None if not required.
        :param sequence (callable): 
            One of the sequences defined above in the Sequences class, which must return a 
            Sequential of convolutional layers, and a Sequential of fully-connected dense layers.
        :param num_feautres (int):
            Number of extra numerical features that will be appended to the fully-connected dense
            layers. 
        '''

        super().__init__()
        self.cnn_network, self.feat_network = sequence(fc_size, num_features)
        self.use_features = num_features > 0


    def forward(self, x, feat=None):
        '''
        As required by pyTorch.
        '''
        x = self.cnn_network(x)
        if self.use_features:    
            x = torch.cat([x, feat], dim=1)

        return self.feat_network(x)    


class Trainer:
    '''
    A class designed to allow users to easily and efficiently train a model.
    '''
    def __init__(self, model, loss_fn, optimizer, data_path, batch_size=32, val_frac=None, 
                 device='cpu', parallel_device_ids=None, use_features=False, vlen_data=False,
                 save_path=None, preload=None, verbose=True):
        '''
        :param model (MRCNetwork):
            The initialized model to train.
        :param loss_fn (torch.nn loss function) 
            The initialized loss function to minimize/maximize.
        :param optimizer (torch.optim optimizer)
            The optimizer, already initialized with the model's parameters.
        :param data_path (str):
            Path to the HDF5 file containing the training data, features, and labels.
        :param batch_size (int):
            Number of samples to be included in each mini-batch. Default is 32.
        :param val_frac (float or None):
            Fraction of data to be set aside as validation data. Must be between 0 and 1.
            Set to None to use all data as training data. Default is 0.
        :param device (str or torch.device):
            The name of the device to run the model on. Use 'cuda:0' to run on 1 GPU. Default
            is 'cpu'.
        :param parallel_device_ids (list of int, optional):
            List of all devices to train the model on in parallel, using DataParallel.
        :param use_features (bool):
            Whether or not extra features will be added after the convolutional layers. Default
            is False. 
        :param vlen_data (bool):
            Whether or not the image data will have different shapes (must still be square). 
            Default is False (fixed length data).
        :param save_path (str, optional):
            The path to a .pth file to save the model to. The save file can then be used to
            resume training later. The file will be created if it doesn't already exist.
        :param preload (str, optional):
            The path to the .pth file to load previously trained weights from. The file must
            already exist.
        :param verbose (bool):
            Whether to print model architecture, data overview, and updates during training. 
            Default is True. 
        '''

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
        self.verbose = verbose

        self.cur_epoch = 0

        if batch_size is not None and (not isinstance(batch_size, int) or batch_size <= 0):
            raise ValueError(f'batch size must be a positive integer! Got {batch_size}')
        if val_frac is not None and (not isinstance(val_frac, (int, float)) or (val_frac < 0 or val_frac >= 1)):
            raise ValueError(f'val_frac must be between [0,1) or None! Got {val_frac}')
        if preload is not None and not os.path.exists(preload):
            raise ValueError(f'invalid path for preload: {preload}')

        self.print('\nTRAINING OVERVIEW\n-------------------------------')
        self.print('OPTIMIZER:\n', optimizer, '\n-------------------------------') 
        self.print('LOSS FUNCTION:\n', loss_fn, '\n-------------------------------')
        self.print('MODEL ARCHITECTURE:\n', model, '\n-------------------------------')
        self.print(f'OTHER:')
        self.print(f'Training with batch size of {batch_size}')
        self.print(f'Running on device {device}')

        if val_frac:
            self.print(f'Split {val_frac*100.:.2f}% of data for validation data')
        if parallel_device_ids:
            self.print(f'Preparing to train in parallel: main device on {self.device}, all devices on {parallel_device_ids}')
            self.init_data_parallel(parallel_device_ids)
        if save_path:
            self.print(f'Will save model to {save_path}')
        else:
            self.print('WARNING: will not save the model to a file!')
        if preload:
            self.print(f'Loading saved weights from {preload}')
            self.load_model(preload)

        if vlen_data:
             self.print('Expecting variable sized data')
             tensor_transformer = lambda arr: arr[0].unsqueeze(0) # Use for variable size data
        else:
            self.print('Expecting fixed size data')
            tensor_transformer = lambda arr: arr.unsqueeze(-3) # Use for fixed size data

        self.print('-------------------------------\n')

        feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}

        self.train_dataset = dataset.MRCImageDataset(
            hdf5_path=data_path,
            use_features=use_features,
            feature_scale=feature_scale,
            verbose=verbose,
            transform=tensor_transformer       
        )

        self.val_dataset = dataset.MRCImageDataset(
            hdf5_path=data_path,
            use_features=use_features,
            feature_scale=feature_scale,
            verbose=verbose,
            transform=tensor_transformer,
        )

        if self.train_dataset.vlen_data != self.vlen_data or self.val_dataset.vlen_data != self.vlen_data:
            raise ValueError(f'data type mismatch. The dataset contains '+
                             f'{"variable" if self.train_dataset.vlen_data else "fixed"} length data, but' +
                             f'{"variable" if self.vlen_data else "fixed"} length data is expected.')


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
            self.print('Using previous training validation set')


        self.train_dataset.select_subset(self.train_ind)
        self.val_dataset.select_subset(self.val_ind)

        train_collate_fn = self.train_dataset.make_collate_fn()
        val_collate_fn = self.val_dataset.make_collate_fn()

        self.train_loader = DataLoader(self.train_dataset, batch_size=batch_size, shuffle=True, collate_fn=train_collate_fn)
        self.val_loader = DataLoader(self.val_dataset, batch_size=batch_size, shuffle=True, collate_fn=val_collate_fn)

        self.print('Ready to train\n')

    def init_data_parallel(self, device_ids):
        '''
        Create a DataParallel wrapper around the model to train on multiple GPUs

        :param device_ids (list of int):
            Integer IDs of the GPUs to use.
        '''

        self.model = nn.DataParallel(self.model, device_ids=device_ids).to(self.device)


    def run_training(self, epochs=10, print_freq=100):
        '''
        Train the model for the given number of epochs.

        :param epochs (int):
            The number of epochs to train for.
        :param print_freq (int):
            Every {print_freq} batches, print an update of the current training loss, time
            taken, and validation loss. Default is 100.

        :return None:
        '''

        main_timer, loop_timer = Timer(), Timer()
        self.print(f'Beginning training for {epochs} epochs (from epoch {self.cur_epoch+1})...')
        
        for _ in range(epochs):
            self.cur_epoch += 1
            self.print(f'Epoch {self.cur_epoch}\n-------------------------------')
            self.train_loop(print_freq=print_freq)

            if self.save_path:
                self.save_model(self.cur_epoch)
                self.print(f'Saved to {self.save_path}')
            self.print(f'Took {loop_timer.get_elapsed(reset=True):.3f}s total\n-------------------------------\n')

        self.print(f'Took {main_timer.get_elapsed():.4f} seconds')
        self.print('Done!\n')


    def train_loop(self, print_freq=100):
        '''
        Trains the model for one epoch, and may print useful information as it trains.

        :param print_freq (int):
            As specified in Trainer.run_training.
        
        :return None:
        '''

        def predict_vlen(X, feat, y):
            a = torch.Tensor([self.model(
                x.to(self.device, dtype=torch.float), 
                f.unsqueeze(0),
                ).squeeze() for x,f in zip(X, feat)]).to(self.device)
            
            loss = self.loss_fn(a, y)
            loss.requires_grad = True

            return loss
        
        size, n_batches, batch_size = len(self.train_loader.dataset), len(self.train_loader), self.train_loader.batch_size
        timer = Timer()

        for batch, (X, y, feat) in enumerate(self.train_loader):
            self.model.train()
            
            y = y.to(self.device, dtype=torch.float)
            feat = feat.to(self.device, dtype=torch.float)

            if self.vlen_data and len(X) > 1:
                loss = predict_vlen(X, feat, y)
            else:
                if self.vlen_data:
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
                self.print(f'Batch {batch+1:>3d}/{n_batches}, loss: {loss:>7f}  [{current:>5d}/{size:>5d}] ({elapsed:.3f}s)', end=' ')
                if self.val_frac:
                    val_loss = self.get_val_error()
                    self.print(f'val loss: {val_loss:>7f}', end='')
                self.print('')


    def get_val_error(self):
        '''
        Returns the mean loss for all samples in the validation dataset. This method assumes that
        there is a validation set (i.e., that val_frac is nonzero).

        :return (float):
            The mean validation loss.
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
                
                if self.vlen_data:
                    total_loss += predict_vlen(X, feat, y).item()
                else:
                    X = X.to(self.device, dtype=torch.float)
                    pred = self.model(X, feat)
                    total_loss += self.loss_fn(pred, y.unsqueeze(1)).item()
        
        return total_loss / n_batches
    

    def save_model(self, epoch, all_params=True):
        '''
        Save the model to a specified .pth file. Can either store all parameters to resume
        training later, or store only the model weights if you only need to predict later
        and training is finished. The model will be saved to `self.save_path`.

        :param epoch (int):
            The current epoch.
        :param all_params (bool):
            Whether to store all parameters (epoch, train/validation indices, model weights
            and optimizer weights), or only the model weights. Default is True.

        :return None:
        '''
        model_state_dict = self.model.module.state_dict() if self.parallel_device_ids is not None \
                            else self.model.state_dict()
        if all_params:
            torch.save({
                'epoch': epoch,
                'train_ind': self.train_ind,
                'val_ind': self.val_ind,
                'model_state_dict': model_state_dict,
                'optimizer_state_dict': self.optimizer.state_dict(),
            }, self.save_path)
        else:
            torch.save(model_state_dict, self.save_path)


    def load_model(self, model_path):
        '''
        Load a previously trained model to continue training. The saved model must have been saved
        with `Trainer.save_model` with `all_params=True`.

        :param model_path (str):
            Path to the saved .pth model.

        :return None:
        '''
        checkpoint = torch.load(model_path, map_location=torch.device(self.device))

        self.cur_epoch = checkpoint['epoch']
        self.val_ind = checkpoint['val_ind']
        self.train_ind = checkpoint['train_ind']

        if self.parallel_device_ids is not None:
            self.model.module.load_state_dict(checkpoint['model_state_dict'])
        else:
            self.model.load_state_dict(checkpoint['model_state_dict'])

        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

    def print(self, *s, end='\n'):
        '''
        Helper print function that only prints if verbose is true
        '''

        if self.verbose:
            print(*s, end=end)



def main_relion():
    num_features = 6
    use_features = num_features > 0
    sequence = Sequences.sequence8
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
    fc_size = None #4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    

    device_ids = [cuda_main_id, cuda_main_id+1]
    save_path = f'/nfs/home/khom/test_projects/CNNTraining/models/relion_model_0.pth'
    data_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/relion_data_flen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=32,
                      save_path=save_path, use_features=use_features, vlen_data=False,
                      device=device, parallel_device_ids=device_ids,
                      preload=preload)

    trainer.run_training(epochs=100, print_freq=50)       

def main_csparc_vlen():
    num_features = 6
    use_features = num_features > 0
    sequence = Sequences.sequence8
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
    fc_size = None #4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-5, weight_decay=1e-4)

    

    device_ids = [cuda_main_id]
    save_path = None
    data_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/alldata_vlen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=1,
                      save_path=save_path, use_features=use_features,
                      vlen_data=True, device=device, 
                      parallel_device_ids=device_ids, preload=preload)

    trainer.run_training(epochs=100, print_freq=200)    

def main_csparc_flen():
    num_features = 6
    use_features = num_features > 0
    sequence = Sequences.sequence8
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
    fc_size = None #4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    

    device_ids = [cuda_main_id]
    save_path = None #'/nfs/home/khom/test_projects/CNNTraining/models/sanitytest_flen.pth'
    data_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/alldata_flen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=32,
                      save_path=save_path, use_features=use_features,
                      vlen_data=False, device=device, parallel_device_ids=device_ids,
                      preload=preload, verbose=False)

    trainer.run_training(epochs=1, print_freq=25)    

def main_combined():
    num_features = 6
    use_features = num_features > 0
    sequence = Sequences.sequence8
    cuda_main_id = 0
    preload = '/nfs/home/khom/test_projects/CNNTraining/final_model/final_model.pth'

    device = (
        f'cuda:{cuda_main_id}'
        if torch.cuda.is_available()
        # else 'mps'
        # if torch.backends.mps.is_available()
        else 'cpu'
    )


    print(f'Using sequence {sequence}')
    fc_size = None #4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    

    device_ids = [cuda_main_id, cuda_main_id+1]
    save_path = '/nfs/home/khom/test_projects/CNNTraining/final_model/final_model_cont.pth'
    data_path = '/nfs/home/khom/test_projects/ClassAvgLabeling/ProcessedData/combined_data_flen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=32,
                      save_path=save_path, use_features=use_features, vlen_data=False,
                      device=device, parallel_device_ids=device_ids,
                      preload=preload)

    trainer.run_training(epochs=75, print_freq=75) 

if __name__ == '__main__':
    main_combined()
    