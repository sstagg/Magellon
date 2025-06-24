import os
from enum import Enum
import mrcfile
import glob
import matplotlib.pyplot as plt
import re
from pydantic import BaseModel, Field
from typing import List, Optional

# Set up directories
current_directory = os.getcwd()
Project2DDirectory = os.path.join(current_directory, '2dclass_evaluator')
UploadsDirectory = os.path.join(current_directory, os.getenv('UPLOAD_DIR', 'uploads'))


class SelectedValue(str, Enum):
    cryo = "cryo"
    relion = "relion"


class Item(BaseModel):
    updated: bool
    oldValue: Optional[float] = Field(None, description="The previous value")
    newValue: Optional[int] = Field(None, description="The new value if updated")


class Payload(BaseModel):
    uuid: str
    selectedValue: str
    items: List[Item]


def getrelionfiles(directory_path):
    if not os.path.isdir(directory_path):
        raise ValueError(f"The provided path '{directory_path}' is not a directory.")

    mrcsFilePath = None
    starFilePath = None

    for fileName in os.listdir(directory_path):
        if fileName.lower().endswith('.mrcs'):
            mrcsFilePath = os.path.join(directory_path, fileName)
        elif fileName.lower().endswith('.star'):
            starFilePath = os.path.join(directory_path, fileName)

        if mrcsFilePath and starFilePath:
            break

    if not mrcsFilePath:
        raise FileNotFoundError("No .mrcs file found in the provided directory.")
    if not starFilePath:
        raise FileNotFoundError("No .star file found in the provided directory.")

    print(mrcsFilePath, starFilePath)
    return mrcsFilePath, starFilePath


def getCommand(selected_value, uuid):
    folder_name = f"{selected_value}_{uuid}"
    try:
        if selected_value == SelectedValue.cryo:
            return ' '.join([
                os.path.join(Project2DDirectory, "CNNTraining", "cryosparc_2DavgAssess.py"),
                "-i", os.path.join(UploadsDirectory, folder_name),
                "-o", os.path.join(UploadsDirectory, folder_name, "outputs", "output"),
                "-w", os.path.join(Project2DDirectory, "CNNTraining", "final_model", "final_model_cont.pth")
            ])
        elif selected_value == SelectedValue.relion:
            mrcs_file, star_file = getrelionfiles(os.path.join(UploadsDirectory, folder_name))
            return ' '.join([
                os.path.join(Project2DDirectory, "CNNTraining", "relion_2DavgAssess.py"),
                "-i", mrcs_file,
                "-m", star_file,
                "-w", os.path.join(Project2DDirectory, "CNNTraining", "final_model", "final_model_cont.pth")
            ])
    except Exception as e:
        raise RuntimeError(f"Failed to generate command for {selected_value}: {str(e)}")


def getMrcsFileName(path, file_pattern):
    try:
        file_pattern_path = os.path.join(path, file_pattern)
        matching_files = glob.glob(file_pattern_path)

        if len(matching_files) == 1:
            return matching_files[0]
        elif not matching_files:
            raise FileNotFoundError(f"No file matching pattern {file_pattern} found in {path}.")
        else:
            raise ValueError(f"Multiple files match pattern {file_pattern} in {path}. Please refine the pattern.")
    except Exception as e:
        raise RuntimeError(f"Error while searching for file: {str(e)}")


async def getImageFilePaths(uuid, outputImageDir, selectedValue):
    imageFilepaths = []
    try:
        if selectedValue == SelectedValue.cryo:
            fileName = getMrcsFileName(os.path.join(UploadsDirectory, uuid, "outputs", "output"), '*_classes.mrcs')
        elif selectedValue == SelectedValue.relion:
            fileName = getMrcsFileName(os.path.join(UploadsDirectory, uuid), '*_magellon_classes.mrcs')
        else:
            raise ValueError(f"Unsupported selected value: {selectedValue}")

        filePath = os.path.join(UploadsDirectory, uuid, "outputs", "output", fileName)
        with mrcfile.open(filePath, mode='r') as mrc:
            data = mrc.data
            for i in range(data.shape[0]):
                relative_path = os.path.join(*outputImageDir.split(os.sep)[-3:])
                imageDir = os.path.join("/images", relative_path)
                output_file_path = os.path.join(outputImageDir, f'slice_{i}.jpg')
                plt.imshow(data[i], cmap='gray')
                plt.savefig(output_file_path)
                plt.close()
                imageFilepaths.append(os.path.join(imageDir, f'slice_{i}.jpg'))

    except FileNotFoundError as e:
        print(f"File error: {e}")
    except PermissionError as e:
        print(f"Permission error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return imageFilepaths


async def getClassifiedOutputValues(uuid, selectedValue):
    try:
        if selectedValue == SelectedValue.cryo:
            pattern = r'\d{5}@.*\s(\d+\.\d+|nan)'
            fileName = getMrcsFileName(os.path.join(UploadsDirectory, uuid, "outputs", "output"), '*_model.star')
            searchFile = os.path.join(UploadsDirectory, uuid, "outputs", "output", fileName)
        elif selectedValue == SelectedValue.relion:
            pattern = r"@[^\t]*\t.*\t([0-9.]+|nan)$"
            fileName = getMrcsFileName(os.path.join(UploadsDirectory, uuid), '*_magellon_model.star')
            searchFile = os.path.join(UploadsDirectory, uuid, fileName)
        else:
            raise ValueError(f"Unsupported selected value: {selectedValue}")

        extracted_values = []
        with open(searchFile, 'r') as file:
            for line in file.readlines():
                match = re.search(pattern, line)
                if match:
                    value = match.group(1)
                    extracted_values.append(None if value.lower() == 'nan' else round(float(value), 3))
        return extracted_values

    except FileNotFoundError as e:
        raise RuntimeError(f"Classification file not found: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error extracting classification values: {str(e)}")
