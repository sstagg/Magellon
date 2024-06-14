import re
import logging
from typing import Optional,List
import os
import platform
import subprocess
# from loggerSetup import setupLogger
from core.model_dto import CryoEmMotionCorTaskData
# logger=setupLogger()
logger = logging.getLogger(__name__)
def getSubCommand(attribute: str, value: Optional[str] = None) -> List[str]:
    return [attribute, value] if value is not None else [attribute]
    
def build_motioncor3_command(params: CryoEmMotionCorTaskData) -> str:
    cmd=[os.environ.get("MOTIONCORFILE")]
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
    # if params.FmIntFile is not None:
    #     cmd.append('-FmIntFile')
    #     cmd.append(params.FmIntFile)
    # if params.EerSampling is not None:
    #     cmd.append('-EerSampling')
    #     cmd.append(str(params.EerSampling))
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


def isFilePresent(directory, fileName):
    filePath = os.path.join(directory, fileName)
    return os.path.isfile(filePath)

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
