import os
from enum import Enum
current_directory = os.getcwd()
sandbox_directory = os.path.dirname(os.path.dirname(current_directory))
Project2DDirectory = os.path.join(sandbox_directory, '2dclass_evaluator')
UploadsDirectory=os.path.join(os.getcwd(),'')

class SelectedValue(str, Enum):
    cryo = "cryo"
    relion = "relion"


def getrelionfiles(directory_path):
    # Ensure the provided path is a directory
    if not os.path.isdir(directory_path):
        raise ValueError(f"The provided path '{directory_path}' is not a directory.")

    mrcsFilePath = None
    starFilePath = None

    # Iterate through the files in the directory
    for fileName in os.listdir(directory_path):
        if fileName.lower().endswith('.mrcs'):
            mrcsFilePath = os.path.join(directory_path, fileName)
        elif fileName.lower().endswith(('.star')):
            starFilePath = os.path.join(directory_path, fileName)

        # Stop searching once both files are found
        if mrcsFilePath and starFilePath:
            break

    # Check if both files were found
    if not mrcsFilePath:
        raise FileNotFoundError("No .mrcs file found in the provided directory.")
    if not starFilePath:
        raise FileNotFoundError("No .star file found in the provided directory.")

    return mrcsFilePath, starFilePath


def getCommand(type,uuid):
    if type==SelectedValue.cryo:
        # CNNTraining/cryosparc_2DavgAssess.py -i /path/to/cryosparc_project_directories/CS-job/J8 -o P147_W1_J8 -w /path/to/Magellon/Sandbox/2dclass_evaluator/CNNTraining/final_model/final_model_cont.pt 
        return ' '.join([os.path.join(Project2DDirectory,"CNNTraining","cryosparc_2DavgAssess.py"),"-i",os.path.join(os.getcwd(),"uploads",uuid),"-o",os.path.join(os.getcwd(),"uploads",uuid,"outputs","output"),"-w",os.path.join(Project2DDirectory,"CNNTraining","final_model","final_model_cont.pth")])
    if type==SelectedValue.relion:
        mrcsfile,starfile=getrelionfiles(os.path.join(os.getcwd(),"uploads",uuid))
        return ' '.join([os.path.join(Project2DDirectory,"CNNTraining","relion_2DavgAssess.py"),"-i",mrcsfile,"-m",starfile,"-w",os.path.join(Project2DDirectory,"CNNTraining","final_model","final_model_cont.pth")])


    elif type==SelectedValue.relion:
        return 


