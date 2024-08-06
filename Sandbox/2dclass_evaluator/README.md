# Automatic Deep Learning Based 2D Class Average Evaluator 

This project contains everything used to train and evaluate a deep learning neural network that can take in a 2D class average (or several at once) along with some metadata and output a "grade" for each one. This automates the process of selecting good class averages.

This is an alternative to 2DAssess (Cianfrocco lab; Li et al. 2020) and the class average evaluator offered in RELION 4.0 called Class Ranker (Scheres lab; Kimanius et al. 2021). 2DAssess simply worked on the image data whereas Class Ranker used both image data and associated RELION meta-data. Class Ranker performed better than 2DAssess, however, its use was restricted to RELION-generated class averages. 

Our new 2D class average evaluator builds on both of these software to evaluate 2D averages and associated meta data from either RELION or cryoSPARC class averages. The end product is a pyTorch model stored in `CNNTraining/final_model/final_model.pth`.  It was trained on a combined dataset consisting of the 26389 images from the Cianfrocco, Lander, and Stagg labs. 

Neural network architecting & software: Keenan Hom (Lander Lab)

Data labeling: Cianfrocco, Lander, Stagg labs

## 2D class average evaluation using pre-trained assessing tool

### Software installation

To install software for using the pre-trained model, you will need download this Github repo, create a conda environment, and then install python dependencies. 

    $ git clone https://github.com/sstagg/Magellon
    $ conda create -n magellon2DAssess python=3.12
    $ conda activate magellon2DAssess
    $ pip3 install -r /path/to/Magellon/Sandbox/2dclass_evaluator/requirements.txt

### RELION 2D averages 
To assess RELION 2D average quality with the pre-trained model, run the following script: 

    CNNTraining/relion_2DavgAssess.py 
    Usage: relion_2DavgAssess.py -i <RELION .mrcs avgs> -m <RELION model.star file>

    Assess RELION 2D class averages
    
    Options:
    -h, --help              show this help message and exit
    -i FILE, --input=FILE
                            RELION stack of class averages (.mrcs)
    -m FILE, --model=FILE
                            RELION model.star file associated with 2D averages
    -w FILE, --weights=FILE 
                            Pre-trained neural network weights file (e.g.,
                            final_model_cont.pth)

Example usage:

    $ CNNTraining/relion_2DavgAssess.py -i Class2D/job013/run_it025_classes.mrcs -m Class2D/job013/run_it025_model.star  -w /path/to/Magellon/Sandbox/2dclass_evaluator/CNNTraining/final_model/final_model_cont.pt

The output will be files with the name `magellon` in them. For the above example, the output files would be: 
* Class2D/job013/run_it025_magellon_model.star
* Class2D/job013/run_it025_magellon_classes.mrcs
* Class2D/job013/run_it025_magellon_data.star 

You can visualize and sort the class averages based on the Magellon 2D Assessing score. 

    $ relion_display --i Class2D/job013/run_it025_magellon_model.star --gui

    > Check box "Sort images on:"
    > Select "rlnClassPriorOffsetY"
    > Check box "Display label?"

Above each average will be the Magellon 2D Assessing score. 

### cryoSPARC 2D averages
To assess cryoSPARC 2D averages, run the following script: 

    CNNTraining/cryosparc_2DavgAssess.py
    Usage: cryosparc_2DavgAssess.py -i <cryoSPARC job dir> -w <weights file>

    Assess cryoSPARC 2D class averages

    Options:
    -h, --help            show this help message and exit
    -i DIRECTORY, --input=DIRECTORY
                            cryoSPARC job directory
    -o DIRECTORY, --output=DIRECTORY
                            Output directory
    -w FILE, --weights=FILE
                            Pre-trained neural network weights file (e.g.,
                            final_model_cont.pth)
    Usage: cryosparc_2DavgAssess.py -i <cryoSPARC job dir> -w <weights file>

Example usage: 

    CNNTraining/cryosparc_2DavgAssess.py -i /path/to/cryosparc_project_directories/CS-job/J8 -o P147_W1_J8 -w /path/to/Magellon/Sandbox/2dclass_evaluator/CNNTraining/final_model/final_model_cont.pt 

The output directory will contain the scores per average in the "_model.star" file. You can visualize and sort the class averages based on the Magellon 2D Assessing score. 

    $ relion_display --i P147_W1_J8/J8_040_class_averages_model.star --gui

    > Check box "Sort images on:"
    > Select "rlnClassPriorOffsetY"
    > Check box "Display label?"

