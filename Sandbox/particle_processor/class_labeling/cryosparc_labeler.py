# cryosparc_labeler.py (clean version for import)
import os
import glob
import shutil
from .train import MRCNetwork, Sequences
from .predict import CryosparcPredictor


def cryosparcpredict(input_dir, output_dir, weights_path):
    """
    Predict scores for CryoSPARC class averages and write result .star files.
    """
    feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
    num_features = 6
    fixed_len = 210

    model = MRCNetwork(None, Sequences.sequence8, num_features)
    predictor = CryosparcPredictor(model, weights_path, device='cpu')

    # Run prediction
    pred = predictor.predict_single(input_dir, feature_scale=feature_scale, fixed_len=fixed_len)

    # Prepare output directory
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, 'info.txt'), 'w') as f:
        f.write(f'Input cryoSPARC directory: {input_dir}')

    # Locate input MRC file
    mrc_files = glob.glob(os.path.join(input_dir, '*.mrc'))
    if len(mrc_files) != 1:
        raise RuntimeError(f"Expected one MRC file in {input_dir}, but found {len(mrc_files)}.")
    
    mrc_basename = os.path.basename(mrc_files[0])[:-4]  # remove '.mrc'

    # Copy MRC file into output
    mrc_out_path = os.path.join(output_dir, f'{mrc_basename}_classes.mrcs')
    shutil.copyfile(mrc_files[0], mrc_out_path)

    # Copy dummy STAR file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dummy_star_src = os.path.join(script_dir, 'dummy_star_4_display.star')
    dummy_star_out = os.path.join(output_dir, f'{mrc_basename}_data.star')
    shutil.copyfile(dummy_star_src, dummy_star_out)

    # Write model.star file with predicted scores
    model_star_path = os.path.join(output_dir, f'{mrc_basename}_model.star')
    with open(model_star_path, 'w') as f:
        f.write("data_model_classes\n\n")
        f.write("loop_\n_rlnReferenceImage #1\n_rlnClassPriorOffsetY #2\n")
        for idx, score in enumerate(pred.tolist(), start=1):
            f.write(f"{idx:05d}@{mrc_out_path} {score:.3f}\n")

    return model_star_path  # You can return this path for downstream processing