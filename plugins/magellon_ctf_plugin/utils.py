import os
from typing import Optional,List
# from model import CtfInput
import subprocess

from core.model_dto import CryoEmCtfTaskData

# from loggerSetup import setupLogger
# logger=setupLogger()
def getSubCommand(attribute: str, value: Optional[str] = None) -> List[str]:
    return [attribute, value] if value is not None else [attribute]

# echo -e "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc\ndiagnostic_output.mrc\n1.0\n300.0\n2.70\n0.07
# \n512\n30.0\n5.0\n5000.0\n50000.0\n100.0\nno\nno\nno\nno\nno\nno\n" | ./ctffind

def buildCtfCommand(params: CryoEmCtfTaskData) -> str:
    # ctf_file=os.environ.get("CTF_ESTIMATION_FILE")
    ctf_file=os.environ.get("CTF_ESTIMATION_FILE")
    values = [
        params.inputFile or "None",
        params.outputFile or "output.mrc",
        str(params.pixelSize) if params.pixelSize is not None else "1.0",
        str(params.accelerationVoltage) if params.accelerationVoltage is not None else "300.0",
        str(params.sphericalAberration) if params.sphericalAberration is not None else "2.70",
        str(params.amplitudeContrast) if params.amplitudeContrast is not None else "0.07",
        str(params.sizeOfAmplitudeSpectrum) if params.sizeOfAmplitudeSpectrum is not None else "512",
        str(params.minimumResolution) if params.minimumResolution is not None else "30.0",
        str(params.maximumResolution) if params.maximumResolution is not None else "5.0",
        str(params.minimumDefocus) if params.minimumDefocus is not None else "5000.0",
        str(params.maximumDefocus) if params.maximumDefocus is not None else "50000.0",
        str(params.defocusSearchStep) if params.defocusSearchStep is not None else "100.0",
        "no","no","no","no","no"
        # "no" if not params.isastigmatismPresent else "yes",
        # "no" if not params.slowerExhaustiveSearch else "yes",
        # "no" if not params.restraintOnAstogmatism else "yes",
        # "no" if not params.FindAdditionalPhaseShift else "yes",
        # "no" if not params.setExpertOptions else "yes",
    ]
    return f'echo -e "{chr(10).join(values)}" | {ctf_file}'


async def getFileContents(file_path:str)->str:
    try:
        with open(file_path, "r") as file:
            file_contents = file.read()

        return file_contents
    except Exception as e:
        errorMessage = f"Error reading file {file_path}: {e}"
        raise Exception(errorMessage)

async def readLastLine(file_path:str)->str:
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
            if lines:
                last_line = lines[-1].strip()
                values = last_line.split(" ")
                return values
            else:
                return None
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

async def GenerateOneDPlots(file_path:str)->str:
    current_directory = os.getcwd()
    command=f"{current_directory}/ctffind_plot_results.sh {file_path}"
    process = subprocess.Popen(
        command,
        cwd=current_directory,
        shell=False,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    output, error_output = process.communicate()
    return_code = process.returncode
    if return_code != 0:
        logger.error("Error output: %s", error_output)
        
        errorMessage = f"Error while generating 1D path {file_path}: {error_output}"
        raise Exception(errorMessage)
    outputFileName="".join(file_path.split(".")[:-1])
    return f"{current_directory}/{outputFileName}.pdf"
        
    
