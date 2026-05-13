import os
import time
import torch
import numpy as np
from PIL import Image
from pathlib import Path
import pandas as pd
import boxnet_utils
from tqdm import tqdm
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split # Useful for later, but we'll use the full dataset for training error
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, classification_report


model = boxnet_utils.BoxnetPT("boxnet.pt")
if torch.cuda.is_available():
    print("Evaluating micrographs using GPU.")
    model.to("cuda")
else:
    print("Evaluating micrographs using CPU.")


def find_all_paths_with_ext(root_folder, exts=("png",)):
    """
    Recursively find all files in subfolders of `root_folder`
    that have extensions listed in `exts`.

    Args:
        root_folder (str): The main folder to search in.
        exts (tuple[str]): Tuple of allowed file extensions (without dots).

    Returns:
        dict: {label_name: [list of file paths]}
    """
    paths = {}
    exts = tuple(ext.lower().lstrip('.') for ext in exts)  # normalize

    for label in os.listdir(root_folder):
        label_path = os.path.join(root_folder, label)
        if os.path.isdir(label_path):
            file_paths = []
            for root, _, files in os.walk(label_path):
                for f in files:
                    if f.lower().endswith(tuple(f".{ext}" for ext in exts)):
                        file_paths.append(os.path.join(root, f))
            if file_paths:
                paths[label] = file_paths

    return paths

def radial_profile(power_spectrum):
    """Compute the radial average (frequency vs magnitude) of a 2D power spectrum."""
    y, x = np.indices(power_spectrum.shape)
    center = np.array([(x.max() - x.min()) / 2.0, (y.max() - y.min()) / 2.0])
    r = np.hypot(x - center[0], y - center[1])
    r = r.astype(np.int32)
    tbin = np.bincount(r.ravel(), power_spectrum.ravel())
    nr = np.bincount(r.ravel())
    radialprofile = tbin / np.maximum(nr, 1)
    return radialprofile


# Creat folders to store BoxNet ouputs
PATH = Path(r"Z:\cianfrocco-data\laiwei\micrograph_evaluator\micassess_k2_labeled_masks")
DIRT_PATH = PATH / "dirt_mask"
PARTICLE_PATH = PATH / "particle_mask"
BACKGROUND_PATH = PATH / "background_mask"

PATHS = [DIRT_PATH, PARTICLE_PATH, BACKGROUND_PATH]
for path in PATHS:
    path.mkdir(parents=True, exist_ok=True)
    print(f"Successfully created directory: {path}")

# Find all paths from the k2 dataset
data_directory = Path(f"Z:\cianfrocco-data\laiwei\micrograph_evaluator\micassess_k2_labeled")
paths_dic = find_all_paths_with_ext(data_directory)

for label in paths_dic:
    print(label, len(paths_dic[label]))

for path in PATHS:
    for label in list(paths_dic):
        new_path = path / label
        new_path.mkdir(parents=True, exist_ok=True)
        print(f"Successfully created directory: {new_path}")

# Use BoxNet to compute masks
BATCH_SIZE = 4
for key in paths_dic.keys():
    path_list = paths_dic.get(key)
    for start in tqdm(range(0, len(path_list), BATCH_SIZE), desc=f"Processing {key}"):
        end = min(len(path_list), start + BATCH_SIZE)
        path_list_batch = path_list[start:end]
        imgs = [np.array(Image.open(path)) for path in path_list_batch]
        batch = np.array(imgs)
        results = model(batch)
        for idx, path in enumerate(path_list_batch):
            file_name = Path(path).name
            scaled_results = (results * 255).astype(np.uint8)
            background_mask = Image.fromarray(scaled_results[idx,:,:,0], 'L')
            background_mask.save(BACKGROUND_PATH / key / file_name)
            particle_mask = Image.fromarray(scaled_results[idx, :, :, 1], 'L')
            particle_mask.save(PARTICLE_PATH / key / file_name)
            dirt_mask = Image.fromarray(scaled_results[idx, :, :, 2], 'L')
            dirt_mask.save(DIRT_PATH / key / file_name)