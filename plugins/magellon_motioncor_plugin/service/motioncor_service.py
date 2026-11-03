import logging
import os
import re
import subprocess
import json
import concurrent.futures
from core.helper import push_info_to_debug_queue
from utils import get_dw_file, save_gain_file,convertToMRC,is_mrc_file,getImageSize,validateInput,build_motioncor3_command,getFrameAlignment,getPatchFrameAlignment,createframealignImage,isFilePresent,createframealignCenterImage,getFilecontentsfromThread
from datetime import datetime
from core.settings import AppSettingsSingleton
from magellon_sdk.models import MotionCorInput, OutputFile, TaskMessage, TaskResultMessage, DebugInfo, ImageMetaData

logger = logging.getLogger(__name__)



def motioncor_errors(*outputs: str) -> str:
    """MotionCor's own error report, on one line. It prints errors such as a
    gain/frame size mismatch, skips the movie and still exits 0, so without
    this the only symptom is a missing output file."""
    found = []
    for text in outputs:
        for line in (text or "").splitlines():
            raw = line.strip()
            if not (raw.lower().startswith("error") or raw.startswith("......")
                    or raw == "Motion correction skipped."):
                continue
            message = re.sub(r"^error:\s*", "", raw.lstrip(".").strip(), flags=re.I).rstrip(".")
            if message and message not in found:
                found.append(message)
    return "; ".join(found)


def add_to_run_log(log_path: str | None, text: str) -> None:
    """Add to the movie's run log. A log that can't be written must never be
    the reason a movie fails."""
    if not log_path:
        return
    try:
        with open(log_path, "a", errors="replace") as log:
            log.write(text if text.endswith("\n") else text + "\n")
    except OSError as e:
        logger.warning("Could not write %s: %s", log_path, e)


def run_and_log(command: str, log_path: str) -> tuple[int, str]:
    """Run the command, writing each line it prints to the log as it appears,
    so the log can be followed during the run and survives a crash. Returns
    the exit code and the output. stdbuf stops the program holding its output
    back until its buffer fills, which it does when not writing to a terminal."""
    add_to_run_log(log_path, f"Command:\n{command}\n\nOutput:")
    lines = []
    with open(log_path, "a", buffering=1, errors="replace") as log:
        process = subprocess.Popen(
            f"stdbuf -oL -eL {command}",
            cwd=os.getcwd(),
            shell=True,
            text=True,
            errors="replace",
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        for line in process.stdout:
            log.write(line)
            lines.append(line)
        return_code = process.wait()
        log.write(f"\nExit code: {return_code}\nFinished: {datetime.now().isoformat(timespec='seconds')}\n")
    return return_code, "".join(lines).strip()


def _container_path(path: str | None) -> str | None:
    if not path:
        return path
    settings = AppSettingsSingleton.get_instance()
    normalized = path.replace("\\", "/")
    if settings.REPLACE_TYPE == "standard":
        pattern = (settings.REPLACE_PATTERN or "").replace("\\", "/")
        if pattern:
            normalized = normalized.replace(pattern, settings.REPLACE_WITH or "")
    return os.path.normpath(normalized).replace("\\", "/")


async def do_motioncor(params: TaskMessage)->TaskResultMessage:

    log_path = None
    try:

        d = DebugInfo()
        logger.info(f"Starting task {params.id} ")
        the_task_data = MotionCorInput.model_validate(params.data)
        print(the_task_data)
        directory_path = os.path.join(AppSettingsSingleton.get_instance().JOBS_DIR, str(the_task_data.image_id))
        os.makedirs(directory_path, exist_ok=True)
        log_name = os.path.splitext(os.path.basename(the_task_data.image_name or str(the_task_data.image_id)))[0]
        log_path = os.path.join(directory_path, f"{log_name}_motioncor.log")
        with open(log_path, "w") as log:
            log.write(f"Image: {the_task_data.image_name}\nTask: {params.id}\n"
                      f"Movie: {the_task_data.inputFile}\nGain: {the_task_data.Gain}\n"
                      f"Started: {datetime.now().isoformat(timespec='seconds')}\n\n")
        if not validateInput(the_task_data):
            raise Exception("Validation failed.")
        the_task_data.inputFile = _container_path(the_task_data.inputFile.strip())
        the_task_data.image_path = _container_path(the_task_data.image_path)
        the_task_data.Gain = _container_path(the_task_data.Gain)
        params.data["inputFile"] = the_task_data.inputFile
        params.data["image_path"] = the_task_data.image_path
        params.data["Gain"] = the_task_data.Gain

        #check the type of inputfile and assign
        input_file=the_task_data.inputFile
        file_extension = os.path.splitext(input_file)[1].lower()
        x_size,y_size=getImageSize(params.data["inputFile"],file_extension)
        file_map = {'.mrc': 'InMrc', '.tif': 'InTiff', '.eer': 'InEer'}
        if file_extension not in file_map:
            raise ValueError("Invalid file type. Must be .mrc, .tif, or .eer.")
        # if file_extension == '.eer' and params.data["FmIntFile"] is None:
        #     raise ValueError("FmIntFile must be provided when the file extension is .eer.")
        
        setattr(the_task_data, file_map[file_extension], input_file)
        params.data[file_map[file_extension]] = input_file
        fileName=input_file
        
        d.line1 = the_task_data.inputFile
        d.line2 = the_task_data.image_path
        d.line3 = the_task_data.inputFile
        d.line4 = the_task_data.image_path

        final_path = the_task_data.inputFile
        the_task_data.inputFile = final_path
        the_task_data.image_path = final_path

        d.line5 = the_task_data.inputFile
        d.line6 = the_task_data.image_path
        push_info_to_debug_queue(d)
        print("directory path",directory_path)
        host_file_path = os.path.join(
            AppSettingsSingleton.get_instance().HOST_JOBS_DIR,
            str(the_task_data.image_id),
            the_task_data.OutMrc,
        )
        the_task_data.OutMrc = os.path.join(directory_path, the_task_data.OutMrc)
        if not the_task_data.OutMrc.endswith(".mrc"):
            the_task_data.OutMrc += ".mrc"
        params.data["OutMrc"] = the_task_data.OutMrc
        the_task_data.LogDir = directory_path
        if not is_mrc_file(the_task_data.Gain):
            the_task_data.Gain=convertToMRC(the_task_data.Gain,directory_path)
            save_gain_file(the_task_data.Gain,directory_path)
        command = build_motioncor3_command(the_task_data)
        logger.info("Command: %s", command)
        return_code, output = run_and_log(os.path.join(os.getcwd(),command), log_path)
        mc_errors = motioncor_errors(output)
        print(output)
        run_log = OutputFile(name="motioncorRunLog", path=log_path, required=False)
        if return_code != 0:
            logger.error(f"MotionCor3 error: {output[-2000:]}")
            from magellon_sdk.models import TaskStatus, FAILED
            return TaskResultMessage(
                worker_instance_id=params.worker_instance_id, task_id=params.id,
                job_id=params.job_id, image_id=params.data["image_id"],
                image_path=params.data["image_path"], session_name=params.session_name,
                code=500, message="MotionCor3 execution failed", description=mc_errors or output[-2000:],
                status=FAILED, type=params.type, created_date=datetime.now(),
                started_on=params.start_on, ended_on=datetime.now(), meta_data=[], output_files=[run_log]
            )
        output_files=[run_log]
        meta_data=[]
        output_data={}
        print(directory_path)
        
        # Search for _DW.mrc first, if not found try _DWS.mrc
        dw_file = get_dw_file(directory_path)
        
        if dw_file:
            output_files.append(OutputFile(name="outputDWMrc", path=dw_file, required=True))
        else:
            raise Exception(f"MotionCor failed: {mc_errors}" if mc_errors
                            else "output_DW or output_DWS output file not found")
        
        with concurrent.futures.ThreadPoolExecutor() as executor:

            if params.data["PatchesX"] > 1 or params.data["PatchesY"] > 1:
                print(directory_path)
                file= isFilePresent(directory_path, "-Patch-Patch.log")
                if file:
                    data = getFilecontentsfromThread(getPatchFrameAlignment, file, executor)
                    output_data["patchAlignment"] = data
                    new_file_path = f'{os.path.join(directory_path, os.path.splitext(the_task_data.image_name)[0])}-patch-Patch.log'
                    os.rename(file, new_file_path)
                    meta_data.append(ImageMetaData(key="patchAlignment_Image_data", value=json.dumps(data)))
                    output_files.append(OutputFile(name="patchAlignment_Image",
                                                path=createframealignImage(dw_file, data["values"], directory_path, data["movie_size"], os.path.splitext(the_task_data.image_name)[0]),
                                                required=True))
                    output_files.append(OutputFile(name="patchAlignment", path=new_file_path, required=True))
                else:
                    raise Exception("Patch-Patch.log file not found")
                file= isFilePresent(directory_path, "-Patch-Full.log")
                if file:
                    output_data["patchFullAlignment"] = getFilecontentsfromThread(getFrameAlignment, file, executor)
                    
                    new_file_path = f'{os.path.join(directory_path,  os.path.splitext(the_task_data.image_name)[0])}-patch-Full.log'
                    os.rename(file, new_file_path)
                    output_files.append(OutputFile(name="patchFullAlignment", path=new_file_path, required=True))
                    meta_data.append(ImageMetaData(key="patchFullAlignment_Image_data", value=json.dumps(output_data["patchFullAlignment"])))
                    output_files.append(OutputFile(name="patchFullAlignment_Image",
                                                path=createframealignCenterImage(dw_file, output_data["patchFullAlignment"], directory_path, [x_size, y_size], os.path.splitext(the_task_data.image_name)[0]),
                                                required=True))
                else:
                    raise Exception("Patch-Full.log file not found")

                file= isFilePresent(directory_path, "-Patch-Frame.log")
                if file:
                    new_file_path = f'{os.path.join(directory_path, os.path.splitext(the_task_data.image_name)[0])}-patch-Frame.log'
                    os.rename(file, new_file_path)
                    output_files.append(OutputFile(name="patchFrameAlignment", path=new_file_path, required=True))

            else:
                file= isFilePresent(directory_path, "-Full.log")
                if file:
                    output_data["fullAlignment"] = getFilecontentsfromThread(getFrameAlignment, file, executor)
                    new_file_path = f'{os.path.join(directory_path, the_task_data.image_name.split(".")[0])}-full.log'
                    os.rename(file, new_file_path)
                    output_files.append(OutputFile(name="frameAlignment", path=new_file_path, required=True))
                    meta_data.append(ImageMetaData(key="frameAlignment_Image_data", value=json.dumps(output_data["fullAlignment"])))
                    output_files.append(OutputFile(name="frameAlignment_Image",
                                                path=createframealignCenterImage(dw_file, output_data["fullAlignment"], directory_path, [x_size, y_size], os.path.splitext(the_task_data.image_name)[0]),
                                                required=True))
        return TaskResultMessage(
                worker_instance_id=params.worker_instance_id,
                task_id=params.id,
                job_id=params.job_id,
                image_id=params.data["image_id"],
                image_path=params.data["image_path"],
                session_name=params.session_name,
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
        add_to_run_log(log_path, f"\nFailed: {e}")
        from magellon_sdk.models import FAILED
        return TaskResultMessage(
            worker_instance_id=params.worker_instance_id,
            task_id=params.id,
            job_id=params.job_id,
            image_id=params.data["image_id"],
            image_path=params.data["image_path"],
            session_name=params.session_name,
            code=500,
            message="Motioncor execution was unsuccessful",
            description=f"An error occurred: {str(e)}",
            status=FAILED,
            type=params.type,
            created_date=datetime.now(),
            started_on=params.start_on,
            ended_on=datetime.now(),
            meta_data=[],
            output_files=[OutputFile(name="motioncorRunLog", path=log_path, required=False)]
            if log_path and os.path.exists(log_path) else []
        )
