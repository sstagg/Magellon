import logging
import math
import os
import subprocess
from datetime import datetime
from core.helper import create_directory
from core.model_dto import CryoEmCtfTaskData, OutputFile, TaskDto, CryoEmTaskResultDto,ImageMetaData
from service.ctfeval import run_ctf_evaluation
from utils import buildCtfCommand, readLastLine, getFileContents
logger = logging.getLogger(__name__)


async def do_ctf(the_task: TaskDto) -> CryoEmTaskResultDto:
    try:
        logger.info(the_task.id)
        os.makedirs(f'{os.path.join(os.getcwd(), "outputs")}',exist_ok=True)
        directory_path = os.path.join(os.getcwd(),"outputs", the_task.id)
        the_task.data["outputFile"]=f'{directory_path}/{the_task.data["outputFile"]}'
        os.makedirs(directory_path,exist_ok=True)
        # create_directory(directory_path)
        the_task_data = CryoEmCtfTaskData.model_validate(the_task.data)
        input_string = buildCtfCommand(the_task_data)
        logger.info("Input String:\n%s", input_string)
        process = subprocess.run(
            input_string,
            cwd=os.getcwd(),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        output = process.stdout
        error_output = process.stderr
        return_code = process.returncode
        # logger.info("output", output)
        # logger.info("Return Code: %s", return_code)
        if return_code != 0:
            logger.error("Error output: %s", error_output)
            # executeMethodFailure.inc()
            return {"error_output": error_output}

        outputFileName = "".join(the_task_data.outputFile.split(".")[:-1])
        CTFestimationValues = await readLastLine(f'{outputFileName}.txt')
        result = run_ctf_evaluation(f'{the_task_data.outputFile}', the_task_data.pixelSize, the_task_data.sphericalAberration,
                                    the_task_data.accelerationVoltage, the_task_data.maximumResolution,
                                    float(CTFestimationValues[1]) * 1e-3, float(CTFestimationValues[2]) * 1e-3,
                                    the_task_data.amplitudeContrast, CTFestimationValues[4],
                                    math.radians(float(CTFestimationValues[3])))
        metaDataList = []
        for key, value in result.items():
            metaDataList.append(ImageMetaData(key=key, value=str(value)))
        outputSuccessResult = CryoEmTaskResultDto(
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
    output_files = [
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
        error_message = f"An error occurred: {str(e)}"
        outputErrorResult = {
            "status_code": 500,
            "error_message": error_message
        }
