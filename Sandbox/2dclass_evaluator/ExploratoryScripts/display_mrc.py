import mrcfile
import sys
import numpy as np
import matplotlib as mpl

from matplotlib import pyplot as plt, patches

mpl.use('TkAgg')

'''
This file contains several methods to display images from MRC or MRCS files, as well as the header
'''

# mrc_path = '/nfs/home/czerio/cryosparc/CS-polqhel-50ss-6mh-dna/J79/J79_020_class_averages.mrc'
# mrc_path = '/nfs/home/khom/test_projects/ExampleData/J73/Class2D/job001/run_it025_classes.mrcs'
# mrc_path = '/nfs/home/glander/KaiC/Class2D/job001/run_it025_classes.mrcs'
# mrc_path = '/nfs/home/czerio/cryosparc/CS-polqhel-5phos-24-16-dna/S3/extract/blob/300/23apr28g_00003sq_v01_00007hl1250_00006ed36-a-DW_patch_aligned_doseweighted_particles.mrc'
mrc_path = '/nfs/home/khom/data/EegieQuee9pu/run_classes.mrcs'

def print_header(mrc_path):
    header = mrcfile.open(mrc_path).header

    j = 0
    print(header.tolist()[0])

    for i, val in enumerate(header.tolist()):
        if type(val) == tuple or type(val) == np.ndarray:
            print(f'{j+1}-{j+len(val)} := {val}')
            j += len(val)
        else:
            print(f'{j+1} := {val}')
            j += 1
    print('\n')

def display_many_images(mrc_path):

    mrc_data = mrcfile.open(mrc_path).data
    num_subplots = 20 # Max number of subplots per plot
    rows, cols = 4, 5
    num_plots = int(np.ceil(mrc_data.shape[0] / num_subplots))

    print(f'Data shape: {mrc_data.shape}')
    
    for d in range(num_plots):
        fig, axes = plt.subplots(rows, cols)
        fig.suptitle(f'Images {num_subplots*d+1} to {num_subplots*(d+1)}')
        fig.subplots_adjust(hspace=1)
        
        # Display the RELION results, colored by the label given by Cianfrocco
        for i in range(num_subplots*d, min(num_subplots*(d+1), mrc_data.shape[0])):
            # Display each 2D class avg in a grid
            img = normalize(mrc_data[i])
            ax = axes[(i%num_subplots)//cols, (i%num_subplots)%cols]
            
            ax.axis('off')
            ax.imshow(img, cmap='gray')

    plt.show()

def display_all_images(mrc_path):
    '''
    Show all images in matplotlib
    '''
    m = mrcfile.open(mrc_path).data
    cols = 12
    rows = int(np.ceil(m.shape[0] / cols))
    
    fig, axes = plt.subplots(rows, cols)

    for i in range(m.shape[0]):
        ax = axes[i//cols, i%cols]
        ax.axis('off')
        ax.imshow(normalize(m[i]), cmap='gray')

    plt.show()

def display_all_images_box(mrc_path):
    mrc_data = mrcfile.open(mrc_path).data
    num_subplots = 20 # Max number of subplots per plot
    rows, cols = 4, 5
    num_plots = int(np.ceil(mrc_data.shape[0] / num_subplots))

    print(f'Data shape: {mrc_data.shape}')
    
    for d in range(num_plots):
        fig, axes = plt.subplots(rows, cols)
        fig.suptitle(f'Images {num_subplots*d+1} to {num_subplots*(d+1)}')
        fig.subplots_adjust(hspace=1)
        
        # Display the RELION results, colored by the label given by Cianfrocco
        for i in range(num_subplots*d, min(num_subplots*(d+1), mrc_data.shape[0])):
            # Display each 2D class avg in a grid
            img = normalize(mrc_data[i])
            ax = axes[(i%num_subplots)//cols, (i%num_subplots)%cols]
            ax.axis('off')
            ax.imshow(img, cmap='gray')

            img_width = img.shape[0]
            mask = patches.Circle((img_width/2, img_width/2), img_width/2, linewidth=1, edgecolor='r', facecolor='none')
            ax.add_patch(mask)
    
    plt.show()

def display_one_image(mrc_path, idx=0):
    mrc_data = mrcfile.open(mrc_path).data
    img = normalize(mrc_data[idx])

    fig, ax = plt.subplots()

    ax.axis('off')
    ax.imshow(img, cmap='gray')

    img_width = img.shape[0]
    mask = patches.Circle((img_width/2, img_width/2), img_width/2, linewidth=1, edgecolor='r', facecolor='none')
    ax.add_patch(mask)

    plt.show()

def normalize(arr):
    return (arr - arr.min()) / (arr.max() - arr.min())


display_many_images(mrc_path)
# print_header(mrc_path)
# display_all_images_box(mrc_path, box_percent=0.85)

# display_one_image(mrc_path)