import mrcfile
import starfile
import numpy as np
import pandas as pd
import os





RLN_IMAGE_COL, IMAGE_COL = 'rlnReferenceImage', 'image_num'
RLN_SCORE_COL, SCORE_COL = 'rlnClassScore', 'score'


def get_numeric_columns(df, exclude=[]):
    '''
    Returns the names of all numeric columns in the DataFrame
    Exclude any specified columns
    '''
    return df.select_dtypes(include=np.number).drop(labels=exclude, axis='columns', errors='ignore').columns


def modify_attributes(input_paths, output_paths, attrs_list):
    '''
    Zeros out all specified attributes from each of the STAR files, and writes each to a new 
    STAR file at a specified location

    attrs_list is a list of dict, each dict represents a set of attributes mapped to new
    values for one STAR file

        Each value in attrs_list maps {attribute_name --> value}, where value can either
        be (1) a scalar value, or (2) an iterable with same length as the table 
    '''

    N = len(input_paths) # Number of STAR files to modify 

    for i in range(N):
        dfs = starfile.read(input_paths[i], always_dict=True)
        print(f'Writing: {output_paths[i]} ({len(dfs)} sub-table(s))')

        for name, df in dfs.items():
            for attribute in attrs_list[i]:
                if attribute in df.columns:
                    if len(attrs_list[i][attribute]) != df.shape[0]:
                        df[attribute] = [attrs_list[i][attribute][0]] * df.shape[0]
                    else:
                        df[attribute] = attrs_list[i][attribute]
                    print(f'\tModify: {attribute} in sub-table {name}')
            

        starfile.write(dfs, output_paths[i], overwrite=True, force_loop=False)
            
    print('Finished!')
    

def execute_relion_class_ranker(optimizer_path, 
                                relion_project_path,
                                relative_output_path='Select/job001'):
    '''
    Runs the relion_class_ranker program from the command line, given the _optimizer.star file
    that was produced by the 2D classification.

    The relative output path is the path (relative to this python file) to dump the results
    of the ranking
    '''

    relion_cmd = fr'''`which relion_class_ranker` \
                --opt {optimizer_path} \
                --o {relative_output_path} \
                --fn_sel_parts particles.star \
                --fn_sel_classavgs class_averages.star \
                --python python3 \
                --fn_root rank \
                --do_granularity_features \
                --auto_select  \
                --min_score 0.5 \
                --pipeline_control {relative_output_path}
            '''
    os.system(f'cd {relion_project_path}; {relion_cmd}')    


def get_class_avg_df(star_path, sort=False):
    '''
    Returns a pd.DataFrame, with each row representing one 2D class average, containing its 
    image number as the index (index in the MRCS file) and its quality score given by RELION, given a 
    "rank_model.star" path.
    '''
    relion_scores = starfile.read(star_path)

    # Extract only the image number and its score from the DataFrame
    match_str = r'^(\d{6})'
    relion_scores[IMAGE_COL] = relion_scores[RLN_IMAGE_COL].str.extract(match_str).astype(int)
    relion_scores = relion_scores[[IMAGE_COL, RLN_SCORE_COL]].rename(columns={RLN_SCORE_COL: SCORE_COL})
    # relion_scores[label_col] = relion_scores['image_num'].map(class_avg_labels)

    if sort:
        # Sort descending by score, if specified
        relion_scores = relion_scores.sort_values(by=SCORE_COL, ascending=False)


    return relion_scores.set_index(IMAGE_COL)

def find_scores_mae(rank_path1, rank_path2):
    '''
    Finds the MAE between two score distributions for relion_class_ranker, using different
    metadata (some metadata will have been modified to be 0). This is useful to quantify the
    importance of a certain metadata value
    '''

    df1, df2 = get_class_avg_df(rank_path1), get_class_avg_df(rank_path2)
    scores_df = pd.merge(df1, df2, left_index=True,  right_index=True, suffixes=('_1', '_2'))

    res = (scores_df['score_1'] - scores_df['score_2']).abs().mean()
    try:
        return res.mean()
    except:
        return res


def find_diffs_one_by_one(star_path, star_modified_path, 
                          ranked_modified_path, ranked_baseline_path, 
                          relion_project_path, optimizer_path, 
                          exclude=[], output_file='output.txt'):
    '''
    Iterates over all features and zeros them out one at a time in the given STAR file,
    and prints out the mean absolute error (MAE) each time

    star_path: STAR file to read from
    star_modified_path: STAR file to write the modified data to
    ranked_modified_path: rank_model.star path which contains the results of running the ranker on modified metadata
    ranked_baseline_path: rank_model.star path that was run on the true metadata
    relion_project_path: path to the 'fake' relion project that contains the modified STAR files
    optimizer_path: path to the modified _optimizer.star file
    exclude: list of attribtues to exclude from modification 

    '''


    dfs = starfile.read(star_path, always_dict=True)
    for name, df in dfs.items():
        # df = starfile.read(star_path)
        attributes = get_numeric_columns(df, exclude=exclude)

        res_file = open(output_file, 'a')
        res_file.write(f'Finding individual MAE for {len(attributes)} attributes in table {name}...\n')
        res_file.close()

        for attribute in attributes:
            star_input_paths = [star_path]
            star_output_paths = [star_modified_path]
            attribute_val = df[attribute]
            # to_zero = [[attribute]]
            # Zero each attribute, then call relion_class_ranker, then compare the results
            #  to the baseline

            for i, val in enumerate([-1, 0, 1, attribute_val*2, attribute_val*3, attribute_val*4]):
                modify_attributes(star_input_paths, star_output_paths, [{attribute: np.atleast_1d(val)}])    
                execute_relion_class_ranker(optimizer_path, relion_project_path)
                score_mae = find_scores_mae(ranked_modified_path, ranked_baseline_path)

                res_file = open(output_file, 'a')
                res_file.write(f'\tMAE for {attribute} set to value #{i} ({type(val)}): {score_mae}\n')
                res_file.close()
    
    print('Finished!')


def run_full_modification(star_name, exclude=[]):
    '''
    For one *.star file, run a comparison by changing each attribute one at a time and recording the MAE
    `star_name` must be one of 'optimizer', 'data', 'sampling', 'model'
    '''

    index_map = dict(zip(['optimizer', 'sampling', 'data', 'model'], range(4)))

    if star_name not in index_map.keys():
        raise ValueError(f'{star_name} is not a valid option')
    
    star_input_paths = [
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_optimiser.star', 
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_sampling.star',
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_data.star',
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_model.star'
    ]

    star_output_paths = [
        f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/Class2D/job001/run_it025_optimiser.star',
        f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/Class2D/job001/run_it025_sampling.star',
        f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/Class2D/job001/run_it025_data.star',
        f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/Class2D/job001/run_it025_model.star'
    ]

    # Path to the directory containing the modified relion project output 
    relion_project_path = f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/'

    to_modify = [
        # optimizer:
        {}, 
        # sampling:
        {},     
        # data:
        {},   
        # model:       
        {}           
    ]

    # --------
    # Path to the 'rank_model.star' file containing the scores of each 2D average using edited metadata
    ranked_mrc_path = f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/Select/job001/rank_model.star'
    # Path to the 'rank_model.star' file containing the scores of each 2D average using original metadata
    baseline_ranked_mrc_path = '/nfs/home/khom/test_projects/Select/job011/rank_model.star'
    # Path to the _optimizer.star file that resulted from the 2D class averaging
    run_optimizer_path = f'/nfs/home/khom/test_projects/ExampleData/KaiC/{star_name}/Class2D/job001/run_it025_optimiser.star'

    # First, copy all star files to the directory, manually modifying some attributes if desired 
    modify_attributes(star_input_paths, star_output_paths, to_modify)

    index = index_map[star_name]
    find_diffs_one_by_one(star_input_paths[index], 
                          star_output_paths[index], 
                          ranked_mrc_path, 
                          baseline_ranked_mrc_path, 
                          relion_project_path,
                          star_output_paths[0],
                          exclude=exclude, 
                          output_file=f'{star_name}_output.txt')


# data, model, sampling, optimizer

exclude = [
'rlnSpectralIndex',
'rlnResolution',
'rlnAngstromResolution',
'rlnSsnrMap',
'rlnGoldStandardFsc',
'rlnFourierCompleteness',
'rlnReferenceSigma2',
'rlnReferenceTau2',
'rlnSpectralOrientabilityContribution',
'rlnReferenceDimensionality',
'rlnDataDimensionality',
'rlnOriginalImageSize',
'rlnCurrentResolution',
'rlnCurrentImageSize',
'rlnPaddingFactor',
'rlnIsHelix',
'rlnFourierSpaceInterpolator',
'rlnMinRadiusNnInterpolation',
'rlnPixelSize',
'rlnNrClasses',
'rlnNrBodies',
'rlnNrGroups',
'rlnTau2FudgeFactor',
'rlnNormCorrectionAverage',
'rlnSigmaOffsetsAngst',
'rlnOrientationalPriorMode',
'rlnSigmaPriorRotAngle',
'rlnSigmaPriorTiltAngle',
'rlnSigmaPriorPsiAngle',
'rlnLogLikelihood',
'rlnAveragePmax',
'rlnReferenceImage',
'rlnClassDistribution' ,
'rlnAccuracyRotations',
'rlnAccuracyTranslationsAngst',
'rlnEstimatedResolution',
'rlnOverallFourierCompleteness',
'rlnClassPriorOffsetX',
'rlnClassPriorOffsetY']

run_full_modification('model', exclude=exclude)


# star_input_paths = [
#     '/nfs/home/glander/KaiC/Class2D/job001/run_it025_optimiser.star', 
#     '/nfs/home/glander/KaiC/Class2D/job001/run_it025_sampling.star',
#     '/nfs/home/glander/KaiC/Class2D/job001/run_it025_data.star',
#     '/nfs/home/glander/KaiC/Class2D/job001/run_it025_model.star'
# ]

# star_output_paths = [
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_optimiser.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_sampling.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_data.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_model.star'
# ]

# For optimizer.star:
# star_output_paths = [
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/optimizer/Class2D/job001/run_it025_optimiser.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/optimizer/Class2D/job001/run_it025_sampling.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/optimizer/Class2D/job001/run_it025_data.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/optimizer/Class2D/job001/run_it025_model.star'
# ]
# # Path to the directory containing the modified relion project output 
# relion_project_path = '/nfs/home/khom/test_projects/ExampleData/KaiC/optimizer/'

# For model.star:
# star_output_paths = [
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/model/Class2D/job001/run_it025_optimiser.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/model/Class2D/job001/run_it025_sampling.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/model/Class2D/job001/run_it025_data.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/model/Class2D/job001/run_it025_model.star'
# ]
# # Path to the directory containing the modified relion project output 
# relion_project_path = '/nfs/home/khom/test_projects/ExampleData/KaiC/model/'

# For data.star:
# star_output_paths = [
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/data/Class2D/job001/run_it025_optimiser.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/data/Class2D/job001/run_it025_sampling.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/data/Class2D/job001/run_it025_data.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/data/Class2D/job001/run_it025_model.star'
# ]
# # Path to the directory containing the modified relion project output 
# relion_project_path = '/nfs/home/khom/test_projects/ExampleData/KaiC/data/'

# For sampling.star:
# star_output_paths = [
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/sampling/Class2D/job001/run_it025_optimiser.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/sampling/Class2D/job001/run_it025_sampling.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/sampling/Class2D/job001/run_it025_data.star',
#     '/nfs/home/khom/test_projects/ExampleData/KaiC/sampling/Class2D/job001/run_it025_model.star'
# ]
# # Path to the directory containing the modified relion project output 
# relion_project_path = '/nfs/home/khom/test_projects/ExampleData/KaiC/sampling/'


# to_zero = [
#     # optimizer:
#     [], 
#     # sampling:
#     [],     
#     # data:
#     [],   
#     # model:       
#     []           
# ]







# print(get_class_avg_df(ranked_mrc_path, sort=True))
# modify_attributes(star_input_paths, star_output_paths, to_zero)



# execute_relion_class_ranker(run_optimizer_path, relion_project_path)
# find_scores_mae(ranked_mrc_path, baseline_ranked_mrc_path)

# print(get_class_avg_df(ranked_mrc_path, sort=True))
# print(get_class_avg_df(baseline_ranked_mrc_path, sort=True))

# find_diffs_one_by_one(star_input_paths[0], star_output_paths[0], 
#                           ranked_mrc_path, baseline_ranked_mrc_path, relion_project_path,
#                          star_output_paths[0], exclude=[], output_file='model_output.txt')

'''
`which relion_class_ranker` --opt Class2D/job001/run_it025_optimiser.star --o Select/job001/ --fn_sel_parts particles.star --fn_sel_classavgs class_averages.star --python python3 --fn_root rank --do_granularity_features  --auto_select  --min_score 0.5  --pipeline_control Select/job001/
'''

