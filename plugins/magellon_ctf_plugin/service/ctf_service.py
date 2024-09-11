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

logger = logging.getLogger(__name__)


async def do_ctf(the_task: TaskDto) -> TaskResultDto:
    try:
        d = DebugInfo()
        logger.info(f"Starting task {the_task.id} ")
        the_task_data = CtfTaskData.model_validate(the_task.data)

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

        try:
            result = await run_ctf_evaluation(
                f'{the_task_data.inputFile}', the_task_data.pixelSize, the_task_data.sphericalAberration,
                the_task_data.accelerationVoltage, the_task_data.maximumResolution,
                float(CTFestimationValues[1]) * 1e-4, float(CTFestimationValues[2]) * 1e-4,
                the_task_data.amplitudeContrast, CTFestimationValues[4],
                math.radians(float(CTFestimationValues[3]))
            )

            metaDataList = [ImageMetaData(key=key, value=str(value)) for key, value in result.items()]

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
                meta_data=metaDataList,
                output_files=[
                    OutputFile(name="ctfevalplots", path=f"{outputFileName}.mrc-plots.png", required=True),
                    OutputFile(name="ctfevalpowerspec", path=f"{outputFileName}.mrc-powerspec.jpg", required=True),
                    OutputFile(name="ctfestimationOutputFile", path=f"{outputFileName}.mrc", required=True),
                    OutputFile(name="ctfestimationOutputTextFile", path=f"{outputFileName}.txt", required=True),
                    OutputFile(name="ctfestimationOutputAvrotFile", path=f"{outputFileName}_avrot.txt", required=True),
                ]
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
                meta_data=[],
                output_files=[
                    OutputFile(name="ctfestimationOutputFile", path=f"{outputFileName}.mrc", required=True),
                    OutputFile(name="ctfestimationOutputTextFile", path=f"{outputFileName}.txt", required=True),
                    OutputFile(name="ctfestimationOutputAvrotFile", path=f"{outputFileName}_avrot.txt", required=True),
                ]
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
