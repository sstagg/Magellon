import pandas as pd
import numpy as np
import starfile
import mrcfile
import os
import shutil
import matplotlib as mpl

from matplotlib import pyplot as plt

mpl.use('TkAgg')


'''
Necessary for running relion_class_ranker

in optimizer.star:
    rlnParticleDiameter
    rlnDoIgnoreCtfUntilFirstPeak set to 0
in model.star:
    rlnClassDistribution (USE scratch.py)
    rlnPixelSize
    rlnNrClasses
    rlnNrBodies set to 1
    rlnDataDimensionality set to 2
    rlnOriginalImageSize
    rlnCurrentImageSize


Files:
/nfs/home/czerio/cryosparc/CS-polqhel-50ss-6mh-dna/J79/J79_020_class_averages.mrc
/nfs/home/czerio/cryosparc/CS-polqhel-5phos-24-16-dna/J73/J73_020_class_averages.mrc
/nfs/home/jmindrebo/cryosparc/CS-23mar10x-2/J39/J39_020_class_averages.mrc
/nfs/home/lgebert/cryosparc/CS-40s-ires-a2/J336/J336_020_class_averages.mrc
/nfs/home/jmindrebo/cryosparc/P209/J18/cryosparc_P209_J18_055_class_averages.mrc
/nfs/home/bbasanta/TAF_TTR/P193/J10/cryosparc_P193_J10_080_class_averages.mrc
'''

'''
Contains methods to convert data from cryoSPARC into a mocked RELION project (or mocking from a real RELION project), 
then runs relion_class_ranker and 2DAssess on the data. It also pulls as much metadata as possible from the cryoSPARC 
data.
'''

RLN_IMAGE_COL, IMAGE_COL = 'rlnReferenceImage', 'image_num'
RLN_SCORE_COL, SCORE_COL = 'rlnClassScore', 'score'

def rank_cryosparc_data(particles_file, particles_pass_file, class_avg_cs_file, mrc_file, rln_project, dummy_star_files, 
                        run_2d_assess=None):
    '''
    Runs a full pipeline for comparing relion_class_ranker to 2DAssess, using cryoSPARC data:
        1. Run csparc2star on J###_###_particles.cs, J###_###_class_averages.cs and MRC to get data and metadata
        2. Import metadata into new dummy RELION folder, along with dummy optimiser, sampling, and model STAR files
        3. Write the class distributions and estimated resolutions to `data_model_classes` table in the model STAR file
        4. Run relion_class_ranker on the imported data 
        5. (optional) Runs 2DAssess on the imported data (for comparison to relion_class_ranker)

    :param particles_file: full path of J###_###_particles.cs
    :param particles_pass_file: full path of J###_###_passthrough_particles.cs
    :param class_avg_cs_file: full path of J###_###_class_averages.cs
    :param mrc_file: full path to MRC or MRCS file containing the 2D class averages
    :param rln_project: full path of new folder for the dummy RELION project (may not exist yet)
    :param dummy_star_files: dict of full paths to dummy optimiser, sampling, and model STAR files. 
                            Keys are 'model', 'sampling', and 'optimiser'; each points to its corresponding file name
    :param run_2d_assess: to run 2DAssess, pass a str of the full path to the TensorFlow model (h5) file
    '''
    STAR_PREFIX = 'run_it025' # Prefix to put on STAR files to mock a RELION project

    print('\n')
    if not os.path.exists(f'{rln_project}/Class2D/job001/'):
        os.makedirs(f'{rln_project}/Class2D/job001/')
        print(f'Created new mock RELION project directory: {rln_project}')

    # Step 1
    print(f'Converting cryoSPARC data from {os.path.dirname(particles_file)}...')
    os.system(f'csparc2star.py {particles_file} {particles_pass_file} {rln_project}/Class2D/job001/{STAR_PREFIX}_data.star')
    shutil.copy(mrc_file, f'{rln_project}/Class2D/job001/{STAR_PREFIX}_classes.mrcs')
    print('Done\n')

    # Step 2
    print('Copying mock star files...')
    for name, star_path in dummy_star_files.items():
        print(f'\tCopying {name} from {star_path}')
        shutil.copy(star_path, f'{rln_project}/Class2D/job001/{STAR_PREFIX}_{name}.star')
    print('Done\n')
    
    # Step 3
    print('Writing metadata to model STAR file...')
    write_model_metadata(dummy_star_files['model'], f'{rln_project}/Class2D/job001/{STAR_PREFIX}_data.star', class_avg_cs_file)
    print('Done\n')

    # Step 4
    print('Running relion_class_ranker...')
    relion_cmd = fr'''`which relion_class_ranker` \
                --opt Class2D/job001/{STAR_PREFIX}_optimiser.star \
                --o Select/job001 \
                --fn_sel_parts particles.star \
                --fn_sel_classavgs class_averages.star \
                --python python3 \
                --fn_root rank \
                --do_granularity_features \
                --auto_select  \
                --min_score 0.5 \
                --pipeline_control Select/job001
            '''
    os.system(f'cd {rln_project}; {relion_cmd}')
    print('Done\n')

    # (Optional) Step 5
    if run_2d_assess is not None:
        print('Running 2DAssess...')
        os.system(f'cd {rln_project}; 2dassess -i {rln_project}/Class2D/job001/{STAR_PREFIX}_classes.mrcs -m {run_2d_assess}')
        print('Done\n')

def calculate_dummy_class_dist(particles, rel_mrc_path, img_name_col, class_dist_col):
    '''
    Calculates a dummy `model_classes` with `rlnClassDistribution` filled and all other columns filled with a 
    constant dummy variable

    :param particles: the `data_particles` table from a _data.star file
    :param rel_mrc_path: the path (relative to the RELION project dir) to the MRC/MRCS file
    :param img_name_col: name of the column that contains the image numbers of each 2D class avg
    :param class_dist_col: name of the column containing the class distributions
    '''

    output_col_names = [
            ('rlnAccuracyRotations', 1.0),
            ('rlnAccuracyTranslationsAngst', 0.67),
            ('rlnEstimatedResolution', 10),
            ('rlnOverallFourierCompleteness', 1),
            ('rlnClassPriorOffsetX', 0),
            ('rlnClassPriorOffsetY', 0)]
    
    model_classes = (particles.groupby('rlnClassNumber').count().iloc[:,0] / particles.shape[0]).to_frame(name=class_dist_col)
    img_names = [f'{i:06d}@{rel_mrc_path}' for i in range(1, model_classes.shape[0]+1)]
    model_classes.insert(0, img_name_col, img_names)

    for (col, val) in output_col_names:
        model_classes[col] = val

    return model_classes

def write_model_metadata(model_star_file, data_star_file, class_avg_cs_file):
    '''
    Writes a custom `data_model_classes` table to a specified _model.star file. 
    Calculates rlnClassDistribution, sets rlnEstimatedResolution, and sets all other attributes to a constant
    '''
    
    input_col_names = [
            'rlnImageName', 
            'rlnMicrographName',
            'rlnCoordinateX',
            'rlnCoordinateY',
            'rlnAnglePsi',
            'rlnOriginXAngst',
            'rlnOriginYAngst',
            'rlnDefocusU',
            'rlnDefocusV',
            'rlnDefocusAngle',
            'rlnPhaseShift',
            'rlnCtfBfactor',
            'rlnOpticsGroup']
    
    rel_mrc_path = 'Class2D/job001/run_it025_classes.mrcs'

    img_name_col = 'rlnReferenceImage'
    class_dist_col = 'rlnClassDistribution'
    est_res_col = 'rlnEstimatedResolution'

    data = starfile.read(data_star_file, always_dict=True)
    class_avgs = np.load(class_avg_cs_file)
    est_res = class_avgs['blob/res_A']
    particles = data['particles']
    model_classes = calculate_dummy_class_dist(particles, rel_mrc_path, img_name_col, class_dist_col)
    model_classes[est_res_col] = est_res

    output_dfs = starfile.read(model_star_file, always_dict=True)
    
    model_general = output_dfs['model_general']
    model_general['rlnPixelSize'] = class_avgs['blob/psize_A'][0]
    model_general['rlnNrClasses'] = class_avgs.shape[0]
    model_general['rlnOriginalImageSize'] = data['optics']['rlnImageSize']
    model_general['rlnCurrentImageSize'] = class_avgs['blob/shape'][0][0]

    output_dfs['model_classes'] = model_classes
    output_dfs['model_general'] = model_general
    
    starfile.write(output_dfs, model_star_file, overwrite=True, force_loop=False)
    

def mock_cryosparc_export(rln_project, mock_rln_project, true_star_files, dummy_star_files):
    '''
    Mocks a cryoSPARC export, using RELION data. This is used to determine how much information is
    lost when we use only the metadata provided by cryoSPARC.

    Runs a full pipeline for comparing relion_class_ranker to 2DAssess, using RELION data:
        1. Import metadata into new dummy RELION folder, along with dummy optimiser, sampling, and model STAR files. Imports
            from another basline RELION project whose files should be always held constant. Also copies the MRC file from
            the real RELION project (not the baseline one).
        2. Write the `model_classes` and `model_general` tables to `data_model_classes` table in the model STAR file
        3. Run relion_class_ranker on the imported data
        4. Find the mean absolute error (MAE) between when the other metadata is missing, and whether it is present. This
            requires the real RELION project to have run relion_class_ranker with all metadata already.

    :param rln_project: full path of the original RELION project
    :param mock_rln_project: full path to the mocked RELION project (may not exist yet)
    :param true_star_files: dict with two paths to the true model and data STAR files.
                    Keys are 'model' and 'data'; each points to its corresponding file name
    :param dummy_star_files: dict of full paths to dummy model, sampling, and optimiser STAR files. 
                    Keys are 'model', 'sampling', and 'optimiser'; each points to its corresponding file name
    :param run_2d_assess: to run 2DAssess, pass a str of the full path to the TensorFlow model (h5) file
    '''

    print(f'Mocking RELION project from {rln_project}...\n')

    STAR_PREFIX = 'run_it025'
    true_data_star = starfile.read(true_star_files['data'], always_dict=True)
    true_model_star = starfile.read(true_star_files['model'], always_dict=True)
    mock_model_star = starfile.read(dummy_star_files['model'], always_dict=True)
    mrc_file = os.path.join(rln_project, 'Class2D/job001/run_classes.mrcs')

   
    if not os.path.exists(f'{mock_rln_project}/Class2D/job001/'):
        os.makedirs(f'{mock_rln_project}/Class2D/job001/')
        print(f'Created new mock RELION project directory: {mock_rln_project}')

    # Step 1
    print('Copying mock star files...')
    for name, star_path in dummy_star_files.items():
        print(f'\tCopying {name} from {star_path}')
        shutil.copy(star_path, f'{mock_rln_project}/Class2D/job001/{STAR_PREFIX}_{name}.star')

    # Copy the true data STAR file
    # print(f'\tCopying data from {true_star_files["data"]}')
    # shutil.copy(true_star_files['data'], f'{mock_rln_project}/Class2D/job001/{STAR_PREFIX}_data.star')
    # Copy the MRC file as well
    shutil.copy(mrc_file, f'{mock_rln_project}/Class2D/job001/{STAR_PREFIX}_classes.mrcs')
    print('Done\n')


    # Step 2
    print('Writing metadata to model STAR file...')

    output_col_names = [
            ('rlnAccuracyRotations', 1.0),
            ('rlnAccuracyTranslations', 0.67),
            # ('rlnEstimatedResolution', 10),
            ('rlnOverallFourierCompleteness', 1),
            ('rlnClassPriorOffsetX', 0),
            ('rlnClassPriorOffsetY', 0),
            ('rlnAccuracyTranslations', 0.67)]
    
    mock_model_star['model_general'] = true_model_star['model_general']

    model_classes = true_model_star['model_classes']
    model_classes['rlnReferenceImage'] = \
        model_classes['rlnReferenceImage'].str.replace('run_', f'{STAR_PREFIX}_')

    for (col, val) in output_col_names:
        model_classes[col] = val

    mock_model_star['model_classes'] = model_classes
    print(model_classes.head(10))
    
    starfile.write(mock_model_star, f'{mock_rln_project}/Class2D/job001/{STAR_PREFIX}_model.star', overwrite=True, force_loop=False)
    
    data_cols = ['rlnImageName', 
            'rlnMicrographName',
            'rlnCoordinateX', 
            'rlnCoordinateY', 
            'rlnAnglePsi', 
            'rlnOriginXAngst', 
            'rlnOriginYAngst',
            'rlnDefocusU',  
            'rlnDefocusV',  
            'rlnDefocusAngle',  
            'rlnPhaseShift', 
            'rlnCtfBfactor', 
            'rlnOpticsGroup'
            ]
    
    particles = true_data_star['particles']
    true_data_star['particles'] = particles[data_cols]
    print(true_data_star['particles'].head())
    
    starfile.write(true_data_star, f'{mock_rln_project}/Class2D/job001/{STAR_PREFIX}_data.star', overwrite=True, force_loop=False)
    
    print('Done\n')

    '''
    TODO copy the mock data file over after extracting the class distribution metadata from the true one
    '''

    # Step 3
    print('Running relion_class_ranker...')
    relion_cmd = fr'''`which relion_class_ranker` \
                --opt Class2D/job001/{STAR_PREFIX}_optimiser.star \
                --o Select/job001 \
                --fn_sel_parts particles.star \
                --fn_sel_classavgs class_averages.star \
                --python python3 \
                --fn_root rank \
                --do_granularity_features \
                --auto_select  \
                --min_score 0.5 \
                --pipeline_control Select/job001
            '''
    # os.system(f'cd {mock_rln_project}; {relion_cmd}')
    print('Done\n')

    # Step 4
    # The two `rank_model.star` files to compare 
    baseline_rank_file = os.path.join(rln_project, 'Select/job001/rank_model.star')
    modified_rank_file = os.path.join(mock_rln_project, 'Select/job001/rank_model.star')

    score_mae = find_scores_mae(baseline_rank_file, modified_rank_file)

    print(f'MAE score of {score_mae}\n')


def find_scores_mae(rank_path1, rank_path2):
    '''
    Finds the MAE between two score distributions for relion_class_ranker, using different
    metadata (some metadata will have been modified to be 0). This is useful to quantify the
    importance of a certain metadata value

    Copied from edit_optimizer.py
    '''

    df1, df2 = get_class_avg_df(rank_path1), get_class_avg_df(rank_path2)
    scores_df = pd.merge(df1, df2, left_index=True,  right_index=True, suffixes=('_1', '_2'))

    res = (scores_df['score_1'] - scores_df['score_2']).abs().mean()
    try:
        return res.mean()
    except:
        return res

def get_class_avg_df(star_path, sort=False):
    '''
    Returns a pd.DataFrame, with each row representing one 2D class average, containing its 
    image number as the index (index in the MRCS file) and its quality score given by RELION, given a 
    "rank_model.star" path.

    Copied from edit_optimizer.py
    '''
    relion_scores = starfile.read(star_path)

    # Extract only the image number and its score from the DataFrame
    match_str = r'^(\d{6})'
    relion_scores[IMAGE_COL] = relion_scores[RLN_IMAGE_COL].str.extract(match_str).astype(int)
    relion_scores = relion_scores[[IMAGE_COL, RLN_SCORE_COL]].rename(columns={RLN_SCORE_COL: SCORE_COL})

    if sort:
        # Sort descending by score, if specified
        relion_scores = relion_scores.sort_values(by=SCORE_COL, ascending=False)


    return relion_scores.set_index(IMAGE_COL)

def find_scores(rank_path1, rank_path2, sort=False):
    '''
    Finds the scores of two class rankings on the same dataset, using different
    metadata (some metadata will have been modified). This is useful to quantify the
    importance of metadata values

    Copied from display_score_diff.py
    '''

    df1, df2 = get_class_avg_df(rank_path1), get_class_avg_df(rank_path2)
    scores_df = pd.merge(df1, df2, left_index=True,  right_index=True, suffixes=('_1', '_2'))

    if sort:
        scores_df = scores_df.sort_values(by='score_1', ascending=False)

    return scores_df

def plot_score_diffs(mrc_path, baseline_ranked_path, mock_ranked_path):
    '''
    Plots each 2D class avg along with its true score and its mocked score.
    '''

    mrc_data = mrcfile.open(mrc_path).data

    num_subplots = 20 # Max number of subplots per plot
    rows, cols = 4, 5
    num_plots = int(np.ceil(mrc_data.shape[0] / num_subplots))

    scores_df = find_scores(baseline_ranked_path, mock_ranked_path).sort_values(by='score_1')

    for d in range(num_plots):
        fig, axes = plt.subplots(rows, cols)
        fig.suptitle(f'Rank {num_subplots*d+1} to {num_subplots*(d+1)}')
        fig.subplots_adjust(hspace=1)
        fig.subplots_adjust(wspace=1.5)
        
        # Display the RELION results
        for i in range(num_subplots*d, min(num_subplots*(d+1), len(scores_df))):
            # Display each 2D class avg in a grid
            img = mrc_data[scores_df.index[i] - 1]
            ax = axes[(i%num_subplots)//cols, (i%num_subplots)%cols]
 
            
            ax.axis('off')
            ax.imshow(img, cmap='gray')
            ax.set_title(f'{scores_df.iloc[i]["score_1"]:.4f} -- {scores_df.iloc[i]["score_2"]:.4f}', fontsize=10)

    print('Plotting images now')
    plt.show()


def run_main():
    
    
    # For mocking a RELION project from a cryoSPARC export
    
    # csparc_project = '/nfs/home/jmindrebo/cryosparc/CS-23mar10x-2'
    # job_num = 'J39'
    
    # particles_file = f'{csparc_project}/{job_num}/{job_num}_020_particles.cs'
    # particles_pass_file = f'{csparc_project}/{job_num}/{job_num}_passthrough_particles.cs'
    # class_avg_cs_file = f'{csparc_project}/{job_num}/{job_num}_020_class_averages.cs'
    # mrc_file = f'{csparc_project}/{job_num}/{job_num}_020_class_averages.mrc'
    # rln_project = f'/nfs/home/khom/test_projects/ExampleData/{job_num}'
    # dummy_star_files = {
    #     'model': '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_model.star',
    #     'optimiser': '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_optimiser.star',
    #     'sampling': '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_sampling.star'
    # }
    # run_2d_assess = '/nfs/home/khom/2dassess_062119.h5'

    # rank_cryosparc_data(particles_file, particles_pass_file, class_avg_cs_file, mrc_file, rln_project, 
    #                     dummy_star_files, run_2d_assess=run_2d_assess)
    

    # For mocking a RELION project that would be produced by a cryoSPARC export, using a true RELION export
    # Essentially gets rid of any metadata that would not be present during a cryoSPARC conversion

    rln_project_name = 'Aechohbozed2'

    rln_project = f'/nfs/home/khom/test_projects/ExampleData/{rln_project_name}' # original RELION project dir
    mock_rln_project = f'/nfs/home/khom/test_projects/ExampleData/{rln_project_name}_mock' # new mocked project to simulate
    
    # Path to the true data STAR file that was created during the 2D class process

    true_star_files = {
        'model': f'/nfs/home/khom/test_projects/ExampleData/{rln_project_name}/Class2D/job001/run_model.star',
        'data': f'/nfs/home/khom/test_projects/ExampleData/{rln_project_name}/Class2D/job001/run_data.star'
    }

    # Sources for dummy star files to copy over
    dummy_star_files = {
        # 'data': '/nfs/home/khom/test_projects/ExampleData/J39/Class2D/job001/run_it025_data.star',
        'model': '/nfs/home/khom/test_projects/ExampleData/J39/Class2D/job001/run_it025_model.star',
        'optimiser': '/nfs/home/khom/test_projects/ExampleData/J39/Class2D/job001/run_it025_optimiser.star',
        'sampling': '/nfs/home/khom/test_projects/ExampleData/J39/Class2D/job001/run_it025_sampling.star'
    }

    mock_cryosparc_export(rln_project, mock_rln_project, true_star_files, dummy_star_files)





def print_score_diff(path1, path2, sort=False):
    
    print(find_scores(path1, path2, sort=sort))

if __name__ == '__main__':
    pd.options.display.max_rows = 1000
    # run_main()
    
    baseline_ranked_path = '/nfs/home/khom/test_projects/ExampleData/Aechohbozed2/Select/job001/rank_model.star'
    mock_ranked_path = '/nfs/home/khom/test_projects/ExampleData/Aechohbozed2_mock/Select/job001/rank_model.star'
    print_score_diff(baseline_ranked_path, mock_ranked_path, sort=True)
    
    mrc_path = '/nfs/home/khom/test_projects/ExampleData/Aechohbozed2_mock/Class2D/job001/run_it025_classes.mrcs'
    plot_score_diffs(mrc_path, baseline_ranked_path, mock_ranked_path)