import os
import torch
import time
import numpy as np

import dataset
from util import Timer

from torch import nn, optim
from torch.nn import Conv2d, Linear, Dropout, ReLU, MaxPool2d, Flatten, Sequential, BatchNorm2d, AdaptiveAvgPool2d

from torch.utils.data import DataLoader
# from torchvision.transforms import ToTensor
from sklearn.model_selection import train_test_split





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

        AdaptiveAvgPool2d((6,6)),
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
    def __init__(self, fc_size, sequence, use_features=False):
        super().__init__()
        self.cnn_network, self.feat_network = sequence(fc_size, 3 if use_features else 0)
        self.use_features = use_features

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
                 use_features=False, 
                 save_path=None, preload=None):
        self.model = model
        self.loss_fn = loss_fn
        self.optimizer = optimizer

        self.batch_size = batch_size
        self.val_frac = val_frac
        self.device = device
        self.parallel_device_ids = parallel_device_ids
        self.use_features = use_features
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
        if preload:
            print(f'Loading saved weights from {preload}')
            self.load_model(preload)
        print('-------------------------------\n')

        tensor_transformer = lambda arr: torch.tensor(np.array(arr)).unsqueeze(-3)

        self.train_dataset = dataset.MRCImageDataset(
            mode='hdf5',
            hdf5_path=data_path,
            use_features=use_features,
            transform=tensor_transformer
        )

        self.val_dataset = dataset.MRCImageDataset(
            mode='hdf5',
            hdf5_path=data_path,
            use_features=use_features,
            transform=tensor_transformer
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

        self.train_dataset.select_subset(self.train_ind)
        self.val_dataset.select_subset(self.val_ind)

        train_collate_fn = self.train_dataset.make_collate_fn()
        val_collate_fn = self.val_dataset.make_collate_fn()

        self.train_loader = DataLoader(self.train_dataset, batch_size=batch_size, shuffle=True, collate_fn=train_collate_fn)
        self.val_loader = DataLoader(self.val_dataset, batch_size=batch_size, shuffle=True, collate_fn=val_collate_fn)

        print('Ready to train\n')

    def init_data_parallel(self, device_ids):
        self.model = nn.DataParallel(self.model, device_ids=device_ids).to(self.device)

    def train_loop(self):
        '''
        Trains the model for one epoch

        :param val_loader: a second data loader for validation data, which will be evaluated every
        100 batches.

        '''

        def predict_vlen(X, feat, y):
            a = ([self.model(
                torch.from_numpy(x).to(self.device, dtype=torch.float), 
                f.unsqueeze(0),
                ).squeeze() for x,f in zip(X, feat)])
            return sum([self.loss_fn(a[i], y[i].unsqueeze(-1)) for i in range(torch.numel(y))])


        size, n_batches, batch_size = len(self.train_loader.dataset), len(self.train_loader), self.train_loader.batch_size
        timer = Timer()

        for batch, (X, y, feat) in enumerate(self.train_loader):
            # print(X.shape, y.shape, feat.shape)
            self.model.train()
            
            y = y.to(self.device, dtype=torch.float)
            feat = feat.to(self.device, dtype=torch.float)

            if type(X) == list:
                loss = predict_vlen(X, feat, y)
            else:
                X = X.to(self.device, dtype=torch.float)
                pred = self.model(X, feat)
                loss = self.loss_fn(pred, y.unsqueeze(1))
            
            loss.backward()
            self.optimizer.step()
            self.optimizer.zero_grad()

            if (batch % 100 == 0 or batch == n_batches-1) and batch > 0:
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
            a = ([self.model(
                torch.from_numpy(x).to(self.device, dtype=torch.float), 
                f.unsqueeze(0),
                ).unsqueeze(-1) for x,f in zip(X, feat)])

            return sum([self.loss_fn(a[i], y[i]) for i in range(torch.numel(y))])

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
    
    def run_training(self, epochs=10):
        main_timer, loop_timer = Timer(), Timer()
        print(f'Beginning training for {epochs} epochs (from epoch {self.cur_epoch+1})...')
        
        for e in range(epochs):
            self.cur_epoch += 1
            print(f'Epoch {self.cur_epoch}\n-------------------------------')
            self.train_loop()

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
            self.train_ind = [i for i in range(26389) if i not in self.val_ind]
        else:
            self.train_ind = checkpoint['train_ind']




if __name__ == '__main__':

    use_features = True
    sequence = sequence7
    cuda_main_id = 0
    preload = '/nfs/home/khom/test_projects/CNNTraining/models/experiment_model_2.pth'

    device = (
        f'cuda:{cuda_main_id}'
        if torch.cuda.is_available()
        # else 'mps'
        # if torch.backends.mps.is_available()
        else 'cpu'
    )


    fc_size = 4608 #456 #12800
    model = MRCNetwork(fc_size, sequence, use_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    

    device_ids = [cuda_main_id, cuda_main_id+1]
    save_path = f'/nfs/home/khom/test_projects/CNNTraining/models/experiment_model_2_cont.pth'
    data_path = '/nfs/home/khom/data210-2.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, 
                      save_path=save_path, use_features=use_features,
                      device=device, parallel_device_ids=device_ids,
                      preload=preload)

    trainer.run_training(epochs=100)    

    # cuda_main_id = 0

    # device = (
    #     f'cuda:{cuda_main_id}'
    #     if torch.cuda.is_available()
    #     else 'mps'
    #     if torch.backends.mps.is_available()
    #     else 'cpu'
    # )
    # print(f'Using device: {device}\n\n')
    

    # train_dataset = dataset.MRCImageDataset(
    #     data_path='/nfs/home/khom/data.hdf5',
    #     mode='hdf5',
    #     transform=ToTensor()
    # )
    # val_dataset = dataset.MRCImageDataset(
    #     data_path='/nfs/home/khom/data.hdf5',
    #     mode='hdf5',
    #     transform=ToTensor()
    # )


    # val_frac = 0.10  # Fraction of the data to use as validation data 
    # batch_size = 32
    # indices = list(range(len(train_dataset)))
    # save_path = '/nfs/home/khom/test_projects/CNNTraining/models/base_model_1.pth'
    
    # train_ind, val_ind = train_test_split(indices, test_size=val_frac, shuffle=True)
    # train_ind.sort()
    # val_ind.sort()

    # train_dataset.select_subset(train_ind)
    # val_dataset.select_subset(val_ind)

    # train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    # val_loader = DataLoader(val_dataset, batch_size=batch_size)

    # # model = MRCNetwork().to(device)
    # model = nn.DataParallel(MRCNetwork(), device_ids=[cuda_main_id]).to(device)
    # loss_fn = nn.MSELoss()
    # optimizer = optim.Adam(model.parameters(), weight_decay=1e-5)

    # print('\nTRAINING OVERVIEW\n-------------------------------')
    # print('OPTIMIZER:\n', optimizer, '\n-------------------------------')
    # print('LOSS FUNCTION:\n', loss_fn, '\n-------------------------------')
    # print('MODEL ARCHITECTURE:\n', model, '\n-------------------------------')
    # print('\n')

    # epochs = 25
    # main_timer, loop_timer = Timer(), Timer()
    
    # for e in range(epochs):
    #     print(f'Epoch {e+1}\n-------------------------------')
    #     train_loop(model, loss_fn, optimizer, train_loader, val_loader=val_loader)
    #     torch.save(model.module.state_dict(), save_path)
    #     print(f'Saved to {save_path}')
    #     print(f'Took {loop_timer.get_elapsed(reset=True):.3f}s total\n-------------------------------\n')

    # print(f'Took {main_timer.get_elapsed():.4f} seconds')
    # print('Done!\n')
