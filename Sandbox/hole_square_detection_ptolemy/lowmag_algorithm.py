#!/usr/bin/env python
"""
Low-Mag Ptolemy Algorithm Script
Processes low-magnitude MRC images to detect and score squares.

Usage: python lowmag_algorithm.py <path_to_mrc_file>

Outputs JSON to stdout with detected squares, their centers, areas, brightness, and scores.
"""

import sys
import os
import json
import numpy as np
import torch

# Add the current directory to path to import ptolemy (assuming ptolemy folder is in the same directory)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from ptolemy.images import load_mrc, Exposure
    import ptolemy.algorithms as algorithms
    import ptolemy.models as models
except ImportError as e:
    print(f"Error importing ptolemy modules: {e}", file=sys.stderr)
    print("Make sure the ptolemy folder is in the same directory as this script.", file=sys.stderr)
    sys.exit(1)

def process_lowmag(mrc_path):
    """
    Process a low-magnitude MRC image and return results as a dictionary.
    """
    # Load the image
    try:
        image = load_mrc(mrc_path)
    except Exception as e:
        raise ValueError(f"Failed to load MRC file {mrc_path}: {e}")

    # Create Exposure object
    ex = Exposure(image)

    # Segment the image
    segmenter = algorithms.PMM_Segmenter()
    ex.make_mask(segmenter)

    # Process the mask
    processor = algorithms.LowMag_Process_Mask()
    ex.process_mask(processor)

    # Get crops
    cropper = algorithms.LowMag_Process_Crops()
    ex.get_crops(cropper)

    # Load and apply the model
    script_dir = os.path.dirname(os.path.abspath(__file__))
    weights_path = os.path.join(script_dir, 'weights', '211215_lowmag_64x5_defaultadam_tightw_e2.torchmodel')

    if not os.path.exists(weights_path):
        raise FileNotFoundError(f"Weights file not found: {weights_path}")

    model = models.LowMag_64x5_2ep()
    model.load_state_dict(torch.load(weights_path, map_location='cpu'))
    wrapper = models.Wrapper(model)
    ex.score_crops(wrapper, final=False)

    # Prepare results
    results = []
    vertices = [box.as_matrix_y().tolist() for box in ex.crops.boxes]
    areas = [box.area() for box in ex.crops.boxes]
    centers = np.round(ex.crops.center_coords.as_matrix_y()).astype(int).tolist()
    intensities = ex.mean_intensities
    scores = ex.crops.scores

    # Sort by score descending
    order = np.argsort(scores)[::-1]

    for i in order:
        result = {
            'vertices': vertices[i],
            'center': centers[i],
            'area': float(areas[i]),
            'brightness': float(intensities[i]),
            'score': float(scores[i])
        }
        results.append(result)

    return results

def main():
    if len(sys.argv) != 2:
        print("Usage: python lowmag_algorithm.py <path_to_mrc_file>", file=sys.stderr)
        sys.exit(1)

    mrc_path = sys.argv[1]

    if not os.path.exists(mrc_path):
        print(f"Error: MRC file not found: {mrc_path}", file=sys.stderr)
        sys.exit(1)

    try:
        results = process_lowmag(mrc_path)
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Error processing image: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()