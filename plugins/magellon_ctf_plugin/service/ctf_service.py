import logging
import math
import os
import subprocess

from core.helper import create_directory
from core.model_dto import CryoEmCtfTaskData, TaskDto, CryoEmTaskResultDto
from service.ctfeval import run_ctf_evaluation
from utils import buildCtfCommand, readLastLine, getFileContents

logger = logging.getLogger(__name__)


async def do_ctf(the_task: TaskDto):
    try:
        # create_directory()
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
        logger.info("output", output)
        logger.info("Return Code: %s", return_code)
        if return_code != 0:
            logger.error("Error output: %s", error_output)
            # executeMethodFailure.inc()
            return {"error_output": error_output}

        outputFileName = "".join(the_task_data.outputFile.split(".")[:-1])
        CTFestimationValues = await readLastLine(f'{os.getcwd()}/{outputFileName}.txt')
        result = run_ctf_evaluation(f'{os.getcwd()}/{the_task_data.outputFile}', the_task_data.pixelSize, the_task_data.sphericalAberration,
                                    the_task_data.accelerationVoltage, the_task_data.maximumResolution,
                                    float(CTFestimationValues[1]) * 1e-3, float(CTFestimationValues[2]) * 1e-3,
                                    the_task_data.amplitudeContrast, CTFestimationValues[4],
                                    math.radians(float(CTFestimationValues[3])))

        # result=CryoEmTaskResultDto()
        outputSuccessResult = {
            "status_code": 200,
            "message": "ctf completed successfully",
            "output_txt": await getFileContents(f'{os.getcwd()}/{outputFileName}.txt'),
            "output_avrot": await getFileContents(f'{os.getcwd()}/{outputFileName}_avrot.txt'),
            "ctf_a"
            "nalysis_result": result,
            "ctf_analysis_images": [f'{os.getcwd()}/{the_task_data.outputFile}-plots.png',
                                    f'{os.getcwd()}/{the_task_data.outputFile}-powerspec.jpg',
                                    f'{os.getcwd()}/{the_task_data.outputFile}']
        }
        # executeMethodSuccess.inc()
        return {"data": outputSuccessResult}

    except subprocess.CalledProcessError as e:
        error_message = f"An error occurred: {str(e)}"
        outputErrorResult = {
            "status_code": 500,
            "error_message": error_message
        }
