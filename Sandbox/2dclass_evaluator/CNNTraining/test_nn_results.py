import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('TkAgg')

from matplotlib import pyplot as plt

from train import MRCNetwork, Sequences
from predict import DatasetPredictor, CryosparcPredictor, RelionPredictor
from dataset import MRCImageDataset
from util import unconvert_labels

'''
Some functions to test how well the model does on select data.

traindata_error() tests on a portion of the training data.
csparc_prediction() tests on a cryoSPARC job.
relion_prediction() tests on a RELION job.

Change the file paths to test on your own data!
'''

def traindata_error():
    num_features = 6
    use_features = (num_features > 0)
    model = MRCNetwork(None, Sequences.sequence8, num_features)
    save_path = 'final_model/final_model_cont.pth'
    ds = MRCImageDataset(
        hdf5_path='../ClassAvgLabeling/ProcessedData/csparc_data_flen.hdf5',
        use_features=use_features,
        feature_scale={'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
    )

    predictor = DatasetPredictor(model, save_path, device='cpu')

    idxs = list(range(len(ds)))[2710:2760]
    pred, true = predictor.predict_multiple(ds, idxs)

    print(pred)

    thresh = np.linspace(0, 1, 11)
    for i in range(len(thresh)-1):
        thresh_ind = np.where((thresh[i] <= true) & (true < thresh[i+1]))
        print(f'MSE [{thresh[i]:.2f}, {thresh[i+1]:.2f}): {np.mean((pred[thresh_ind]-true[thresh_ind])**2)}')



    print(f'MSE: {np.mean((pred-true)**2)}')

    plt.hist((pred - true))
    plt.show()

    # i = np.random.randint(len(ds))
    # pred_score, score = predictor.predict_single(ds, i)
    # print(f'Prediction for image {i}: \n\tTrue score: {score}\n\tPredicted score: {pred_score}')


def csparc_prediction():
    job_dir = '../J222/'
    feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
    num_features = 6
    use_features = (num_features > 0)
    fixed_len = 210

    model = MRCNetwork(None, Sequences.sequence8, num_features)
    save_path = 'final_model/final_model_cont.pth'
    predictor = CryosparcPredictor(model, save_path, device='cpu')

    pred = predictor.predict_single(job_dir, feature_scale=feature_scale, fixed_len=fixed_len)


    ds = MRCImageDataset(
        hdf5_path='../ClassAvgLabeling/ProcessedData/csparc_data_flen.hdf5',
        use_features=use_features,
        feature_scale=feature_scale,
    )

    imgs_true, labels, metadata_true = ds[list(range(2710,2760))]
    est_res = metadata_true[:,0].numpy()
    weights = ((est_res.min() / est_res) ** 2)

    labels_true = unconvert_labels(labels.to_numpy(), weights)
    
    print('Comparison of predicted vs true labels:')
    print(pd.DataFrame(data={'pred': pred.tolist(), 'true': labels_true.tolist()}))

def relion_prediction():
    mrcs_path = '../data/Abou5aoshahr/run_classes.mrcs'
    model_path = '../data/Abou5aoshahr/run_model.star'
    feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
    num_features = 6
    use_features = (num_features > 0)
    fixed_len = 210

    model = MRCNetwork(None, Sequences.sequence8, num_features)
    save_path = 'final_model/final_model_cont.pth'
    predictor = RelionPredictor(model, save_path, device='cpu')

    pred = predictor.predict_single(mrcs_path, model_path, recover_labels=True,
                                    feature_scale=feature_scale, fixed_len=fixed_len)

    ds = MRCImageDataset(
        hdf5_path='../ClassAvgLabeling/ProcessedData/relion_data_flen.hdf5',
        use_features=use_features,
        feature_scale=feature_scale,
    )

    imgs_true, labels, metadata_true = ds[list(range(100))]

    pd.set_option('display.max_rows', None)
    print(pd.DataFrame(data={'pred': pred, 'true': labels}))





if __name__ == '__main__':
    relion_prediction()
    # csparc_prediction()
    # traindata_error()