import re
import logging
from typing import Optional,List
import os
import platform
import subprocess
import mrcfile
import numpy as np
import matplotlib.pyplot as plt
# from loggerSetup import setupLogger
from core.model_dto import CryoEmMotionCorTaskData
from PIL import Image
import tifffile
# logger=setupLogger()
logger = logging.getLogger(__name__)
def getSubCommand(attribute: str, value: Optional[str] = None) -> List[str]:
    return [attribute, value] if value is not None else [attribute]
    
def build_motioncor3_command(params: CryoEmMotionCorTaskData) -> str:
    # cmd=[os.environ.get("MOTIONCORFILE")]
    cmd=["MotionCor2_1.6.4_Cuda121_Mar312023"]
    # cmd = ['motioncor3']
    if params.InMrc is not None:
        cmd+=getSubCommand("-InMrc",params.InMrc)
    if params.InTiff is not None:
        cmd+=getSubCommand('-InTiff',params.InTiff)
    if params.InEer is not None:
        cmd+=getSubCommand('-InEer',params.InEer)
    # if params.InSuffix is not None:
        # cmd+=getSubCommand('-InSuffix',params.InSuffix)
    if params.OutMrc is not None:
        cmd+=getSubCommand('-OutMrc',params.OutMrc)
    else:
        cmd+=getSubCommand('-OutMrc',"output.mrc")
    # if params.ArcDir is not None:
        # cmd+=getSubCommand('-ArcDir',params.ArcDir)
    if params.Gain is not None:
        cmd+=getSubCommand('-Gain',params.Gain)
    if params.Dark is not None:
        cmd+=getSubCommand('-Dark',params.Dark)
    if params.DefectFile is not None:
        cmd+=getSubCommand('-DefectFile',params.DefectFile)
    # if params.InAln is not None:
        # cmd+=getSubCommand('-InAln',params.InAln)
    # if params.OutAln is not None:
        # cmd+=getSubCommand('-OutAln',params.OutAln)
    if params.DefectMap is not None:
        cmd+=getSubCommand('-DefectMap',params.DefectMap)
    # if params.Serial is not None:
        # cmd+=getSubCommand('-Serial',params.Serial)
    # if params.FullSum is not None:
    #     cmd+=getSubCommand('-FullSum',params.FullSum)
    if params.PatchesX is not None and params.PatchesY is not None:
        cmd+=getSubCommand('-Patch',f'{params.PatchesX} {params.PatchesY}')
    if params.Iter is not None:
        cmd+=getSubCommand('-Iter',str(params.Iter))
    else:
        cmd+=getSubCommand('-Iter','5')
    if params.Tol is not None:
        cmd+=getSubCommand('-Tol',str(params.Tol))
    else:
        cmd+=getSubCommand('-Tol','0.5')
    if params.Bft is not None:
        cmd+=getSubCommand('-Bft',str(params.Bft))
    else:
        cmd+=getSubCommand('-Bft','100')
    # if params.PhaseOnly is not None:
        # cmd+=getSubCommand('-PhaseOnly',str(params.PhaseOnly))
    # else:
        # cmd+=getSubCommand('-PhaseOnly','0')
    # if params.TmpFile is not None:
        # cmd+=getSubCommand('-TmpFile',params.TmpFile)
    if params.LogDir is not None:
        cmd+=getSubCommand('-LogDir',params.LogDir)
    else:
        cmd+=getSubCommand('-LogDir',".")
    if params.Gpu is not None:
        cmd+=getSubCommand('-Gpu','0')
    #stackz not available 
    # if params.StackZ is not None:
        # cmd+=getSubCommand('-StackZ',params.StackZ)
    if params.FtBin is not None:
        cmd+=getSubCommand('-FtBin',str(params.FtBin))
    else:
        cmd+=getSubCommand('-FtBin','2')
    #init Dose
    # if params.InitDose is not None:
    #     cmd.append('-InitDose')
    #     cmd.append(params.InitDose)
    if params.FmDose:
        cmd+=getSubCommand('-FmDose',str(params.FmDose))
    if params.PixSize:
        cmd+=getSubCommand('-PixSize',str(params.PixSize))
    if params.kV is not None:
        cmd+=getSubCommand('-kV',str(params.kV))
    else:
        cmd+=getSubCommand('-kV','300')
    if params.Cs is not None:
        cmd+=getSubCommand('-Cs',str(params.Cs))
    else:
        cmd+=getSubCommand('-Cs','0')
    if params.AmpCont is not None:
        cmd+=getSubCommand('-AmpCont',str(params.AmpCont))
    else:
        cmd+=getSubCommand('-AmpCont','0.07')
    if params.ExtPhase is not None:
        cmd+=getSubCommand('-ExtPhase',str(params.ExtPhase))
    else:
        cmd+=getSubCommand('-ExtPhase','0')
    #Align need to check how to pass the variables
    # if params.Align is not None:
    #     cmd.append('-Align')
    #     cmd.append(str(params.Align))
    # if params.Throw is not None:
    #     cmd.append('-Throw')
    #     cmd.append(str(params.Throw))
    # else:
    #     cmd.append('-Throw')
    #     cmd.append('0')
    # if params.Trunc is not None:
    #     cmd.append('-Trunc')
    #     cmd.append(str(params.Trunc))
    # else:
    #     cmd.append('-Trunc')
    #     cmd.append('0')
    #sumRange how the values need to be passed
    if params.SumRangeMinDose is not None and params.SumRangeMaxDose is not None:
        cmd.append('-SumRange')
        cmd.append(f'{params.SumRangeMinDose} {params.SumRangeMaxDose}')

    if params.Group is not None:
        cmd.append('-Group')
        cmd.append(str(params.Group))
    #Group how the values need to be passed
    # if params.GroupGlobalAlignment is not None and params.GroupPatchAlignment is not None:
    #     cmd.append('-Group')
    #     cmd.append(f'{params.GroupGlobalAlignment} {params.GroupPatchAlignment}')
    #FmRef need to chek how to pass the reference
    # if params.FmRef is not None:
    #     cmd.append('-FmRef')
    #     cmd.append(str(params.FmRef))
    # #tilt not mentioned
    # if params.Tilt is not None:
    #     cmd.append('-Tilt')
    #     cmd.append(params.Tilt)
    # #crop how the size being passed
    # if params.Crop is not None:
    #     cmd.append('-Crop')
    #     cmd.append(params.Crop)
    # if params.OutStackAlignment is not None and params.OutStackZbinning is not None:
    #     cmd.append('-OutStack')
    #     cmd.append(f'{params.OutStackAlignment} {params.OutStackZbinning}')
    if params.RotGain is not None:
        cmd+=getSubCommand('-RotGain',str(params.RotGain))
    else:
        cmd+=getSubCommand('-RotGain',"0")
    if params.FlipGain is not None:
        cmd+=getSubCommand('-FlipGain',str(params.FlipGain))
    else:
        cmd+=getSubCommand('-FlipGain','0')
    if params.InvGain is not None:
        cmd+=getSubCommand('-InvGain',str(params.InvGain))
    # if params.MagMajoraxes is not None and params.MagMinoraxes is not None and params.MagAngle is not None:
    #     cmd.append('-Mag')
    #     cmd.append(f'{params.MagMajoraxes} {params.MagMinoraxes} {params.MagAngle}')
    # if params.InFmMotion is not None:
    #     cmd.append('-InFmMotion')
    #     cmd.append(str(params.InFmMotion))
    
    # if params.GpuMemUsage is not None:
    #     cmd.append('-GpuMemUsage')
    #     cmd.append(str(params.GpuMemUsage))
    # else:
    #     cmd.append('-GpuMemUsage')
    #     cmd.append('0.5')
    # if params.UseGpus is not None:
    #     cmd.append('-UseGpus')
    #     cmd.append(str(params.UseGpus))
    # if params.SplitSum:
    #     cmd.append('-SplitSum')
        # cmd.append(params.SplitSum)
    if params.FmIntFile is not None:
        cmd+=getSubCommand("-FmIntFile",params.FmIntFile)
    if params.EerSampling is not None:
        cmd+=getSubCommand('-EerSampling',str(params.EerSampling))
    else:
        cmd+=getSubCommand('-EerSampling',"1")
    # if params.OutStar:
    #     cmd.append('-OutStar')
    #     cmd.append('1')
    # if params.TiffOrder is not None:
    #     cmd.append('-TiffOrder')
    #     cmd.append(str(params.TiffOrder))
    # if params.CorrInterp is not None:
    #     cmd.append('-CorrInterp')
    #     cmd.append(str(params.CorrInterp))
    return ' '.join(cmd)


def getFrameAlignment(fileName):
    try:
        data = []
        with open(fileName, "r") as file:
            for line in file:
                values = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                if len(values) == 3:
                    row = [float(value) for value in values]
                    data.append(row)

        return data
    
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {fileName}")
    except Exception as e:
        raise Exception(f"Error reading file {fileName}: {e}")

def getPatchFrameAlignment(fileName):
    try:
        result = {
            "no_of_patches": 0,
            "movie_size": [],
            "values": []
        }
        with open(fileName, "r") as file:
            for line in file:
                matchPatches = re.search(r"Number of patches:\s*(\d+)", line)
                if matchPatches:
                    result["no_of_patches"] = int(matchPatches.group(1))
                matchMovieSize = re.search(r"Movie size:\s*(\d+)\s+(\d+)\s+(\d+)", line)
                if matchMovieSize:
                    result["movie_size"] = list(map(int, matchMovieSize.groups()))
                values = re.findall(r"[-+]?\d*\.\d+|\d+", line)
                if len(values) == 6:
                    result["values"].append(list(map(float, values)))
        return result
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {fileName}")
    except Exception as e:
        raise Exception(f"Error reading file {fileName}: {e}")
    





def isFilePresent(fileName):
    return os.path.isfile(fileName)

def getRequirements(filePath):
    try:
        with open(filePath, 'r') as file:
            requirementsContent = file.read()
        requirementsList = [line.strip() for line in requirementsContent.split('\n') if line.strip()]
        return requirementsList
    except Exception as e:
       raise Exception(f"Error reading file {filePath}: {e}")

def getFilecontentsfromThread(method,filePath,executor)->list:
    try:
        process = executor.submit(method, filePath)
        return process.result()
    except Exception as e:
       raise Exception(f"Error executing the threads {method}- {filePath}: {e}")
    
def checkSystemRequirements():
    if platform.system() != "Linux":
        raise Exception("Unsupported operating system. This program requires Linux.")

def checkCudaVersion():
    try:
        nvccVersionOutput = subprocess.check_output(['nvcc', '--version'], stderr=subprocess.STDOUT)
        nvccVersionOutput = nvccVersionOutput.decode('utf-8')
        logger.info(f"nvcc version: {nvccVersionOutput}")
    
        match = re.search(r'release\s+(\d+\.\d+)', nvccVersionOutput)
        if match:
            cudaVersion = match.group(1)
        else:
            raise Exception("Unable to determine CUDA version from nvcc output.")

        logger.info(cudaVersion)
        
        # Check if CUDA version is at least 12.1
        if not cudaVersion.startswith(os.environ.get("CUDAVERSION")):
            raise Exception(f"This program requires CUDA version 12.1 or higher. Current version: {cuda_version}")

    except FileNotFoundError:
        raise Exception("nvcc compiler not found. Please install the NVIDIA CUDA Toolkit.")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error checking CUDA version: {e.output}")

def getRequirements(filePath):
    try:
        with open(filePath, 'r') as file:
            requirementsContent = file.read()
        requirementsList = [line.strip() for line in requirementsContent.split('\n') if line.strip()]
        logger.info(requirementsList)
        checkSystemRequirements()
        checkCudaVersion()
        return requirementsList

    except Exception as e:
        errorMessage = f"Error reading requirements file {filePath}: {e}"
        raise Exception(errorMessage)

def validateInput(params):
    if params.InMrc is not None:
        if not isinstance(params.InMrc, str):
            raise ValueError("InMrc must be a string or None.")
        if not params.InMrc.strip().endswith(".mrc"):
            raise ValueError("InMrc must end with .mrc.")
    
    if params.InTiff is not None:
        if not isinstance(params.InTiff, str):
            raise ValueError("InTiff must be a string or None.")
        if not params.InTiff.strip().endswith(".tif"):
            raise ValueError("InTiff must end with .tif.")
    
    if params.InEer is not None:
        if not isinstance(params.InEer, str):
            raise ValueError("InEer must be a string or None.")
        if not params.InEer.strip().endswith(".eer"):
            raise ValueError("InEer must end with .eer.")
    
    if not params.inputFile or not isinstance(params.inputFile, str) or not params.inputFile.strip():
        raise ValueError("inputFile must be a non-empty string.")
    
    if params.OutMrc is not None:
        if not isinstance(params.OutMrc, str):
            raise ValueError("OutMrc must be a string or None.")
        if not params.OutMrc.strip().endswith(".mrc"):
            raise ValueError("OutMrc must end with .mrc.")
    
    if params.outputFile is not None:
        if not isinstance(params.outputFile, str):
            raise ValueError("outputFile must be a string or None.")
        if not params.outputFile.strip().endswith(".mrc"):
            raise ValueError("outputFile must end with .mrc.")
    
    if not params.Gain or not isinstance(params.Gain, str) or not params.Gain.strip():
        raise ValueError("Gain must be a non-empty string.")
    
    if params.Dark is not None and not isinstance(params.Dark, str):
        raise ValueError("Dark must be a string or None.")
    
    if params.DefectFile is not None and not isinstance(params.DefectFile, str):
        raise ValueError("DefectFile must be a string or None.")
    
    if not isinstance(params.PatchesX, int) or params.PatchesX <= 0:
        raise ValueError("PatchesX must be a positive integer.")
    
    if not isinstance(params.PatchesY, int) or params.PatchesY <= 0:
        raise ValueError("PatchesY must be a positive integer.")
    
    if params.Iter is not None:
        if not isinstance(params.Iter, int):
            raise ValueError("Iter must be a positive integer or None.")
        if params.Iter <= 0:
            raise ValueError("Iter must be a positive integer.")

    if params.Tol is not None:
        if not isinstance(params.Tol, (float, int)):
            raise ValueError("Tol must be a positive integer or None.")
        if params.Tol <= 0:
            raise ValueError("Tol must be a positive integer.")

    if params.Bft is not None:
        if not isinstance(params.Bft, int):
            raise ValueError("Bft must be a positive integer or None.")
        if params.Bft <= 0:
            raise ValueError("Bft must be a positive integer.")
    
    if params.LogDir is not None:
        if not isinstance(params.LogDir, str):
            raise ValueError("LogDir must be a string or None.")
    
    if params.Gpu is not None:
        if not isinstance(params.Gpu, str):
            raise ValueError("Gpu must be a string or None example '0'.")

    if params.FtBin is not None:
        if not isinstance(params.FtBin, (float, int)):
            raise ValueError("FtBin must be a positive integer or None.")
        if params.FtBin <= 0:
            raise ValueError("FtBin must be a positive integer.")
    
    if params.FmDose is not None and not isinstance(params.FmDose, (float, int)):
        raise ValueError("FmDose must be a number or None.")
    
    if params.PixSize is not None and not isinstance(params.PixSize, (float, int)):
        raise ValueError("PixSize must be a number or None.")
    
    if params.kV is not None:
        if not isinstance(params.kV, (int, float)):
            raise ValueError("KV must be a positive integer or None.")
        if params.kV <= 0:
            raise ValueError("KV must be a positive integer.")

    # if params.Cs is not None:
    #     if not isinstance(params.Cs, int):
    #         raise ValueError("Cs must be a positive integer or None.")
    #     if params.Cs <= 0:
    #         raise ValueError("Cs must be a positive integer.")
    
    # if params.AmpCont is not None:
    #     if not isinstance(params.AmpCont, (int, float)):
    #         raise ValueError("AmpCont must be a positive integer or None.")
    #     if params.AmpCont <= 0:
    #         raise ValueError("AmpCont must be a positive integer.")
    
    # if params.ExtPhase is not None:
    #     if not isinstance(params.ExtPhase, (int, float)):
    #         raise ValueError("ExtPhase must be a positive integer or None.")
    #     if params.ExtPhase <= 0:
    #         raise ValueError("ExtPhase must be a positive integer.")
    
    if params.SumRangeMinDose is not None:
        print(params.SumRangeMinDose)
        if not isinstance(params.SumRangeMinDose, (int, float)):
            raise ValueError("SumRangeMinDose must be a positive integer or None.")
        if params.SumRangeMinDose < 0:
            raise ValueError("SumRangeMinDose must be a positive integer.")

    if params.SumRangeMaxDose is not None:
        if not isinstance(params.SumRangeMaxDose, (int, float)):
            raise ValueError("SumRangeMaxDose must be a positive integer or None.")
        if params.SumRangeMaxDose < 0:
            raise ValueError("SumRangeMaxDose must be a positive integer.")

    if params.RotGain is not None:
        if not isinstance(params.RotGain, (int, float)):
            raise ValueError("RotGain must be a positive integer or None.")
        if params.RotGain < 0:
            raise ValueError("RotGain must be a positive integer.")
    
    if params.FlipGain is not None:
        if not isinstance(params.FlipGain, (int, float)):
            raise ValueError("FlipGain must be a positive integer or None.")
        if params.FlipGain < 0:
            raise ValueError("FlipGain must be a positive integer.")
    
    if params.InvGain is not None:
        if not isinstance(params.InvGain, (int, float)):
            raise ValueError("InvGain must be a positive integer or None.")
        if params.InvGain < 0:
            raise ValueError("InvGain must be a positive integer.")
    
    return True

def createframealignImage(outputmrcpath, data, directory_path,originalsize,inputFileName):
    
    with mrcfile.open(outputmrcpath) as mrc:
        new_data = mrc.data.copy()
        original_header = mrc.header.copy()
    
    # Calculate scaling factors
    scale_y = new_data.shape[0] / originalsize[0]
    scale_x = new_data.shape[1] / originalsize[1]
    
    dot_size = max(1, int(5 * min(scale_x, scale_y)))  # Scale dot size, minimum 1 pixel
    
    # Mark the image with white dots at the scaled coordinates
    for _, x, y, deltax, deltay, _ in data:
        px = int((x + deltax * 10) * scale_x)
        py = int((y + deltay * 10) * scale_y)
        
        # Create a dot using numpy operations
        y_indices, x_indices = np.ogrid[-dot_size:dot_size+1, -dot_size:dot_size+1]
        mask = x_indices*x_indices + y_indices*y_indices <= dot_size*dot_size
        
        # Calculate boundaries for the dot
        y_start, y_end = max(0, py-dot_size), min(new_data.shape[0], py+dot_size+1)
        x_start, x_end = max(0, px-dot_size), min(new_data.shape[1], px+dot_size+1)
        
        # Apply the dot to the image
        mask_slice = mask[y_start-py+dot_size:y_end-py+dot_size, x_start-px+dot_size:x_end-px+dot_size]
        new_data[y_start:y_end, x_start:x_end][mask_slice] = np.max(new_data)
    
    normalized_data = ((new_data - np.min(new_data)) / (np.max(new_data) - np.min(new_data)) * 255).astype(np.uint8)
    img = Image.fromarray(normalized_data)
    new_filename = f"{inputFileName}_mco_two.png"
    new_filepath = os.path.join(directory_path, new_filename)
    img.save(new_filepath)
    
    # with mrcfile.new(new_filepath, overwrite=True) as new_mrc:
    #     new_mrc.set_data(new_data)
        
    #     for field in original_header.dtype.names:
    #         if field != 'map' and field != 'machst':
    #             setattr(new_mrc.header, field, original_header[field])
        
    #     new_mrc.update_header_from_data()
    #     new_mrc.update_header_stats()

    return new_filepath



def createframealignCenterImage(outputmrcpath, data, directory_path,originalsize,inputFileName):
    
    with mrcfile.open(outputmrcpath) as mrc:
        new_data = mrc.data.copy()
        original_header = mrc.header.copy()
    
    # Calculate scaling factors
    scale_y = new_data.shape[0] / originalsize[0]
    scale_x = new_data.shape[1] / originalsize[1]
    
    dot_size = max(1, int(5 * min(scale_x, scale_y)))  # Scale dot size, minimum 1 pixel
    center_x,center_y = originalsize[0] // 2, originalsize[1] // 2
    
    # Mark the image with white dots at the scaled coordinates
    for _, deltax, deltay in data:
        px = int((center_x + deltax * 10) * scale_x)
        py = int((center_y + deltay * 10) * scale_y)
        
        # Create a dot using numpy operations
        y_indices, x_indices = np.ogrid[-dot_size:dot_size+1, -dot_size:dot_size+1]
        mask = x_indices*x_indices + y_indices*y_indices <= dot_size*dot_size
        
        # Calculate boundaries for the dot
        y_start, y_end = max(0, py-dot_size), min(new_data.shape[0], py+dot_size+1)
        x_start, x_end = max(0, px-dot_size), min(new_data.shape[1], px+dot_size+1)
        
        # Apply the dot to the image
        mask_slice = mask[y_start-py+dot_size:y_end-py+dot_size, x_start-px+dot_size:x_end-px+dot_size]
        new_data[y_start:y_end, x_start:x_end][mask_slice] = np.max(new_data)
    
    normalized_data = ((new_data - np.min(new_data)) / (np.max(new_data) - np.min(new_data)) * 255).astype(np.uint8)
    img = Image.fromarray(normalized_data)
    new_filename = f"{inputFileName}_mco_one.png"
    new_filepath = os.path.join(directory_path, new_filename)
    img.save(new_filepath)
    
    # with mrcfile.new(new_filepath, overwrite=True) as new_mrc:
    #     new_mrc.set_data(new_data)
        
    #     for field in original_header.dtype.names:
    #         if field != 'map' and field != 'machst':
    #             setattr(new_mrc.header, field, original_header[field])
        
    #     new_mrc.update_header_from_data()
    #     new_mrc.update_header_stats()

    return new_filepath


def getImageSize(file,filetype):
    if filetype== ".tif" or filetype==".eer":
        with tifffile.TiffFile(file) as tif:
            width, height = tif.pages[0].shape
            return width,height
    elif filetype==".mrc":
        with mrcfile.open(file, permissive=True) as mrc:
            x_size, y_size, z_size = mrc.header.nx, mrc.header.ny, mrc.header.nz
            return x_size, y_size
    else:
        raise ValueError("Invalid file type. Must be .mrc, .tif, or .eer.")
