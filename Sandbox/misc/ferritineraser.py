#!/usr/bin/env python

import mrcfile
import numpy as np
import scipy.ndimage
import sys
import glob
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

# Gaussian filter sigma
sig = 7

# Threshold in standard deviations below the mean
nsig = 4

def process_individual_images(file_path, output_path):
    print(f"Starting: {os.path.basename(file_path)}")

    # Read MRC image and preserve header
    with mrcfile.open(file_path, permissive=True) as mrc:
        image = np.array(mrc.data, copy=True)
        voxel_size = mrc.voxel_size  # Preserve header information
        nx = mrc.header.nx
        ny = mrc.header.ny
        nz = mrc.header.nz

    # Apply Gaussian filter to the image
    filtered = scipy.ndimage.gaussian_filter(image, sigma=sig)

    # Calculate mean and standard deviation for the filtered image
    mean_value = np.mean(filtered)
    std_deviation = np.std(filtered)
    threshold = mean_value - nsig * std_deviation

    # Create a boolean array where True indicates pixels below the threshold
    boolarray = filtered < threshold

    # Label connected regions (blobs) in the boolean array
    boolarray_int = boolarray.astype(int)
    labeled_array, num_features = scipy.ndimage.label(boolarray_int)

    # Calculate the area (in pixels) of each blob
    blob_areas = np.array([np.sum(labeled_array == j) for j in range(1, num_features + 1)])

    # Replace pixels for blobs with specified areas
    image_mean = np.mean(image)
    features = 0
    for m in range(num_features):
        if 400 < blob_areas[m]:
            features += 1
            blob_mask = labeled_array == (m + 1)
            image[blob_mask] = image_mean

    print(f"{features} features replaced in {os.path.basename(file_path)}")
    print(f"Finished: {os.path.basename(file_path)}")

    # Save modified image with original voxel size and dimensions
    with mrcfile.new(output_path, overwrite=True) as mrc_processed:
        mrc_processed.set_data(image)
        mrc_processed.voxel_size = voxel_size  
        mrc_processed.header.nx = nx
        mrc_processed.header.ny = ny 
        mrc_processed.header.nz = nz

    return os.path.basename(file_path)

if __name__ == "__main__":
    # Example usage
    source_dir = sys.argv[1]
    output_dir = sys.argv[2]
    print("Starting")

    # Gather all .mrc files in source directory
    files = glob.glob(os.path.join(source_dir, '*.mrc'))
    tasks = [(f, os.path.join(output_dir, os.path.basename(f))) for f in files]

    completed = 0
    total = len(tasks)

    # Process images in parallel using all available CPUs
    with ProcessPoolExecutor() as executor:
        future_to_file = {executor.submit(process_individual_images, f, o): f for f, o in tasks}

        # Handle results as they complete
        for future in as_completed(future_to_file):
            filename = os.path.basename(future_to_file[future])
            try:
                result = future.result()
            except Exception as exc:
                print(f"{filename} generated an exception: {exc}")
            else:
                completed += 1
                print(f"Completed: {result} ({completed}/{total})")

    print("All files processed!")
