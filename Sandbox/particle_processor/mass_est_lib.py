import numpy
import numpy as np
from scipy import stats
from matplotlib import pyplot
import mrcfile as mrc
import sys
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

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

def find_optimal_clusters(masses, max_k=10, tolerance=1e-3):
    """
    Determine the optimal number of clusters using K-Means while handling single-cluster cases.

    Parameters:
        masses (list or numpy.ndarray): 1D array of mass estimates.
        max_k (int): Maximum number of clusters to evaluate.
        tolerance (float): Minimum variation in mass values to consider multiple clusters.

    Returns:
        tuple: (best_k, cluster_labels)
    """
    masses = np.array(masses).reshape(-1, 1)
    
    # Handle case where all values are nearly identical
    if np.std(masses) < tolerance:
        return 1, np.zeros(len(masses), dtype=int)  # Return single cluster

    best_k = 1
    best_labels = np.zeros(len(masses), dtype=int)  # Default: all in one cluster
    best_score = -1

    K_range = range(2, min(len(masses), max_k))

    for k in K_range:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(masses)

        # Ensure at least 2 meaningful clusters exist
        if len(np.unique(labels)) < 2:
            continue  # Skip if clustering isn't valid

        sil_score = silhouette_score(masses, labels)

        if sil_score > best_score:
            best_score = sil_score
            best_k = k
            best_labels = labels

    return best_k, best_labels


import numpy as np
import matplotlib.pyplot as plt

def create_montage(images, numbers=None, clusters=None, ncols=5, padding=4, image_size_in_inches=1.5):
    """
    Create a montage of images with overlayed image numbers (bottom center) and cluster ID (top-left).

    Parameters:
        images (numpy.ndarray): A 3D numpy array of shape (num_images, height, width).
        numbers (list or None): List of mass values to display.
        clusters (list or None): List of cluster labels to display.
        ncols (int): Number of columns in the montage grid.
        padding (int): Padding between images in pixels.
        image_size_in_inches (float): Fixed size per image in inches.

    Returns:
        matplotlib.figure.Figure: The matplotlib figure object.
    """
    n_images, height, width = images.shape
    nrows = int(np.ceil(n_images / ncols))

    # Calculate exact figure size to prevent extra space
    fig_width = width * ncols / 100  # Scale down figure size
    fig_height = height * nrows / 100  # Scale down figure size

    # Create figure with exact dimensions
    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=100)

    # Remove all figure background space
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_position([0, 0, 1, 1])
    fig.patch.set_visible(False)  # Ensures no background

    # Dynamically adjust text size based on image height
    text_size = max(height // 12, 6)

    montage_height = nrows * height + (nrows - 1) * padding
    montage_width = ncols * width + (ncols - 1) * padding
    montage = np.zeros((montage_height, montage_width))

    # Generate distinct colors for clusters
    unique_clusters = np.unique(clusters) if clusters is not None else []
    cluster_colors = plt.cm.get_cmap('tab10', len(unique_clusters))

    for i in range(n_images):
        row = i // ncols
        col = i % ncols
        start_row = row * (height + padding)
        start_col = col * (width + padding)
        end_row = start_row + height
        end_col = start_col + width

        # Place image in the montage
        montage[start_row:end_row, start_col:end_col] = images[i]

        # Assign colors based on cluster
        if clusters is not None:
            cluster_idx = np.where(unique_clusters == clusters[i])[0][0]  # Find cluster index
            cluster_color = cluster_colors(cluster_idx)  # Get color from colormap
        else:
            cluster_color = 'gray'

        # Add cluster number in the top-left corner
        ax.text(start_col + padding, start_row + padding,
                f"{clusters[i]}", color='white', ha='left', va='top',
                fontsize=text_size, fontweight='bold',
                bbox=dict(facecolor=cluster_color, alpha=1, edgecolor='none'))

        # Add mass number centered at the bottom
        if numbers is not None:
            ax.text(start_col + width / 2, end_row - padding,
                    f"{numbers[i]}", color='red', ha='center', va='bottom',
                    fontsize=text_size, fontweight='bold')

    # Display the montage with all padding removed
    ax.imshow(montage, cmap='gray')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_frame_on(False)
    ax.axis('off')

    plt.tight_layout(pad=0)  # Ensure tight layout with zero padding

    return fig




if __name__ == '__main__':
    stackstats=calc_mass_stats_for_stack(sys.argv[1])
    for stat in stackstats:
        print (stat)