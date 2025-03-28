## What is in this repository: 

### ClassAvgLabeling

This folder contains code and directions to help you convert your cryoSPARC class average data into a format that can be used to further train the model, if you so desire. You will need to also assign manual labels to your images, which may be time-consuming. 

It has its own `README` and other Markdown files that you should read for more information.

`extract_mrc.py` will take your raw cryoSPARC 2D class average jobs and place them neatly into two folders: `images` (containing JPGs) and `metadata` (.npy files containing the necessary metadata).

`tkteach.py` provides a GUI to let you manually label your images on a letter grade scale (Best, Decent, Acceptable, Bad, Unusable). Multiple people can (and should) label the same set of images, by running `tkteach.py` and passing in their email address as a unique identifier; in this case, labels will be averaged for each image. **IMAGES *MUST* BE LABELED IN ORDER TO BE USED TO TRAIN THE MODEL!**

### CNNTraining

This folder contains Python files that will construct a dataset (from your extracted cryoSPARC data, from RELION data stored in EMPIAR-10812, or both), and train a model on that data.

**IMPORTANT: When training on cryoSPARC data, the model converts the categories in the range [1,5] to the range [0,1], weighted by each image's estimated resolution. When using the *CryosparcPredictor*, make sure to set `recover_labels=True` to get predicted labels in the range [1,5]!**

`dataset.py` can preprocess your cryoSPARC data or downloaded RELION data, into a single HDF5 file which can then be used to train the model. 

`train.py` contains everything you need to train (or continue training) a model- `MRCNetwork` can take in an architecture of choice from `Sequences`, and then the `Trainer` can train it for a specified number of epochs.

`predict.py` contains classes to help you take a trained model (as a .pth file) and make predictions given a cryoSPARC or RELION job.

`util.py` contains a menagerie of helper classes and functions that the other files use for convenience.

## Full workflow: data > preprocessing > model training > model evalulation

Below is an example of how you can assemble your data, preprocess it, assemble a model, train the model, and evaulate the model.

1. **Choose your data**: If you want to include your own cryoSPARC data, go read `ClassAvgLabeling`'s `README` and corresponding Markdown files for more details. Let's say that you have some cryoSPARC data, in addition to EMPIAR-10812 used to train RELION's *Class Ranker*.
    - First use `extract_mrc.py` to choose which cryoSPARC jobs you want to include. The program outputs an `images` and `metadata` folders. Let's assume that your cryoSPARC data is then extracted into the following folder structure:
        ```
        my_csparc_data/
        +-- images/
        +-- metadata/
        ```
        Then, we need to label all of our images with `tkteach.py`. See `TkTeach.md` in `ClassAvgLabeling` for more information on how to do this. Let's assume that 3 people label the images in `my_csparc_data`: Alice, Bob, and Charlie, which produces the following SqlLite3 database files:
        ```
        storage_alice@gmail.com.db
        storage_bob@gmail.com.db
        storage_charlie@gmail.com.db
        ```

    - Next, download RELION's data from EMPIAR-10812 (which is already labeled), which will be represented as the following folder structure:
        ```
        data/
        +-- Abou5aoshahr/
        +-- aD9Ahno3Yaey/
        ...
        +-- Zoh4ohseg7pe/
        ```
2. **Preprocess the data into HDF5 files**: HDF5 files are used to feed data directly into the model, so we will need to change the data stored in folders (created in Step 1) into HDF5 files.
    - To preprocess your cryoSPARC data, use the `JPGPreprocessor` class.:
        ```python
        from dataset import JPGPreprocessor
        JPGPreprocessor.execute(
            jpg_dir='my_csparc_data/images/',
            metadata_dir='my_csparc_data/metadata/',
            label_paths=['storage_alice@gmail.com.db', 
                        'storage_bob@gmail.com.db',
                        'storage_charlie@gmail.com.db'],
            hdf5_path='ProcessedData/csparc_data.hdf5'
        ).execute(fixed_len=210)
        ```
        This will combine the images, labels, and metadata into a single HDF5 called `csparc_data.hdf5` in the folder `ProcessedData`, while zero-padding or downacaling images to a fixed size of 210x210.

    - To preprocess RELION 4.0's EMPIAR-10812 data that they used to train their own *Class Ranker*, use the `MRCPreprocessor` class:
        ```python
        from dataset import MRCPreprocessor
        MRCPreprocessor.execute(
            data_dir='empiar-10812/data/',
            hdf5_path='ProcessedData/relion_data.hdf5'
        ).execute(fixed_len=210)
        
        ```
        Again, this combines all images, labels, and metadata into a single HDF5 called `relion_data.hdf5` in `ProcessedData`, again zero-padding or downscaling images to a fixed size of 210x210.
    - To combine the two datasets into one:
        ```python
        from util import combine_hdf5
        dataset_paths = ['ProcessedData/csparc_data.hdf5', 'ProcessedData/relion_data.hdf5']
        combine_hdf5(dataset_paths, 'ProcessedData/combined_data_flen.hdf5', fixed_len=210)
        ```
        This creates our final dataset called `combined_data_flen.hdf5`. This file will then be used as the training data.
3. **Create the model and train it**: We first create a `MRCNetwork`, and pass it into a `Trainer` to be trained, along with other variables to modify the training process. Here's how I trained the final model:
    ```python
    from torch import nn, optim
    from train import Sequences, MRCNetwork, Trainer
  
    num_features = 6
    use_features = num_features > 0
    sequence = Sequences.sequence8
    cuda_main_id = 0
    device = (f'cuda:{cuda_main_id}' if torch.cuda.is_available() else 'cpu')

    model = MRCNetwork(None, sequence, num_features).to(device)
    loss_fn = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)

    save_path = 'final_model.pth'
    data_path = 'ProcessedData/combined_data_flen.hdf5'

    trainer = Trainer(model, loss_fn, optimizer, data_path,
                      val_frac=0.1, batch_size=32,
                      save_path=save_path, use_features=use_features, vlen_data=False,
                      device=device)

    trainer.run_training(epochs=75, print_freq=75) 
    ```
    This assembles a `MRCNetwork` model using the architecture provided by `Sequences.sequence8`, and trains it for 75 epochs on our combined data from **Step 2**, with a mini batch size of 32 and using 10% of the data as validation data. It uses one GPU ('cuda:0') and saves the model to `final_model.pth`.

4. **Use the model to make predictions on new data**: We can use code from `predict.py` to use our model saved in `final_model.pth` to automatically assess new data, whether it's from cryoSPARC or RELION!
    - If you have a cryoSPARC job that created some 2D averages, and you want to grade them, use the `CryosparcPredictor`. Let's say you have job `J222` in project `P001`. We can do the following:
        ```python
        from predict import CryosparcPredictor
        from train import Sequences, MRCNetwork
        job_dir = 'P001/J222/'
        # feature_scale is very important! Please keep it as is shown here
        feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
        num_features = 6
        use_features = (num_features > 0)
        fixed_len = 210

        save_path = 'final_model.pth'
        predictor = CryosparcPredictor(model, save_path, device='cuda:0')

        pred = predictor.predict_single(job_dir, recover_labels=True, feature_scale=feature_scale, fixed_len=fixed_len)

        print('Here are the predicted scores, in order!')
        print(pred.tolist())
        ```
        This will return predicted scores from 1 to 5, according to the categories: 1 or "Best"; 2 or "Decent"; 3 or "Acceptable"; 4 or "Bad"; 5 or "Unusable". *Remember to set recover_labels=True to get scores in the range [1,5] rather than [0,1]*.
    - If you have a RELION job that created some 2D averages, we can grade them with a similar process using `RelionPredictor`. Let's say you have `job001`. We can do the following:
        ```python
        mrcs_path = 'Class2D/job001/run_it025_classes.mrcs'
        model_path = 'Class2D/job001/run_it025_model.star'
        # feature_scale is very important! Please keep it as is shown here
        feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
        num_features = 6
        use_features = (num_features > 0)
        fixed_len = 210

        model = MRCNetwork(None, Sequences.sequence8, num_features)
        save_path = 'final_model.pth'
        predictor = RelionPredictor(model, save_path, device='cpu')

        pred = predictor.predict_single(mrcs_path, model_path, feature_scale=feature_scale, fixed_len=fixed_len)

        print('Here are the predicted scores, in order!')
        print(pred.tolist())
        ``` 

5. **Integrate into a GUI?**: The model can only be called from the command line at the moment, but the hope is that this can be become a part of Magellon with a well-functioning GUI that allows anyone to use it.



    
