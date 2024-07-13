import logging
import math
import os
import subprocess
import concurrent.futures
from utils import build_motioncor3_command,getFrameAlignment,getPatchFrameAlignment,isFilePresent,getRequirements,getFilecontentsfromThread
from datetime import datetime
from core.model_dto import CryoEmMotionCorTaskData, OutputFile, TaskDto, TaskResultDto


logger = logging.getLogger(__name__)


async def do_motioncor(params: TaskDto):
    
    try:
        print(params)
        os.makedirs(f'{os.path.join(os.getcwd(),"gpfs", "outputs")}', exist_ok=True)
        directory_path = os.path.join(os.getcwd(),"gpfs", "outputs", str(params.image_id))
        params.OutMrc = f'{directory_path}/{params.OutMrc}'
        os.makedirs(directory_path, exist_ok=True)
        command = build_motioncor3_command(params)
        logger.info("Command: %s", command)
        fileName = ""
        if params.InMrc is not None:
            fileName, _ = os.path.splitext(params.InMrc)
        if params.InEer is not None:
            fileName, _ = os.path.splitext(params.InEer)
        if params.InTiff is not None:
            fileName, _ = os.path.splitext(params.InTiff)
        process = subprocess.run(
            os.path.join(os.getcwd(),command),
            cwd=os.getcwd(),
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
        inputFileName=os.path.join(os.getcwd(),fileName.split("/")[-1])
        output_data={}
        output_files=[]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            if(isFilePresent(f'{inputFileName}-Full.log')):          
                output_data["frameAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{inputFileName}-Full.log',executor)
                source_path = f'{inputFileName}-Full.log'
                base_path = "/".join(inputFileName.split("/")[:-1])
                destination_path = f'{base_path}/gpfs/outputs/{str(params.image_id)}/{os.path.splitext(os.path.basename(inputFileName))[0]}-Full.log'
                os.rename(source_path, destination_path)
                output_files.append(OutputFile(name="frameAlignment",path=destination_path,required=True))
        
            if(isFilePresent(f'{inputFileName}-Patch-Frame.log')): 
                output_data["patchFrameAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{inputFileName}-Patch-Frame.log',executor)
                source_path = f'{inputFileName}-Patch-Frame.log'
                base_path = "/".join(inputFileName.split("/")[:-1])
                destination_path = f'{base_path}/gpfs/outputs/{str(params.image_id)}/{os.path.splitext(os.path.basename(inputFileName))[0]}-Patch-Frame.log'
                os.rename(source_path, destination_path)
                output_files.append(OutputFile(name="patchFrameAlignment",path=destination_path,required=True))

            if(isFilePresent(f'{inputFileName}-Patch-Full.log')): 
                output_data["patchFullAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{inputFileName}-Patch-Full.log',executor)
                source_path = f'{inputFileName}-Patch-Full.log'
                base_path = "/".join(inputFileName.split("/")[:-1])
                destination_path = f'{base_path}/gpfs/outputs/{str(params.image_id)}/{os.path.splitext(os.path.basename(inputFileName))[0]}-Patch-Full.log'
                os.rename(source_path, destination_path)
                output_files.append(OutputFile(name="patchFullAlignment",path=destination_path,required=True))

            if(isFilePresent(f'{inputFileName}-Patch-Patch.log')): 
                output_data["patchAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{inputFileName}-Patch-Patch.log',executor)
                source_path = f'{inputFileName}-Patch-Patch.log'
                base_path = "/".join(inputFileName.split("/")[:-1])
                destination_path = f'{base_path}/gpfs/outputs/{str(params.image_id)}/{os.path.splitext(os.path.basename(inputFileName))[0]}-Patch-Patch.log'
                os.rename(source_path, destination_path)
                output_files.append(OutputFile(name="patchAlignment",path=destination_path,required=True))

        outputMrcs=[params.OutMrc]
        values=params.OutMrc.split("/")
        outputFileName=f'{".".join(values[-1].split(".")[:-1])}_DW.mrc'
        values[-1]=outputFileName
        fileNameDW="/".join(values)
        if isFilePresent( fileNameDW):
            outputMrcs.append(fileNameDW)
        outputSuccessResult["outputMrcs"]=outputMrcs
        # outputSuccessResult = TaskResultDto(
        #     # worker_instance_id=params.worker_instance_id,
        #     # task_id=params.id,
        #     # job_id=params.job_id, 
        #     image_id=params.image_id,
        #     image_path=params.image_path,
        #     # session_name=params.sesson_name,
        #     code=200,
        #     message="motioncor executed successfully",
        #     description="output for motioncor estimation and evaluation for a input file",
        #     # status=params.status,
        #     # type=params.type,
        #     created_date=datetime.now(),
        #     # started_on=params.start_on,
        #     ended_on=datetime.now(),
        #     output_data=output_data,
        #     # meta_data=metaDataList,
        #     output_files=output_files
        # )
        # executeMethodSuccess.inc()
        print(outputSuccessResult,output_data,output_files)
        return outputSuccessResult
    except subprocess.CalledProcessError as e:
        logger.error("Error running executable: %s", e)
        # executeMethodFailure.inc()
        # executeMethodSuccess.inc()
        return {
        "data":outputSuccessResult
        }
    except Exception as e:
        error_message = f"An error occurred: {str(e) if e else 'Unknown error'}"
        logger.error(error_message)
        return {
            "status_code": 500,
            "error_message": error_message
        }