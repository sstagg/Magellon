import logging
import os
import platform
import subprocess
import sys
import uuid
from typing import List

from pydantic import BaseModel

# from core.execution_engine import publish_message
from core.model_dto import CheckRequirementsResult, TaskDto, FFT_TASK, TaskStatusEnum, PENDING, CryoEmFftTaskDetailDto, \
    RequirementResult, RecuirementResultEnum, CryoEmCtfTaskData
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt
from service.ctf_service import do_ctf
from service.fft_service import compute_file_fft
from utils import buildCtfCommand

logger = logging.getLogger(__name__)


class InputParams(BaseModel):
    x: float
    y: float


# async def execute(request: InputParams):
#     result = request.x * request.y
#     return {"result": result}

def execute(params: CryoEmCtfTaskData):
    try:
        # fft_path = os.path.join(out_dir, FFT_SUB_URL,os.path.splitext(os.path.basename(abs_file_path))[0] +FFT_SUFFIX)
        do_ctf(params)
        return {"message": "MRC file successfully converted to fft PNG!"}

    except Exception as e:
        return {"error": str(e)}

    # try:
    #     input_string = buildCtfCommand(params)
    #     logger.info("Input String:\n%s", input_string)
    #
    #     process = subprocess.run(
    #         input_string,
    #         cwd=os.getcwd(),
    #         shell=True,
    #         stdout=subprocess.PIPE,
    #         stderr=subprocess.PIPE,
    #         universal_newlines=True
    #     )
    #
    #     output = process.stdout
    #     error_output = process.stderr
    #     return_code = process.returncode
    #     logger.info("output",output)
    #     logger.info("Return Code: %s", return_code)
    #     if return_code != 0:
    #         logger.error("Error output: %s", error_output)
    #         # executeMethodFailure.inc()
    #         return {"error_output": error_output}
    #
    #     outputFileName = "".join(params.outputFile.split(".")[:-1])
    #     CTFestimationValues=await readLastLine(f'{os.getcwd()}/{outputFileName}.txt')
    #     result = run_ctf_evaluation(f'{os.getcwd()}/{params.outputFile}', params.pixelSize, params.sphericalAberration, params.accelerationVoltage,params.maximumResolution,float(CTFestimationValues[1])*1e-3,float(CTFestimationValues[2])*1e-3,params.amplitudeContrast, CTFestimationValues[4],math.radians(float(CTFestimationValues[3])))
    #     outputSuccessResult = {
    #         "status_code": 200,
    #         "message": "ctf completed successfully",
    #         "output_txt": await getFileContents(f'{os.getcwd()}/{outputFileName}.txt'),
    #         "output_avrot": await getFileContents(f'{os.getcwd()}/{outputFileName}_avrot.txt'),
    #         "ctf_analysis_result": result,
    #         "ctf_analysis_images":[f'{os.getcwd()}/{params.outputFile}-plots.png',f'{os.getcwd()}/{params.outputFile}-powerspec.jpg',f'{os.getcwd()}/{params.outputFile}']
    #     }
    #     # executeMethodSuccess.inc()
    #     return {"data": outputSuccessResult}
    #
    # except subprocess.CalledProcessError as e:
    #     error_message = f"An error occurred: {str(e)}"
    #     outputErrorResult = {
    #         "status_code": 500,
    #         "error_message": error_message
    #     }
        # executeMethodFailure.inc()

    # return {"error_output":  outputErrorResult}
    # try:
    #     # fft_path = os.path.join(out_dir, FFT_SUB_URL,os.path.splitext(os.path.basename(abs_file_path))[0] +FFT_SUFFIX)
    #     compute_file_fft(mrc_abs_path=request.image_path, abs_out_file_name=request.target_path)
    #     return {"message": "MRC file successfully converted to fft PNG!"}
    #
    # except Exception as e:
    #     return {"error": str(e)}


async def check_requirements():
    all_results = []

    # Execute each check function and aggregate results
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())

    # Add more checks for other requirements here

    return all_results

# async def publish():
#     data1 = {"key1": "value1", "key2": "value2"}
#     instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
#     job_id1 = uuid.uuid4()  # Replace with your specific job ID
#
#     task1 = TaskDto.create(data1, FFT_TASK, PENDING, instance_id1, job_id1)
#
#     publish_message(task1.model_dump_json())
#     return task1.model_dump_json()

# Example 2
# data2 = {"key3": "value3", "key4": "value4"}
# ptype2 = TaskType()  # Replace with your specific TaskType initialization
# pstatus2 = TaskStatus()  # Replace with your specific TaskStatus initialization
# instance_id2 = UUID("your_worker_instance_id2")  # Replace with your specific worker instance ID
# job_id2 = "your_job_id2"  # Replace with your specific job ID
#
# task2 = TaskDto.create(data2, ptype2, pstatus2, instance_id2, job_id2)



