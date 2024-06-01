# 2D Class Average Manual Labelling for Training Data

These files will help you manually label your cryoSPARC 2D class averaged particle image data, for use in Magellon's new ML-driven algorithm for automatic selection of 2D averages. This README file provides a brief overview of the purposes of each Python file and the workflow. For more detailed information:

- See **ExtractMRC.md** for more details on how to extract your 2D class data and necessary metadata. Since the data only needs to be extracted once, only one person per lab must read this.
- See **TkTeach.md** for details on how to label the 2D class images. Any person who is helping to label the data must read this.
- See the *Requirements For Data* section at the end of this document for suggestions on how much, what kind, and the range of quality for the data you choose.

Please make sure you have **Python 3** available (this program was tested in Python 3.8.3). Python library requirements are in `requirements.txt`. *We recommend creating an Anaconda environment with Python 3.8.3 and `requirements.txt` to avoid versioning errors.* See **ExtractMrc.md** for instructions on how to create an Anaconda environment.

The `tkteach.py` program was modified from the original program written by [rmones](https://github.com/rmones/tkteach) under the Apache License 2.0.

## High-Level Overview

The end goal of these programs is to allow you to conveniently manually label each image in your datasets, while getting all necessary data and metadata in the background for use in training the classification algorithm. Each image may be graded as A, B, C, D, or F; we would like each image to be graded multiple times to reduce bias from subjectivity. The hope is that this algorithm can replace the 'Select 2D' step in your processing workflows. 

The *data extraction* and *labeling* workflows are divided into two files:

- `extract_mrc.py` will automatically extract MRC data and necessary metadata (estimated resolution, class distribution, and pixel size in Angstroms) from a "2D Class" job. It can take one or many jobs at once. **All you need to do is give it the path to a cryoSPARC 2D class averaging job**, and the program automatically transforms and organizes all the results neatly. See **ExtractMRC.md** for details.
-  `tkteach.py` will open a GUI to let you assign labels to 2D class images, which were extracted by `extract_mrc.py`. You must select a dataset (which represents one "2D Class" job), then label all the images in that dataset. See **TkTeach.md** for details.


### Workflow Overview

An overview of the whole workflow is as follows. The first 3 steps cover the data extraction process. ***If you are only labeling the data, skip to Step 4***. Again, read the relevant Markdown files **ExtractMrc.md** (steps 1-3) and **TkTeach.md** (step 4) for more detailed instructions on each part of the process.

1. **Setup**: Download the `ClassAvgLabeling` folder from the OneDrive onto your own Linux machine.
2. **Extract the data**: On your own machine, run `extract_mrc.py`, passing in your chosen list of "2D Class" jobs. This will produce folders `images` and `metadata` in a location of your choice (*This only needs to be run once per job*). You can run `extract_mrc.py` multiple times instead of all at once, provided you give it the same output location. See **ExtractMRC.md** for details.
3. **Move data to shared drive**: Copy the resulting `imgaes` and `metadata` folders into your lab's home folder on the shared OneDrive (e.g., `LanderData`).
4. **Begin assigning labels**: on the shared OneDrive, run `tkteach.py`, passing in as command line arguments: the lab's home folder, and your organizational email (to uniquely identify users). You may also run `tkteach.py` on other labs' data. See **TkTeach.md** for details. We would like each labeler to label all uploaded images, including those from other labs.
5. **Finish**: Once your 2D class images have each been labeled by each labeler, your task is done. I will then download everything and begin training. 

## Requirements For Data (IMPORTANT!)

All users responsible for extracting data must read this.

- **For each project, please select the first, middle, and last iterations of "2D Class" jobs for extraction**. This provides a good balance of low, medium, and high quality images, for the same particle structure.
- **We want 3,000-4,000 images per lab**, for about 10,000 total images. This requires 30-40 "2D Class" jobs per lab, assuming 100 images per job. 
- **We would like each labeler to run through all 10,000 images**. Since this is a tedious task, `tkteach.py` will automatically save your answers, and you may close the program at any time and return to it later. See **TkTeach.md** for details.
- Inside a "2D Class" job folder, the program requires the following files:
     - `JXXX_YYY_class_averages.mrc` for MRC image data
     - `JXXX_YYY_class_averages.cs` for class average metadata
     - `JXXX_YYY_particles.cs` for particle metadata
    with 'YYY' being the highest iteration. **If you need to, you can make a 'fake' job folder containing only these three files**, and pass it to the program as a `--job-dir`. All processes would still run correctly. See **ExtractMRC.md** for more details on how to extract data.
