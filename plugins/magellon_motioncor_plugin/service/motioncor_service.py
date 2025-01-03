import logging
import math
import os
import subprocess
import concurrent.futures
from core.helper import push_info_to_debug_queue
from utils import build_motioncor3_command,getFrameAlignment,getPatchFrameAlignment,isFilePresent,getRequirements,getFilecontentsfromThread
from datetime import datetime
from core.settings import AppSettingsSingleton
from core.model_dto import CryoEmMotionCorTaskData, OutputFile, TaskDto, TaskResultDto,DebugInfo


logger = logging.getLogger(__name__)


async def do_motioncor(params: TaskDto)->TaskResultDto:
    
    try:

        d = DebugInfo()
        # logger.info(f"Starting task {params.id} ")
        the_task_data = CryoEmMotionCorTaskData.model_validate(params.data)
        # d.line1 = the_task_data.inputFile
        # d.line2 = the_task_data.image_path
        # replace_settings = AppSettingsSingleton.get_instance()
        # if replace_settings.REPLACE_TYPE == "standard":
        #     the_task_data.inputFile = the_task_data.inputFile.replace(
        #         replace_settings.REPLACE_PATTERN, replace_settings.REPLACE_WITH
        #     )
        #     the_task_data.image_path = the_task_data.image_path.replace(
        #         replace_settings.REPLACE_PATTERN, replace_settings.REPLACE_WITH
        #     )
        # d.line3 = the_task_data.inputFile
        # d.line4 = the_task_data.image_path

        # final_path = os.path.normpath(the_task_data.inputFile).replace("\\", "/")
        # the_task_data.inputFile = final_path
        # the_task_data.image_path = final_path

        # d.line5 = the_task_data.inputFile
        # d.line6 = the_task_data.image_path
        # push_info_to_debug_queue(d)
        os.makedirs(f'{os.path.join(os.getcwd(),"gpfs", "outputs")}', exist_ok=True)
        directory_path = os.path.join(os.getcwd(),"gpfs", "outputs", str(params.id))
        params.data["OutMrc"] = f'{directory_path}/{params.data["OutMrc"]}'
        os.makedirs(directory_path, exist_ok=True)
        the_task_data.OutMrc = params.data["OutMrc"]
        the_task_data.LogDir= directory_path
        command = build_motioncor3_command(the_task_data)
        logger.info("Command: %s", command)
        fileName = ""
        if params.data["InMrc"] is not None:
            fileName, _ = os.path.splitext(params.data["InMrc"])
        if params.data["InEer"] is not None:
            fileName, _ = os.path.splitext(params.data["InEer"])
        if params.data["InTiff"] is not None:
            fileName, _ = os.path.splitext(params.data["InTiff"])
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
        inputFileName=fileName.split("/")[-1].split(".")[0]
        output_data={}
        output_files=[]
        with concurrent.futures.ThreadPoolExecutor() as executor:
            if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Full.log')):   
                output_data["frameAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{inputFileName}-Full.log',executor)
                output_files.append(OutputFile(name="frameAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Full.log',required=True))
        
            if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Patch-Frame.log')): 
                output_data["patchFrameAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{os.path.join(directory_path,inputFileName)}-Patch-Frame.log',executor)
                output_files.append(OutputFile(name="patchFrameAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Patch-Frame.log',required=True))

            if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Patch-Full.log')): 
                output_data["patchFullAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{os.path.join(directory_path,inputFileName)}-Patch-Full.log',executor)
                output_files.append(OutputFile(name="patchFullAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Patch-Full.log',required=True))

            if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Patch-Patch.log')): 
                output_data["patchAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{os.path.join(directory_path,inputFileName)}-Patch-Patch.log',executor)
                output_files.append(OutputFile(name="patchAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Patch-Patch.log',required=True))

        outputMrcs=[params.data["OutMrc"]]
        values=params.data["OutMrc"].split("/")
        outputFileName=f'{".".join(values[-1].split(".")[:-1])}_DW.mrc'
        values[-1]=outputFileName
        fileNameDW="/".join(values)
        if isFilePresent( fileNameDW):
            outputMrcs.append(fileNameDW)
        outputSuccessResult["outputMrcs"]=outputMrcs
        return TaskResultDto(
                worker_instance_id=params.worker_instance_id,
                task_id=params.id,
                job_id=params.job_id,
                image_id=params.data["image_id"],
                image_path=params.data["image_path"],
                session_name=params.sesson_name,
                code=200,
                message="Motioncor executed successfully",
                description="Output for Motioncor for an input file",
                status=params.status,
                type=params.type,
                created_date=datetime.now(),
                started_on=params.start_on,
                ended_on=datetime.now(),
                output_data=output_data,
                meta_data=[],
                output_files=output_files
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"An error occurred: {str(e)}")
        return TaskResultDto(
            worker_instance_id=params.worker_instance_id,
            task_id=params.id,
            job_id=params.job_id,
            image_id=params.data["image_id"],
            image_path=params.data["image_path"],
            session_name=params.sesson_name,
            code=500,
            message="Motioncor execution was unsuccessful",
            description=f"An error occurred: {str(e)}",
            status=params.status,
            type=params.type,
            created_date=datetime.now(),
            started_on=params.start_on,
            ended_on=datetime.now(),
            output_data={},
            meta_data=[],
            output_files=[]
        )
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return TaskResultDto(
            worker_instance_id=params.worker_instance_id,
            task_id=params.id,
            job_id=params.job_id,
            image_id=params.data["image_id"],
            image_path=params.data["image_path"],
            session_name=params.sesson_name,
            code=500,
            message="Motioncor execution was unsuccessful",
            description=f"An error occurred: {str(e)}",
            status=params.status,
            type=params.type,
            created_date=datetime.now(),
            started_on=params.start_on,
            ended_on=datetime.now(),
            output_data={},
            meta_data=[],
            output_files=[]
        )