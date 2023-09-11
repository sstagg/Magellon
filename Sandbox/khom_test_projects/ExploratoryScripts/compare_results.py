import starfile
import mrcfile
import os
import re
import numpy as np
import pandas as pd
import matplotlib as mpl


from matplotlib import pyplot as plt, colors as clr

mpl.use('TkAgg')

'''
This file contains methods to visually compare the scoring/classification results of 
RELION's class ranker and 2DAssess 
'''

# For use in the pd.DataFrame representing the scores for each 2D class average
image_name_col, image_num_col = 'rlnReferenceImage', 'image_num'
class_score_col, score_col = 'rlnClassScore', 'score'
label_col = 'label' 

# Names of the directories containing the corresponding label, in which each 2D class average is assigned
label_folders = ['Clip', 'Edge', 'Good', 'Noise']

def get_mrc_data(mrcs_path):
    '''
    Returns np.ndarray of size (num_images, height, width) corresponding to the number of 
    images in the MRCS file 
    '''
    return mrcfile.open(mrcs_path).data

def get_class_avg_df(star_path, assess_path, sort=False):
    '''
    Returns a pd.DataFrame with one row representing one 2D class average, containing its 
    image number (index in the MRCS file) and its quality score given by RELION
    '''
    relion_scores = starfile.read(star_path)
    class_avg_labels = get_class_avg_labels(assess_path)

    # Extract only the image number and its score from the DataFrame
    match_str = r'^(\d{6})'
    relion_scores['image_num'] = relion_scores[image_name_col].str.extract(match_str).astype(int)
    relion_scores = relion_scores[[image_num_col, class_score_col]].rename(columns={class_score_col: score_col})
    relion_scores[label_col] = relion_scores['image_num'].map(class_avg_labels)

    if sort:
        # Sort descending by score, if specified
        relion_scores = relion_scores.sort_values(by=score_col, ascending=False)

    return relion_scores.set_index('image_num')

def get_class_avg_labels(assess_path):
    '''
    Returns a dictionary mapping {particle number -> label} where label is one of 
    ['Clip', 'Edge', 'Good', 'Noise']
    '''
    particle_labels = {}
    particle_pattern = r'[A-z]+_(\d+).jpg'
    
    for label_name in label_folders:
        labeled_img_path = os.path.join(assess_path, label_name)
        
        for img_name in os.listdir(labeled_img_path):
            particle_id = int(re.search(particle_pattern, img_name).group(1))
            particle_labels[particle_id] = label_name

    return particle_labels

def display_relion(mrc_data, class_avg_df):
    '''
    Display images sorted by their scores given by RELION, and whose borders are green (if 2DAssess
    deemed it 'good') or red (if 2DAssess deemed it 'bad')
    '''
    num_subplots = 20 # Max number of subplots per plot
    rows, cols = 4, 5
    num_plots = int(np.ceil(mrc_data.shape[0] / num_subplots))
    # cmap = clr.LinearSegmentedColormap.from_list('green_to_red', ['red', 'green'], N=256)

    for d in range(num_plots):
        fig, axes = plt.subplots(rows, cols)
        fig.suptitle(f'Rank {num_subplots*d+1} to {num_subplots*(d+1)}')
        fig.subplots_adjust(hspace=1)
        
        # Display the RELION results, colored by the label given by Cianfrocco
        for i in range(num_subplots*d, min(num_subplots*(d+1), len(class_avg_df))):
            # Display each 2D class avg in a grid
            img = mrc_data[class_avg_df.index[i] - 1]
            ax = axes[(i%num_subplots)//cols, (i%num_subplots)%cols]
            quality_color =  ((0., 1., 0., 1.) 
                                if class_avg_df.iloc[i][label_col] == 'Good' 
                                else (1., 0., 0., 1.))
            filled_img = add_border(img, img.shape, quality_color)
            
            ax.axis('off')
            ax.imshow(filled_img)
            ax.set_title(f'{class_avg_df.iloc[i][score_col]:.4f}')
    print('Plotting images now')
    plt.show()

def display_2dassess(mrc_data, class_avg_df):
    '''
    Display images categorized into 4 plots, for each label of 2DAssess. Sorted and labeled by the
    score given by RELION 
    '''
    cols = 6

    # Display a series of subplots for each label
    for label_name in label_folders:
        labeled_df = class_avg_df[class_avg_df[label_col] == label_name]
        rows = max(int(np.ceil(len(labeled_df) / cols)), 0) +  1
        
        fig, axes = plt.subplots(rows, cols)
        fig.subplots_adjust(hspace=1)
        fig.suptitle(label_name)

        for z in axes.flatten():
            z.axis('off')
        

        for i, (img_id, row) in enumerate(labeled_df.iterrows()):
            img = normalize(mrc_data[img_id-1])
            ax = axes[i//cols, i%cols] 
            ax.axis('off')
            ax.imshow(img, cmap='gray')
            ax.set_title(f'{row[score_col] :.3f}')



    plt.show()

def plot_thresholds(class_avg_df):
    assess_label_col, relion_label_col = 'assess_labels', 'relion_labels'

    def get_accuracy(assess_labels, relion_labels):
        return (assess_labels == relion_labels).sum() / len(assess_labels)

    df = class_avg_df.copy()
    df[assess_label_col] = df[label_col].replace({
        'Clip': False, 'Edge': False, 'Noise': False, 'Good': True
    })
    
    thresholds = np.arange(0, 1, 0.01)
    acc = []
    for t in thresholds:
        df[relion_label_col] = (df[score_col] > t)
        acc.append(get_accuracy(df[assess_label_col], df[relion_label_col]))

    plt.plot(thresholds, acc)
    plt.xlabel('Threshold value')
    plt.ylabel(r'% of labels agreed upon')
    plt.show()
        

def add_border(img, shape, rgba, b=5, norm=True):
    '''
    Adds a colored border of given thickness around an RGB image
    '''    
    pad_img = np.ones((3,) + (shape[0] + 2*b, shape[1] + 2*b))
    rgb = np.array(rgba[:3])
    padded_img = np.einsum('i,ijk->ijk', rgb, pad_img).T
    if norm:
        img = normalize(img)

    padded_img[b:-b, b:-b, :] = np.repeat(img[np.newaxis,...], 3, axis=0).T
    
    return padded_img

def normalize(arr):
    return (arr - arr.min()) / (arr.max() - arr.min())


# Name of the RELION project directory
proj_dir = 'J39'

# Path to model.star file containing the quality score, from 0 to 1, of each 2D class average
star_path = f'/nfs/home/khom/test_projects/ExampleData/{proj_dir}/Select/job001/rank_model.star'
# Path to MRCS file containing the images of the 2D class averages
mrcs_path = f'/nfs/home/khom/test_projects/ExampleData/{proj_dir}/Class2D/job001/run_it025_classes.mrcs'
# Path to the 2D assess directory containing 4 directories of JPG sorted into the 4 categories
assess_path = f'/nfs/home/khom/test_projects/ExampleData/{proj_dir}/Class2D/job001/2DAssess'


mrc_data = get_mrc_data(mrcs_path)
class_avg_df = get_class_avg_df(star_path, assess_path, sort=True)



display_relion(mrc_data, class_avg_df)
# display_2dassess(mrc_data, class_avg_df)
# plot_thresholds(class_avg_df)


