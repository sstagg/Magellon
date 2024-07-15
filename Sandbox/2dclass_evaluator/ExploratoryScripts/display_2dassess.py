# import mrcfile
import numpy as np
import os
import matplotlib as mpl


from matplotlib import pyplot as plt
from PIL import Image

mpl.use('TkAgg')

# Names of the directories containing the corresponding label, in which each 2D class average is assigned
label_folders = ['Clip', 'Edge', 'Good', 'Noise']

# Path to directory containing directories label directories
imgs_pathname = '/nfs/home/khom/test_projects/Class2D/job001/2DAssess/'

cols = 5


for label in label_folders:
    labeled_img_path = os.path.join(imgs_pathname, label)
    img_names = os.listdir(labeled_img_path)

    rows = int(np.ceil(len(img_names) / cols)) + 1
    fig, axes = plt.subplots(rows, cols)
    fig.suptitle(label)

    for i, img_name in enumerate(img_names):
        img = Image.open(os.path.join(labeled_img_path, img_name))
        axes[i//cols, i%cols].axis('off')
        axes[i//cols, i%cols].imshow(img, cmap='gray', vmin=np.min(img), vmax=np.max(img))

plt.show()