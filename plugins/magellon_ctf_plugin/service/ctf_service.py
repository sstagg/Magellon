import logging
import math
import os
import shutil
import subprocess
from datetime import datetime

from core.model_dto import CtfTaskData, OutputFile, TaskDto, TaskResultDto, ImageMetaData
from core.settings import AppSettingsSingleton
from service.ctfeval import run_ctf_evaluation
from utils import buildCtfCommand, readLastLine, getFileContents

logger = logging.getLogger(__name__)


async def do_ctf(the_task: TaskDto) -> TaskResultDto:
    try:
        logger.info(f"Starting task {the_task.id} ")
        the_task_data = CtfTaskData.model_validate(the_task.data)

        if AppSettingsSingleton.get_instance().REPLACE_TYPE=="standard" :
            the_task_data.inputFile = the_task_data.inputFile.replace(AppSettingsSingleton.get_instance().REPLACE_PATTERN, AppSettingsSingleton.get_instance().REPLACE_WITH)
            the_task_data.image_path = the_task_data.image_path.replace(AppSettingsSingleton.get_instance().REPLACE_PATTERN, AppSettingsSingleton.get_instance().REPLACE_WITH)

        # os.makedirs(f'{os.path.join(os.getcwd(),"gpfs", "outputs")}', exist_ok=True)
        # directory_path = os.path.join(os.getcwd(),"gpfs", "outputs", the_task.id)

        directory_path = os.path.join( "c:/temp/outputs", the_task.id)
        the_task_data.outputFile = f'{directory_path}/{the_task.data["outputFile"]}'
        os.makedirs(directory_path, exist_ok=True)

        #testing if really we have access to input files
        shutil.copy2(the_task_data.inputFile, directory_path)

        input_string = buildCtfCommand(the_task_data)
        logger.info("Input String:%s", input_string)
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
            # logger.error("Standard output: %s", output)
            # logger.error("Error output: %s", error_output)
            raise Exception(f"Command failed with return code {process.returncode}:{output} {error_output}")
            # executeMethodFailure.inc()
            return {"error_output": error_output}
        outputFileName = "".join(the_task_data.outputFile.split(".")[:-1])
        CTFestimationValues = await readLastLine(f'{outputFileName}.txt')
        result =  await run_ctf_evaluation(f'{the_task_data.outputFile}', the_task_data.pixelSize,
                                    the_task_data.sphericalAberration,
                                    the_task_data.accelerationVoltage, the_task_data.maximumResolution,
                                    float(CTFestimationValues[1]) * 1e-3, float(CTFestimationValues[2]) * 1e-3,
                                    the_task_data.amplitudeContrast, CTFestimationValues[4],
                                    math.radians(float(CTFestimationValues[3])))
        metaDataList = []

        for key, value in result.items():
            metaDataList.append(ImageMetaData(key=key, value=str(value)))

        outputSuccessResult = TaskResultDto(
            worker_instance_id=the_task.worker_instance_id,
            task_id=str(the_task.job_id),
            image_id=the_task.data["image_id"],
            image_path=the_task.data["image_path"],
            code=200,
            message="ctf executed successfully",
            description="output for ctf estimation and evaluation for a input file",
            status=the_task.status,
            type=the_task.type,
            created_date=datetime.now(),
            started_on=the_task.start_on,
            ended_on=datetime.now(),
            output_data={
                "output_txt": await getFileContents(f"{outputFileName}.txt"),
                "output_avrot": await getFileContents(f"{outputFileName}_avrot.txt")
            },
            meta_data=metaDataList,
            output_files=[
                OutputFile(name="ctfevalplots", path=f"{outputFileName}.mrc-plots.png", required=True),
                OutputFile(name="ctfevalpowerspec", path=f"{outputFileName}.mrc-powerspec.jpg", required=True),
                OutputFile(name="ctfestimationOutputFile", path=f"{outputFileName}.mrc", required=True),
                OutputFile(name="ctfestimationOutputTextFile", path=f"{outputFileName}.txt", required=True),
                OutputFile(name="ctfestimationOutputAvrotFile", path=f"{outputFileName}_avrot.txt", required=True),
            ]
        )
        # executeMethodSuccess.inc()
        return {"data": outputSuccessResult}

    except subprocess.CalledProcessError as e:
        error_message = f"Command '{e.cmd}' failed with return code {e.returncode}: {e.stderr}"
        logger.error(error_message)
        return {
            "status_code": 500,
            "error_message": error_message
        }
        
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.error(error_message)
        return {
            "status_code": 500,
            "error_message": error_message
        }


