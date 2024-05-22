#!/usr/bin/env python
import numpy as np
import mass_est_lib as mel
import os
import argparse
import sys
import mrcfile as mrc
from matplotlib import pyplot



def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stackpath", dest="stackpath", type=str, help="Path to stack")
    parser.add_argument("--writemasked", dest="writemasked", type=str, default=None, help="Write out a masked stack with the given name, e.g. '--writemasked out.mrc'. Default is no output")
    parser.add_argument("--nomask", dest="nomask", action='store_true', default=False, help="Don't apply the mask")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()

    return args

def create_montage_with_numbers(images, ncols=5, padding=4):
    """
    Create a montage of images with overlayed image numbers and padding between images from a numpy array of 2D images.

    Parameters:
        images (numpy.ndarray): A 3D numpy array of shape (num_images, height, width).
        ncols (int): Number of columns in the montage grid.
        padding (int): Padding between images in pixels.

    Returns:
        matplotlib.figure.Figure: The matplotlib figure object.
    """
    n_images, height, width = images.shape
    nrows = int(np.ceil(n_images / ncols))

    montage_height = nrows * height + (nrows - 1) * padding
    montage_width = ncols * width + (ncols - 1) * padding

    montage = np.zeros((montage_height, montage_width))
 
    for i in range(n_images):
        row = i // ncols
        col = i % ncols
        start_row = row * (height + padding)
        start_col = col * (width + padding)
        end_row = start_row + height
        end_col = start_col + width
        montage[start_row:end_row, start_col:end_col] = images[i]

    fig, ax = pyplot.subplots()
    ax.imshow(montage, cmap='gray')
    ax.axis('off')

    for i in range(n_images):
        row = i // ncols
        col = i % ncols
        ax.text(col * (width + padding) + padding, (row + 1) * (height + padding) - padding, str(i), color='red', ha='left', va='bottom')

    return fig


if __name__ == '__main__':

    args = parseArgs()
    stackheader=mrc.open(args.stackpath, header_only=True)
    apix=stackheader.voxel_size
    apix=apix.tolist()
    apix=apix[0]
    stackarray=mrc.read(args.stackpath)
    if args.nomask is not True:
        for avg in stackarray:
            particlemask, backgroundmask=mel.make_masks_by_statistics(img=avg)
            mean, std=mel.get_edge_stats_for_box(avg,clippix=3)
            avg[backgroundmask]=mean
        if args.writemasked is not None:
                mrc.write(args.writemasked, stackarray, overwrite=True)
    fig = create_montage_with_numbers(stackarray)
    pyplot.show()
