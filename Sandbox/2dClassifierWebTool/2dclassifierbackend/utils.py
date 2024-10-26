import os
from enum import Enum
import mrcfile
import glob
import matplotlib.pyplot as plt
import re
from pydantic import BaseModel, Field
from typing import List, Optional
current_directory = os.getcwd()
Project2DDirectory = os.path.join(current_directory, '2dclass_evaluator')
UploadsDirectory=os.path.join(os.getcwd(),'uploads')

class SelectedValue(str, Enum):
    cryo = "cryo"
    relion = "relion"

class Item(BaseModel):
    updated: bool
    oldValue: Optional[float] = Field(None, description="The previous value")
    newValue: Optional[int] = Field(None, description="The new value if updated")

class Payload(BaseModel):
    uuid: str
    items: List[Item]

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


def getCommand(selected_value,uuid):
    if selected_value == SelectedValue.cryo:
        return ' '.join([
            os.path.join(Project2DDirectory, "CNNTraining", "cryosparc_2DavgAssess.py"),
            "-i", os.path.join(UploadsDirectory, uuid),
            "-o", os.path.join(UploadsDirectory, uuid, "outputs", "output"),
            "-w", os.path.join(Project2DDirectory, "CNNTraining", "final_model", "final_model_cont.pth")
        ])
    elif selected_value == SelectedValue.relion:
        mrcs_file, star_file = getrelionfiles(os.path.join(UploadsDirectory, uuid))
        return ' '.join([
            os.path.join(Project2DDirectory, "CNNTraining", "relion_2DavgAssess.py"),
            "-i", mrcs_file,
            "-m", star_file,
            "-w", os.path.join(Project2DDirectory, "CNNTraining", "final_model", "final_model_cont.pth")
        ])
    

def getMrcsFileName(path,file_pattern):
    file_pattern_path = os.path.join(path, file_pattern)
    matching_files = glob.glob(file_pattern_path)
    if len(matching_files) == 1:
        return matching_files[0]   
    elif len(matching_files) == 0:
        raise FileNotFoundError(f"No file matching the pattern {file_pattern} was found.")
    else:
        raise ValueError(f"Multiple files match the pattern {file_pattern}. Please refine your pattern.")


async def getImageFilePaths(uuid,outputImageDir,selectedValue):
    imageFilepaths=[]
    try:
        if selectedValue==SelectedValue.cryo:
            fileName=getMrcsFileName(os.path.join(UploadsDirectory,uuid,"outputs","output"),'*_classes.mrcs')
            
        if selectedValue==SelectedValue.relion:
            fileName=getMrcsFileName(os.path.join(UploadsDirectory,uuid),'*_magellon_classes.mrcs')
        
        with mrcfile.open(os.path.join(UploadsDirectory,uuid,"outputs","output",fileName), mode='r') as mrc:
            data = mrc.data
            for i in range(data.shape[0]):
                relative_path = os.path.join(*outputImageDir.split(os.sep)[-3:])
                imageDir=os.path.join("/images",relative_path)
                output_file_path = os.path.join(outputImageDir, f'slice_{i}.png')
                plt.imshow(data[i], cmap='gray')
                plt.savefig(output_file_path)
                plt.close()
                imageFilepaths.append(os.path.join(imageDir, f'slice_{i}.png'))
    except FileNotFoundError as e:
        print(f"Error: {e}. Please check the file paths and ensure the required files are available.")
    except PermissionError as e:
        print(f"Permission denied: {e}. Please check your permissions for the output directory.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return imageFilepaths


async def getClassifiedOutputValues(uuid,selectedValue):
    if selectedValue==SelectedValue.cryo:
        pattern = r'\d{5}@.*\s(\d+\.\d+)'
        fileName=getMrcsFileName(os.path.join(UploadsDirectory,uuid,"outputs","output"),'*_model.star')
        searchFolder=os.path.join(UploadsDirectory,uuid,"outputs","output",fileName)
    if selectedValue==SelectedValue.relion:
        pattern = r"@[^\t]*\t.*\t([0-9.]+)$"
        fileName=getMrcsFileName(os.path.join(UploadsDirectory,uuid),'*_magellon_model.star')
        searchFolder=os.path.join(UploadsDirectory,uuid,fileName)
    extracted_values = []

    with open(searchFolder, 'r') as file:
        lines = file.readlines()
    for line in lines:
        match = re.search(pattern, line)
        if match:
            extracted_values.append(round(float(match.group(1)), 3))
    return extracted_values
