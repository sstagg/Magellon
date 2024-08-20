#!/usr/bin/env python

import mrcfile
import numpy as np
import scipy.ndimage
import sys
import glob
import os
from matplotlib import pyplot

sig = 7
nsig = 4

def process_individual_images(file_path, output_path):
    
    print (f"Processing {file_path}")

    with mrcfile.open(file_path, permissive=True) as mrc:
        image = np.array(mrc.data, copy=True)
        voxel_size = mrc.voxel_size  # Preserve header information
        nx=mrc.header.nx
        ny=mrc.header.ny
        nz=mrc.header.nz

    # Apply Gaussian filter to the image
    filtered = scipy.ndimage.gaussian_filter(image, sigma=sig)

    # Calculate mean and standard deviation for the filtered image
    mean_value = np.mean(filtered)
    std_deviation = np.std(filtered)
    threshold = mean_value - nsig * std_deviation

    # Create a boolean array where True indicates pixels above the threshold
    boolarray = filtered < threshold

    # Label connected regions (blobs) in the boolean array
    #labeled_array, num_features = scipy.ndimage.label(boolarray)
    boolarray_int=boolarray.astype(int)
    labeled_array, num_features = scipy.ndimage.label(boolarray_int)

    # Calculate the area (in pixels) of each blob
    blob_areas = np.array([np.sum(labeled_array == j) for j in range(1, num_features + 1)])

    # Replace pixels for blobs with specified areas
    image_mean = np.mean(image)
    features=0
    for m in range(num_features):
        if 400 < blob_areas[m]:
            features +=1
            blob_mask = labeled_array == (m + 1)
            image[blob_mask] = image_mean
    print (f"{features} features replaced")
    print (f"Writing to {output_path}")

    with mrcfile.new(output_path, overwrite=True) as mrc_processed:
        mrc_processed.set_data(image)
        mrc_processed.voxel_size = voxel_size  
        mrc_processed.header.nx = nx
        mrc_processed.header.ny = ny 
        mrc_processed.header.nz = nz
 
    return

if __name__ == "__main__":
    # Example usage
    source_dir = sys.argv[1]
    output_dir = sys.argv[2]
    print("Starting")
    
    files=glob.glob(os.path.join(source_dir,'*.mrc'))
    
    for f in files:
        filename=os.path.split(f)[-1]
        file_path=f
        out_path=os.path.join(output_dir,filename)
        process_individual_images(file_path, out_path)
    print ("Done!")

