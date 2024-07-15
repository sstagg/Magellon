# 2D Class Average Manual Labelling for Training Data
## Instructions For Extracting Data

**A 2D Class job only needs to be extracted once. If your role is only to label data, disregard these instructions and see *TkTeach.md* for instructions on how to label data.**

This Markdown file will guide you in extracting your cryoSPARC 2D Class jobs into individual JPG files that can then be used for manually labeling, which will then be fed into the machine learning algorithm. 

## Steps

1. Make sure that you have downloaded `ClassAvgLabeling` from the shared OneDrive onto your Linux machine. The download location does not matter. 
2. To ensure that Python dependencies are not violated, we recommend you create an Anaconda environment using the provided `requirements.txt` (make sure Anaconda is installed first). *However, if you are able to run Step 3 without any errors, you don't need to do this.* 

**To set up an Anaconda Environment: on your Linux machine, run the following commands in your terminal**
    
    $ cd /path/to/ClassAvgLabeling/

    Given that /path/to/conda/envs is the directory containing Anaconda environments:
    $ conda create -p /path/to/conda/envs/magellon2davg python=3.8.3

    $ conda activate /path/to/conda/envs/magellon2davg

    $ pip3 install -r requirements.txt

    Make sure that the 'magellon2davg' environment is active whenever you run a Python script. 
    When you finish your work, deactivate the environment: 
    $ conda deactivate
3. On your Linux machine, in a terminal shell, navigate to this folder (`ClassAvgLabeling`).
4. Run `extract_mrc.py` with Python on all jobs that we want to extract data from. This pulls out the image data (as JPGs) and the necessary metadata, and places it into a desired directory. **Please pass in the following command line arguments:**
    - `--directory`: The path to the directory to place the data and metadata into. The directory must exist.
    - Either `--job-dir` or `--job-dir-list`. This lets you choose whether to extract data from a single job, or from many jobs at once, respectively:
        - `--job-dir`: A single cryoSPARC 2D averaging job folder e.g., `/nfs/home/glander/cryosparc/P175/J66/`, where **J66** is the 2D class job.
        - `--job-dir-list`: A `.txt` file containing a list of cryoSPARC job folders, with one folder per line. Please provide the FULL directory path, e.g. `/nfs/home/glander/cryosparc/P175/J66/` See `example_jobs.txt` for an example on the expected format of this file.

    Within the destination directory, the program creates an `images` folder and `metadata` folder. The structure of each folder is detailed here for your convenience, but you will not need to edit them at all.
    - Inside `images`, each job that you extract from is given a uniquely named sub-directory `[project ID]_[job ID]_[user ID]`, into which all the images are placed as JPGs.
    - Inside `metadata`, each job that you extract from is given the same uniquely named `[project ID]_[job ID]_[user ID].npy` file which contains all the necessary metadata for the class averages of that job. 

    Example extracting data from a single job:

        python extract_mrc.py --directory /path/to/MyDestinationFolder/ --job-dir /path/to/cryoSPARCjob/PXXX/JXX/

    Example extracting data from multiple jobs:

        python extract_mrc.py --directory /path/to/MyDestinationFolder/ --job-dir-list /path/to/listOfJobDirectories.txt

5. You may run Step 3 multiple times with either `--job-dir` and `--job-dir-list` (rather than all at once), but make sure you pass the same `--directory` each time.
6. From your destination directory (that you passed to `--directory`), copy the `images` and `metadata` folders into your lab's home folder on the shared OneDrive (e.g., `LanderData/`). 
7. On the shared OneDrive, begin labeling the new images. See **TkTeach.md** for instructions on manual labeling. 

    