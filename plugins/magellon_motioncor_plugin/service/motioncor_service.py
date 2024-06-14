import logging
import math
import os
import subprocess
import concurrent.futures
from utils import build_motioncor3_command,getFrameAlignment,getPatchFrameAlignment,isFilePresent,getRequirements,getFilecontentsfromThread

from core.model_dto import CryoEmMotionCorTaskData


logger = logging.getLogger(__name__)


async def do_motioncor(params: CryoEmMotionCorTaskData):
    try:
        command = build_motioncor3_command(params)
        logger.info("Command: %s", command)
        fileName = ""
        if params.InMrc is not None:
            fileName, _ = os.path.splitext(params.InMrc)
        if params.InEer is not None:
            fileName, _ = os.path.splitext(params.InEer)
        if params.InTiff is not None:
            fileName, _ = os.path.splitext(params.InTiff)
        current_directory = os.getcwd()
        process = subprocess.run(
            f'{current_directory}/{command}',
            wd=os.getcwd(),
            shell=True,
            text=True,
            check=False,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = process.stdout.strip()
        error_output = process.stderr.strip()
        return_code = process.returncode
        if return_code != 0:
            logger.error("Error output: %s", error_output)
        #     executeMethodFailure.inc()
            return(f"Error output: {error_output}")
        outputSuccessResult={
             "message": "MotionCor process completed successfully", 
        }
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            if(isFilePresent(current_directory,f'{fileName}-Full.log')):            
                outputSuccessResult["frameAlignmet"]=getFilecontentsfromThread(getFrameAlignment, f'{current_directory}/{fileName}-Full.log',executor)
            if(isFilePresent(current_directory,f'{fileName}-Patch-Frame.log')):
                outputSuccessResult["patchFrameAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{current_directory}/{fileName}-Patch-Frame.log',executor)
            if(isFilePresent(current_directory,f'{fileName}-Patch-Full.log')):
                outputSuccessResult["patchFullAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{current_directory}/{fileName}-Patch-Full.log',executor)
            if(isFilePresent(current_directory,f'{fileName}-Patch-Patch.log')):
                outputSuccessResult["patchAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{current_directory}/{fileName}-Patch-Patch.log',executor)
        
        outputMrcs=[f'{current_directory}/{params.OutMrc}']
        values=params.OutMrc.split("/")
        values[-1]="output_DW.mrc"
        fileNameDW="/".join(values)
        if isFilePresent(current_directory, fileNameDW):
            outputMrcs.append(f'{current_directory}/{fileNameDW}')
        outputSuccessResult["outputMrcs"]=outputMrcs
    except subprocess.CalledProcessError as e:
        logger.error("Error running executable: %s", e)
        # executeMethodFailure.inc()
        # executeMethodSuccess.inc()
        return {
        "data":outputSuccessResult
        }
    except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            logger.error(error_message)
            return {
                "status_code": 500,
                "error_message": error_message
            }