import numpy
import numpy as np
from scipy import stats
from matplotlib import pyplot
import mrcfile as mrc
import sys

#import cv2

def calc_mass(avg=None, apix=None, scalefactor=26.455, usebackground=True):
    particlemask, backgroundmask = make_masks_by_statistics(nstd=3, img=avg)
    backgroundmean = numpy.average(avg[backgroundmask])

    if usebackground is True:
        avg = avg - backgroundmean
    else:
        mean, std = get_edge_stats_for_box(avg, 3)
        avg = avg - mean
    pixsum = numpy.sum(avg[particlemask])
    angsum = pixsum * apix ** 2
    estmass = angsum * scalefactor
    return estmass

def calc_mass_stats_for_stack(avgfilename):
    stackheader=mrc.open(avgfilename, header_only=True)
    apix=stackheader.voxel_size
    apix=apix.tolist()
    apix=apix[0]
    stackarray=mrc.read(avgfilename)

    masses=[]
    for avg in stackarray:
        masses.append(calc_mass(avg=avg, apix=apix, usebackground=True))

    masses=numpy.array(masses)
    mean=masses.mean()
    median=numpy.median(masses)
    mode=stats.mode(masses, keepdims=False)
    mode=mode.mode
    print (f'mean {mean}, median {median}, mode {mode}')
    statlist=[]
    for mass in masses:
        statdict={}
        statdict['dmean']=abs(mass-mean)
        statdict['dmedian']=abs(mass-median)
        statdict['dmode']=abs(mass-mode)
        statdict['mass']=mass
        statlist.append(statdict)
    return statlist


def make_masks_by_statistics(nstd=3, img=None):
    mean, std = get_edge_stats_for_box(img, 3) # use stats for 3 pixels inside edge to avoid edge effects
    particlemask = img > (mean + std * nstd)
    backgroundmask = numpy.invert(particlemask)
    return particlemask, backgroundmask

def get_edge_stats_for_box(img, clippix):
    edgepix = img[clippix:-clippix, clippix]
    edgepix = numpy.append(edgepix, img[clippix:-clippix, -clippix])
    edgepix = numpy.append(edgepix, img[clippix, clippix:-clippix])
    edgepix = numpy.append(edgepix, img[-clippix, clippix:-clippix])
    mean = edgepix.mean()
    std = edgepix.std()
    return mean, std

# def mask_otsu_thresholding(image):
#     """
#     Perform Otsu Thresholding.
#
#     Returns:
#         bool mask
#     """
#     # Convert the floating-point image to a suitable format (e.g., 8-bit)
#     normalized_image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
#
#     # Perform light Gaussian filter
#     filtered = cv2.GaussianBlur(normalized_image, (5,5),0 )
#
#     # Apply Otsu's thresholding on the converted image
#     threshvalue, thresholded = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
#
#     particlemask = thresholded > 0
#     backgroundmask = numpy.invert(boolarray)
#
#     return particlemask, backgroundmask

def create_montage_with_numbers(images, numbers=None, ncols=5, padding=4):
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
        if numbers is None:
            ax.text(col * (width + padding) + padding, (row + 1) * (height + padding) - padding, str(i), color='red', ha='left', va='bottom')
        else:
            ax.text(col * (width + padding) + padding, (row + 1) * (height + padding) - padding, str(numbers[i]), color='red', ha='left', va='bottom')

    return fig

if __name__ == '__main__':
    stackstats=calc_mass_stats_for_stack(sys.argv[1])
    for stat in stackstats:
        print (stat)
