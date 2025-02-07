import logging
import os
import subprocess
import json
import concurrent.futures
from core.helper import push_info_to_debug_queue
from utils import validateInput,build_motioncor3_command,getFrameAlignment,getPatchFrameAlignment,createframealignImage,isFilePresent,createframealignCenterImage,getFilecontentsfromThread
from datetime import datetime
from core.settings import AppSettingsSingleton
from core.model_dto import CryoEmMotionCorTaskData, OutputFile, TaskDto, TaskResultDto,DebugInfo,ImageMetaData


logger = logging.getLogger(__name__)


async def do_motioncor(params: TaskDto)->TaskResultDto:
    
    try:

        d = DebugInfo()
        logger.info(f"Starting task {params.id} ")
        the_task_data = CryoEmMotionCorTaskData.model_validate(params.data)
        if not validateInput(the_task_data):
            raise Exception("Validation failed.")
        #check the type of inputfile and assign 
        input_file=the_task_data.inputFile.strip()
        file_extension = os.path.splitext(input_file)[1].lower() 
        file_map = {'.mrc': 'InMrc', '.tif': 'InTiff', '.eer': 'InEer'}
        if file_extension not in file_map:
            raise ValueError("Invalid file type. Must be .mrc, .tif, or .eer.")
        if file_extension == '.eer' and params.data["FmIntFile"] is None:
            raise ValueError("FmIntFile must be provided when the file extension is .eer.")
        
        setattr(the_task_data, file_map[file_extension], input_file)
        params.data[file_map[file_extension]] = input_file
        fileName,_=os.path.splitext(input_file)
        
        d.line1 = the_task_data.inputFile
        d.line2 = the_task_data.image_path
        replace_settings = AppSettingsSingleton.get_instance()
        if replace_settings.REPLACE_TYPE == "standard":
            the_task_data.inputFile = the_task_data.inputFile.replace(
                replace_settings.REPLACE_PATTERN, replace_settings.REPLACE_WITH
            )
            the_task_data.image_path = the_task_data.image_path.replace(
                replace_settings.REPLACE_PATTERN, replace_settings.REPLACE_WITH
            )
        d.line3 = the_task_data.inputFile
        d.line4 = the_task_data.image_path

        final_path = os.path.normpath(the_task_data.inputFile).replace("\\", "/")
        the_task_data.inputFile = final_path
        the_task_data.image_path = final_path

        d.line5 = the_task_data.inputFile
        d.line6 = the_task_data.image_path
        push_info_to_debug_queue(d)
        directory_path = os.path.join(AppSettingsSingleton.get_instance().JOBS_DIR, str(the_task_data.image_id))
        os.makedirs(directory_path, exist_ok=True)
        host_file_path = os.path.join(AppSettingsSingleton.get_instance().HOST_JOBS_DIR, str(the_task_data.image_id), the_task_data.outputFile)
        the_task_data.outputFile = os.path.join(directory_path, the_task_data.outputFile)
        params.data["OutMrc"] = the_task_data.outputFile
        the_task_data.OutMrc = the_task_data.outputFile
        the_task_data.LogDir= directory_path
        command = build_motioncor3_command(the_task_data)
        logger.info("Command: %s", command)
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
        return_code = process.returncode
        if return_code != 0:
            logger.error(f"MotionCor3 error: {process.stderr.strip()}")
            return TaskResultDto(
                worker_instance_id=params.worker_instance_id, task_id=params.id,
                job_id=params.job_id, image_id=params.data["image_id"],
                image_path=params.data["image_path"], session_name=params.sesson_name,
                code=500, message="MotionCor3 execution failed", description=process.stderr.strip(),
                status=params.status, type=params.type, created_date=datetime.now(),
                started_on=params.start_on, ended_on=datetime.now(), meta_data=[], output_files=[]
            )
        output_files=[]
        values=params.data["OutMrc"].split("/")
        outputFileName=f'{".".join(values[-1].split(".")[:-1])}_DW.mrc'
        values[-1]=outputFileName
        fileNameDW="/".join(values)
        if not isFilePresent( fileNameDW):
                raise Exception("output_DW output file not found")
        output_files.append(OutputFile(name="outputDWMrc",path=fileNameDW,required=True))
        inputFileName=fileName.split("/")[-1].split(".")[0]
        meta_data=[]
        output_data={}
        output_files=[]
        if params.data["PatchesX"]>1 or params.data["PatchesY"]>1:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Patch-Patch.log')): 
                    data=getFilecontentsfromThread(getPatchFrameAlignment, f'{os.path.join(directory_path,inputFileName)}-Patch-Patch.log',executor)
                    output_data["patchAlignment"] = data  
                    meta_data.append(ImageMetaData(key="patchAlignment_Image_data",value=json.dumps(data)))
                    output_files.append(OutputFile(name="patchAlignment_Image",path=createframealignImage(fileNameDW,data["values"],directory_path,data["movie_size"],inputFileName),required=True))
                    output_files.append(OutputFile(name="patchAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Patch-Patch.log',required=True))
                else:
                    raise Exception("Patch-Patch-log file not found")
                
                if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Patch-Full.log')): 
                    output_data["patchFullAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{os.path.join(directory_path,inputFileName)}-Patch-Full.log',executor)
                    output_files.append(OutputFile(name="patchFullAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Patch-Full.log',required=True))
                    meta_data.append(ImageMetaData(key="patchFullAlignment_Image_data",value=json.dumps(output_data["patchFullAlignment"])))
                    output_files.append(OutputFile(name="patchFullAlignment_Image",path=createframealignCenterImage(fileNameDW,output_data["patchFullAlignment"],directory_path,output_data["patchAlignment"]["movie_size"],inputFileName),required=True))
                else:
                    raise Exception("Patch-Full-log file not found")
        
                if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Full.log')):   
                    # output_data["frameAlignment"]=getFilecontentsfromThread(getFrameAlignment, f'{inputFileName}-Full.log',executor)
                    output_files.append(OutputFile(name="frameAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Full.log',required=True))
            
                if(isFilePresent(f'{os.path.join(directory_path,inputFileName)}-Patch-Frame.log')): 
                    # output_data["patchFrameAlignment"]=getFilecontentsfromThread(getPatchFrameAlignment, f'{os.path.join(directory_path,inputFileName)}-Patch-Frame.log',executor)
                    output_files.append(OutputFile(name="patchFrameAlignment",path=f'{os.path.join(directory_path,inputFileName)}-Patch-Frame.log',required=True))

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
                meta_data=meta_data,
                output_files=output_files
            )
    except Exception as e:
        logger.error(f"An error occurred in Motioncor processing: {str(e)}")
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
            meta_data=[],
            output_files=[]
        )