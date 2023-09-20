import starfile
import numpy as np
import pandas as pd


import edit_optimizer

'''
Parameters of interest: 

rlnClassDistribution
rlnAccuracyRotations
rlnEstimatedResolution

rlnPixelSize?



'''

def find_scores(rank_path1, rank_path2):
    '''
    Finds the scores of two class rankings on the same dataset, using different
    metadata (some metadata will have been modified). This is useful to quantify the
    importance of a certain metadata value
    '''

    df1, df2 = edit_optimizer.get_class_avg_df(rank_path1), edit_optimizer.get_class_avg_df(rank_path2)
    scores_df = pd.merge(df1, df2, left_index=True,  right_index=True, suffixes=('_1', '_2'))

    return scores_df



def get_score_diff(attr_name, val, star_name, out_file_name):
    '''
    '''

    index_map = dict(zip(['optimizer', 'sampling', 'data', 'model'], range(4)))
    star_input_paths = [
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_optimiser.star', 
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_sampling.star',
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_data.star',
        '/nfs/home/glander/KaiC/Class2D/job001/run_it025_model.star'
    ]

    star_output_paths = [
        '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_optimiser.star',
        '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_sampling.star',
        '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_data.star',
        '/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_model.star'
    ]

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

    # Path to the 'rank_model.star' file containing the scores of each 2D average using edited metadata
    ranked_mrc_path = '/nfs/home/khom/test_projects/ExampleData/KaiC/Select/job001/rank_model.star'
    # Path to the 'rank_model.star' file containing the scores of each 2D average using original metadata
    baseline_ranked_mrc_path = '/nfs/home/khom/test_projects/Select/job011/rank_model.star'
    # Path to the directory containing the modified relion project output 
    relion_project_path = f'/nfs/home/khom/test_projects/ExampleData/KaiC/'
    # Path to the _optimizer.star file that resulted from the 2D class averaging
    optimizer_path = f'/nfs/home/khom/test_projects/ExampleData/KaiC/Class2D/job001/run_it025_optimiser.star'

    index = index_map[star_name]
    to_modify[index] = {attr_name: val}
    star_input_path = [star_input_paths[index]]
    star_output_path = [star_output_paths[index]]

    dfs = starfile.read(star_input_paths[index], always_dict=True)
    for name, df in dfs.items():
        if attr_name in df.columns:
            edit_optimizer.modify_attributes(star_input_path, star_output_path, [{attr_name: np.atleast_1d(val)}])
            edit_optimizer.execute_relion_class_ranker(optimizer_path, relion_project_path)

            scores = find_scores(ranked_mrc_path, baseline_ranked_mrc_path)

            scores.to_csv(out_file_name)
            print(f'MAE of {(scores["score_1"] - scores["score_2"]).abs().mean()} in table {name}:')
            print(scores, '\n')



get_score_diff('rlnEstimatedResolution', 1, 'model', 'scores_estimatedResolution1.csv')