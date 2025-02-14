import logging
import math
import os
import subprocess
from datetime import datetime

from core.helper import push_info_to_debug_queue
from core.model_dto import CtfTaskData, OutputFile, TaskDto, TaskResultDto, ImageMetaData, DebugInfo
from core.settings import AppSettingsSingleton
from service.ctfeval import run_ctf_evaluation
from utils import buildCtfCommand, readLastLine, getFileContents
import json

logger = logging.getLogger(__name__)

def validateInput(params):
    if not params.inputFile or not isinstance(params.inputFile, str) or not params.inputFile.strip():
        raise ValueError("inputFile must be a non-empty string.")
    
    if not isinstance(params.pixelSize, (float, int)) or params.pixelSize <= 0:
        raise ValueError("pixelSize must be a number and greater than zero.")
    
    if not isinstance(params.accelerationVoltage, (float, int)) or params.accelerationVoltage <= 0:
        raise ValueError("accelerationVoltage must be a number and greater than zero.")
    
    if not isinstance(params.sphericalAberration, (float, int)) or params.sphericalAberration <= 0:
        raise ValueError("sphericalAberration must be a number and greater than zero.")
    
    if not isinstance(params.amplitudeContrast, (float, int)) or params.amplitudeContrast <= 0:
        raise ValueError("amplitudeContrast must be a number between 0 and 1.")
    
    if not isinstance(params.sizeOfAmplitudeSpectrum, int) or params.sizeOfAmplitudeSpectrum <= 0:
        raise ValueError("sizeOfAmplitudeSpectrum must be a number and greater than zero.")
    
    if not isinstance(params.minimumResolution, (float, int)) or params.minimumResolution <= 0:
        raise ValueError("minimumResolution must be a number and greater than zero.")
    
    if not isinstance(params.maximumResolution, (float, int)) or params.maximumResolution <= 0:
        raise ValueError("maximumResolution must be a number and greater than zero.")
    
    if not isinstance(params.minimumDefocus, (float, int)) or params.minimumDefocus <= 0:
        raise ValueError("minimumDefocus must be a number and greater than zero.")
    
    if not isinstance(params.maximumDefocus, (float, int)) or params.maximumDefocus <= 0:
        raise ValueError("maximumDefocus must be a number and greater than zero.")
    
    if not isinstance(params.defocusSearchStep, (float, int)) or params.defocusSearchStep <= 0:
        raise ValueError("defocusSearchStep must be a number and greater than zero.")

    return True

async def do_ctf(the_task: TaskDto) -> TaskResultDto:
    try:
        d = DebugInfo()
        logger.info(f"Starting task {the_task.id} ")
        the_task_data = CtfTaskData.model_validate(the_task.data)
        # validate the input
        try:
            if not validateInput(the_task_data):
                raise Exception("Validation failed.")
            print("Validation passed. Proceeding with task...")
        except ValueError as e:
            raise Exception(f"Input validation error: {e}")
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

        directory_path = os.path.join(AppSettingsSingleton.get_instance().JOBS_DIR, str(the_task.id))
        os.makedirs(directory_path, exist_ok=True)
        host_file_path = os.path.join(AppSettingsSingleton.get_instance().HOST_JOBS_DIR, str(the_task.id), the_task.data["outputFile"])
        the_task_data.outputFile = os.path.join(directory_path, the_task.data["outputFile"])

        input_string = buildCtfCommand(the_task_data)
        logger.info("Input String: %s", input_string)
        process = subprocess.run(
            input_string,
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
            raise Exception(f"Command failed with return code {process.returncode}: {output} {error_output}")

        outputFileName = "".join(the_task_data.outputFile.split(".")[:-1])
        CTFestimationValues = await readLastLine(f'{outputFileName}.txt')

        # Initialize metadata list
        metaDataList = []
        output_files=[]
        files_to_check = [
                ("ctfevalplots", f"{outputFileName}.mrc-plots.png"),
                ("ctfevalpowerspec", f"{outputFileName}.mrc-powerspec.jpg"),
                ("ctfestimationOutputFile", f"{outputFileName}.mrc"),
                ("ctfestimationOutputTextFile", f"{outputFileName}.txt"),
                ("ctfestimationOutputAvrotFile", f"{outputFileName}_avrot.txt"),
            ]
        try:
            result = await run_ctf_evaluation(
                f'{the_task_data.inputFile}',os.path.join(directory_path, the_task.data["outputFile"]), the_task_data.pixelSize, the_task_data.sphericalAberration,
                the_task_data.accelerationVoltage, the_task_data.maximumResolution,
                float(CTFestimationValues[1]) * 1e-4, float(CTFestimationValues[2]) * 1e-4,
                the_task_data.amplitudeContrast, CTFestimationValues[4],
                math.radians(float(CTFestimationValues[3]))
            )
            for name, path in files_to_check:
                if os.path.exists(path):  
                    output_files.append(OutputFile(name=name, path=path, required=True))

            return TaskResultDto(
                worker_instance_id=the_task.worker_instance_id,
                task_id=the_task.id,
                job_id=the_task.job_id,
                image_id=the_task.data["image_id"],
                image_path=the_task.data["image_path"],
                session_name=the_task.sesson_name,
                code=200,
                message="CTF executed successfully",
                description="Output for CTF estimation and evaluation for an input file",
                status=the_task.status,
                type=the_task.type,
                created_date=datetime.now(),
                started_on=the_task.start_on,
                ended_on=datetime.now(),
                output_data={
                    "output_txt": await getFileContents(f"{outputFileName}.txt"),
                    "output_avrot": await getFileContents(f"{outputFileName}_avrot.txt")
                },
                meta_data=[ImageMetaData(key="CTF", value=json.dumps(result), image_id=f"{outputFileName}.mrc")],
                output_files=output_files
            )

        except Exception as eval_error:
            logger.warning(f"CTF evaluation failed: {str(eval_error)}")
            return TaskResultDto(
                worker_instance_id=the_task.worker_instance_id,
                task_id=the_task.id,
                job_id=the_task.job_id,
                image_id=the_task.data["image_id"],
                image_path=the_task.data["image_path"],
                session_name=the_task.sesson_name,
                code=200,
                message="CTF executed successfully but evaluation failed",
                description="Output for CTF estimation and evaluation for an input file",
                status=the_task.status,
                type=the_task.type,
                created_date=datetime.now(),
                started_on=the_task.start_on,
                ended_on=datetime.now(),
                output_data={
                    "output_txt": await getFileContents(f"{outputFileName}.txt"),
                    "output_avrot": await getFileContents(f"{outputFileName}_avrot.txt")
                },
                meta_data=[ImageMetaData(key="CTF", value=json.dumps(result), image_id=f"{outputFileName}.mrc")],
                output_files=output_files
            )

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        return TaskResultDto(
            worker_instance_id=the_task.worker_instance_id,
            task_id=the_task.id,
            job_id=the_task.job_id,
            image_id=the_task.data["image_id"],
            image_path=the_task.data["image_path"],
            session_name=the_task.sesson_name,
            code=500,
            message="CTF execution was unsuccessful",
            description=f"An error occurred: {str(e)}",
            status=the_task.status,
            type=the_task.type,
            created_date=datetime.now(),
            started_on=the_task.start_on,
            ended_on=datetime.now(),
            output_data={},
            meta_data=[],
            output_files=[]
        )
