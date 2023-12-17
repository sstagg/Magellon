# 2D Class Average Manual Labelling for Training Data

These files will help you manually label your cryoSPARC 2D class averaged particle image data, for use in Magellon's new ML-driven algorithm for automatic selection of 2D averages.<br>

Please make sure you have **Python 3** available (this program was tested in Python 3.8.3). Python library requirements are in `requirements.txt`. The `tkteach.py` program was modified from the original program written by [rmones](https://github.com/rmones/tkteach) under the Apache License 2.0.

## Steps

1. In a terminal shell, navigate to this folder (**ClassAvgLabeling**).
2. Run `extract_mrc.py` on all jobs that we want to extract data from. This pulls out the image data (as JPGs) and the necessary metadata, and places it into your lab's home folder (e.g., `LanderLab/`). Please pass in the following command line arguments: 
    - `--directory`: The path to your lab's home folder (e.g., `LanderLab/`), which will tell the program where to extract the data. 
    - Either `--job-dir` or `--job-dir-list`. This lets you choose whether to extract data from a single job, or from many jobs at once:
        - `--job-dir`: A single cryoSPARC 2D averaging job folder.
        - `--job-dir-list`: A `.txt` file containing a list of cryoSPARC job folders, with one folder per line. Please provide the FULL folder path, e.g. `/nfs/home/glander/cryosparc/P175/J66/`, where **J66** is the 2D class job. See `example_jobs.txt` for a an example on formatting this file.<br>

    Within your lab's folder, the program creates an `images` folder and `metadata` folder.
    - Inside `images`, each job that you extract from is given a uniquely named sub-folder `[project ID]_[job ID]_[user ID]`, into which all the images are placed as JPGs.
    - Inside `metadata`, each job that you extract is given the same uniquely named `[project ID]_[job ID]_[user ID].npy` file which contains all the necessary metadata for the class averages of that job. 

3. To begin manually labeling your data, run `tkteach.py`. Please pass in the following command line argument:
    - `--directory`: Your lab's home folder, same as in step 2. 
    
    This program will create a pop-up GUI for you to quickly select folders containing images and manually assign them scores. **Make sure you have X11 forwarding set up** or the program will crash, since tkteach uses a graphical display.

## Tips for using tkteach
- When you first open the program, select a dataset on the left, then click **'Load Data Set'**. Each 2D class averaging job represents one dataset.
- Full-screen the window or zoom in/out on the images to fit your screen size.
- For each image, you may assign it a score by either:
    - Clicking on the category on the right-hand side, or
    - Typing the corresponding key (A, B, C, D, or F)
- You can close tkteach at any time and it will save your answers for you.
- **Be careful not to assign multiple categories to one image, since tkteach will allow you to do this**