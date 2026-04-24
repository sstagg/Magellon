import logging
import math
import os
import re
import uuid
import glob
from pydantic import BaseModel

from config import app_settings
from core.task_factory import CtfTaskFactory, FftTaskFactory, MotioncorTaskFactory
from models.plugins_models import TaskDto, CtfTaskData, FftTaskData, FFT_TASK, TaskResultDto, CTF_TASK, PENDING, CryoEmMotionCorTaskData, \
    MOTIONCOR_TASK, TaskCategory
from models.pydantic_models import LeginonFrameTransferTaskDto, EPUImportTaskDto, ImportTaskDto

logger = logging.getLogger(__name__)

def append_json_to_file(file_path, json_str):
    try:
        # Append the JSON string as a new line to the file
        with open(file_path, 'a') as file:
            file.write(json_str + '\n')

        return True  # Success
    except Exception as e:
        print(f"Error appending JSON to file: {e}")
        return False  # Failure

def create_directory(path):
    """
    Creates the directory for the given image path if it does not exist.

    Args:
    image_path (str): The absolute path of the image file.

    Returns:
    None
    """
    try:
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            # Set permissions to 777
            # os.chmod(directory, 0o777)
    except Exception as e:
        print(f"An error occurred while creating the directory: {str(e)}")


def custom_replace(input_string, replace_type, replace_pattern, replace_with):
    """
    Function to perform various types of string replacement based on the specified replace_type.

    Parameters:
        input_string (str): The input string to be modified.
        replace_type (str): Type of replacement. Can be 'none', 'normal', or 'regex'.
        replace_pattern (str): Pattern to search for in the input string.
        replace_with (str): String to replace the replace_pattern with.

    Returns:
        str: The modified string after replacement.
    """
    if replace_type == 'none':
        return input_string

    elif replace_type == 'standard':
        return input_string.replace(replace_pattern, replace_with)

    elif replace_type == 'regex':
        return re.sub(replace_pattern, replace_with, input_string)

    else:
        raise ValueError("Invalid replace_type. Use 'none', 'normal', or 'regex'.")



def get_queue_name_by_task_type(task_type: TaskCategory, is_result: bool = False) -> str:
    """
    Get the appropriate queue name based on task type and whether it's for results

    Args:
        task_type (str): Type of the task (e.g., MOTIONCOR_TASK, CTF_TASK)
        is_result (bool): If True, returns result queue name, else task queue name

    Returns:
        str: Queue name from app settings
    """
    queue_mapping = {
        5: {  # MOTIONCOR_TASK.code
            'task': app_settings.rabbitmq_settings.MOTIONCOR_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.MOTIONCOR_OUT_QUEUE_NAME
        },
        2: {  # CTF_TASK.code
            'task': app_settings.rabbitmq_settings.CTF_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.CTF_OUT_QUEUE_NAME
        },
        1: {  # FFT_TASK.code
            'task': app_settings.rabbitmq_settings.FFT_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.FFT_OUT_QUEUE_NAME
        },
        6: {  # SQUARE_DETECTION.code
            'task': app_settings.rabbitmq_settings.SQUARE_DETECTION_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.SQUARE_DETECTION_OUT_QUEUE_NAME
        },
        7: {  # HOLE_DETECTION.code
            'task': app_settings.rabbitmq_settings.HOLE_DETECTION_QUEUE_NAME,
            'result': app_settings.rabbitmq_settings.HOLE_DETECTION_OUT_QUEUE_NAME
        },
    }

    if task_type.code not in queue_mapping:
        return None

    return queue_mapping[task_type.code]['result' if is_result else 'task']

def push_task_to_task_queue(task: TaskDto) -> bool:
    """Push a task to its worker via the configured dispatcher.

    Delegates to :class:`magellon_sdk.dispatcher.TaskDispatcherRegistry`;
    adding a new plugin is now a single ``registry.register(...)`` call
    in :mod:`core.dispatcher_registry` — no edit to this function or
    the task-type→queue switch needed.
    """
    try:
        from core.dispatcher_registry import get_task_dispatcher_registry

        _audit_outgoing_message(task)
        return get_task_dispatcher_registry().dispatch(task)
    except Exception as e:
        logger.error(f"Error pushing task to queue: {e}")
        return False


def _audit_outgoing_message(task: TaskDto) -> None:
    """Best-effort on-disk audit log of outgoing tasks.

    Writes one JSON line per dispatched task to
    ``/magellon/messages/<queue>/messages.json``. Matches the old
    ``publish_message_to_queue`` behaviour so operators keep their
    audit trail through the dispatcher migration. Failures are
    swallowed — this is diagnostics, not correctness.
    """
    try:
        queue_name = get_queue_name_by_task_type(task.type, is_result=False)
        if not queue_name:
            return
        destination_dir = os.path.join("/magellon", "messages", queue_name)
        os.makedirs(destination_dir, exist_ok=True)
        append_json_to_file(
            os.path.join(destination_dir, "messages.json"),
            task.model_dump_json(),
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("outgoing-message audit failed (non-fatal): %s", e)


def dispatch_ctf_task(task_id, full_image_path, task_dto: ImportTaskDto):
    if app_settings.DEBUG_CTF:
        full_image_path = full_image_path.replace(app_settings.DEBUG_CTF_PATH, app_settings.DEBUG_CTF_REPLACE)

    file_name = os.path.splitext(os.path.basename(full_image_path))[0]

    #converting LeginonFrameTransferTaskDto to ctf task
    if hasattr(task_dto, 'job_dto') and task_dto.job_dto and hasattr(task_dto.job_dto, 'session_name') and task_dto.job_dto.session_name:
        session_name = task_dto.job_dto.session_name
    else:
        session_name = file_name.split("_")[0]
    out_file_name = f"{file_name}_ctf_output.mrc"
    ctf_task_data = CtfTaskData(
        image_id=task_dto.image_id,
        image_name=file_name,
        image_path=full_image_path,
        inputFile=full_image_path,
        outputFile=out_file_name,
        pixelSize= task_dto.pixel_size * 10**10,  #1
        accelerationVoltage=task_dto.acceleration_voltage,
        sphericalAberration = (task_dto.spherical_aberration if task_dto.spherical_aberration is not None else 2.7) , #    2.7,
        amplitudeContrast=task_dto.amplitude_contrast,
        sizeOfAmplitudeSpectrum=task_dto.size_of_amplitude_spectrum,
        minimumResolution=task_dto.minimum_resolution,
        maximumResolution=task_dto.maximum_resolution,
        minimumDefocus=task_dto.minimum_defocus,
        maximumDefocus=task_dto.maximum_defocus,
        defocusSearchStep=task_dto.defocus_search_step,
        binning_x=task_dto.binning_x
        )

    job_id = None

    if task_dto is not None:
        if hasattr(task_dto, 'job_id'):
            job_id = task_dto.job_id
        elif hasattr(task_dto, 'job_dto') and task_dto.job_dto is not None:
            job_id = getattr(task_dto.job_dto, 'job_id', None)

    ctf_task = CtfTaskFactory.create_task(pid=task_dto.task_id, instance_id=uuid.uuid4(), job_id=job_id,
                                          data=ctf_task_data.model_dump(), ptype=CTF_TASK, pstatus=PENDING)
    ctf_task.session_name = session_name
    return push_task_to_task_queue(ctf_task)


def dispatch_fft_task(
    image_path: str,
    target_path: str,
    *,
    job_id=None,
    task_id=None,
    image_id=None,
) -> bool:
    """Dispatch an FFT task to the fft plugin over RMQ.

    Small, stand-alone analog of :func:`dispatch_ctf_task` — the FFT
    plugin is a test bed for the async pipeline, so this helper exists
    mainly to drive it from the /fft/dispatch REST endpoint.

    ``image_path`` is the input (mrc/tiff/png), ``target_path`` is
    where the plugin should write the FFT PNG. Both are required;
    they're explicit here because the plugin has no knowledge of
    CoreService's FFT_SUB_URL conventions.
    """
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    fft_data = FftTaskData(
        image_id=image_id,
        image_name=file_name,
        image_path=image_path,
        target_path=target_path,
        target_name=os.path.basename(target_path),
    )

    fft_task = FftTaskFactory.create_task(
        pid=task_id or uuid.uuid4(),
        instance_id=uuid.uuid4(),
        job_id=job_id,
        data=fft_data.model_dump(),
        ptype=FFT_TASK,
        pstatus=PENDING,
    )
    return push_task_to_task_queue(fft_task)


def create_motioncor_task_data(image_path, gain_path, defects_path=None, session_name=None, task_dto: ImportTaskDto=None, motioncor_settings: dict = None):
    """
    Create the common MotionCor task data structure used across different task creation methods.

    Args:
        image_path (str): Path to the input image file
        gain_path (str): Path to the gain reference file
        session_name (str, optional): Session name to use. If None, will be extracted from filename
        task_dto (ImportTaskDto, optional): Task data transfer object
        motioncor_settings (dict, optional): Dictionary of MotionCor settings to override defaults.
            Supported keys: FmDose, PatchesX, PatchesY, SumRangeMinDose, SumRangeMaxDose, Group

    Returns:
        CryoEmMotionCorTaskData: Configured task data object
    """
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    # Default settings
    settings = {
        'FmDose': 0.75,
        'PatchesX': 5,
        'PatchesY': 5,
        'SumRangeMinDose': 0,
        'SumRangeMaxDose': 0,
        'Group': 3
    }

    # Update with user-provided settings if any
    if motioncor_settings:
        settings.update(motioncor_settings)


    if session_name is None:
        session_name = file_name.split("_")[0]
    return CryoEmMotionCorTaskData(
            image_id=task_dto.image_id,
            image_name=os.path.basename(task_dto.image_path),
            image_path=task_dto.image_path,

            inputFile=image_path,
            OutMrc=os.path.basename(task_dto.image_path),
            Gain=gain_path,
            DefectFile=defects_path,
            PixSize=task_dto.pixel_size* 10**10,
            RotGain=task_dto.rot_gain,
            FlipGain=task_dto.flip_gain,
            **settings
        )

def find_matching_file(base_path, frame_name):
    # Priority order
    extensions_priority = [".eer", ".tiff", ".tif", ".mrc"]

    for ext in extensions_priority:
        pattern = os.path.join(base_path, frame_name + "*" + ext)
        files = glob.glob(pattern)
        if files:
            return files[0]  # return first file matching in priority
    return None

def create_motioncor_task(image_path=None,
                          gain_path=None,
                          defects_path=None,
                          session_name=None,
                          task_id=None,
                          job_id=None,
                          task_dto: ImportTaskDto=None,
                          motioncor_settings: dict = None

                          ):
    """
    Creates a MotionCor task with specified parameters

    Args:
        image_path (str, optional): Path to the input image file
        gain_path (str, optional): Path to the gain reference file
        session_name (str, optional): Session name
        task_id (str, optional): Task ID to use
        job_id (UUID, optional): Job ID to use

    Returns:
        MotioncorTask: Created task object or False if error occurs
        :param task_dto:
    """

    try:
        # Use provided paths or defaults
        # Create task data
        base_path = os.path.dirname(task_dto.frame_path)
        matching_file = find_matching_file(base_path, task_dto.frame_name)
        if not matching_file:
            raise ("motioncor input File not found",task_dto.frame_path)
        motioncor_task_data = create_motioncor_task_data(
            image_path=matching_file,
            gain_path=gain_path,
            defects_path=defects_path,
            session_name=session_name,
            task_dto=task_dto,
            motioncor_settings=motioncor_settings
        )

        motioncor_task = MotioncorTaskFactory.create_task(
            pid=task_id or str(uuid.uuid4()),
            instance_id=uuid.uuid4(),
            job_id=job_id or uuid.uuid4(),
            data=motioncor_task_data.model_dump(),
            ptype=MOTIONCOR_TASK,
            pstatus=PENDING
        )
        # Set session name from task data if not explicitly provided
        motioncor_task.session_name = session_name or motioncor_task_data.image_name.split("_")[0]

        return motioncor_task
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False


def dispatch_motioncor_task(task_id,
                            full_image_path,
                            task_dto: ImportTaskDto,
                            gain_path="/gpfs/20241202_53597_gain_multi_ref.tif",
                            defects_path=None,
                            session_name="24dec03a",
                            motioncor_settings: dict = None
                            ):
    """
    Creates and dispatches a MotionCor task based on an import task DTO

    Args:
        task_id (str): ID for the new task
        full_image_path (str): Path to the input image file
        task_dto (ImportTaskDto): Import task data transfer object

    Returns:
        bool: True if task was successfully pushed to queue
    """
    job_id = None

    if task_dto is not None:
        if hasattr(task_dto, 'job_id'):
            job_id = task_dto.job_id
        elif hasattr(task_dto, 'job_dto') and task_dto.job_dto is not None:
            job_id = getattr(task_dto.job_dto, 'job_id', None)

        # Handle debug CTF path replacement if needed
    if app_settings.DEBUG_CTF:
        full_image_path = full_image_path.replace(
            app_settings.DEBUG_CTF_PATH,
            app_settings.DEBUG_CTF_REPLACE
        )
    if hasattr(task_dto, 'job_dto') and task_dto.job_dto and hasattr(task_dto.job_dto, 'session_name') and task_dto.job_dto.session_name:
        session_name = task_dto.job_dto.session_name
    motioncor_task = create_motioncor_task(
        image_path=full_image_path,
        task_id=task_id,
        job_id=job_id,
        gain_path=gain_path,
        defects_path=defects_path,
        session_name=session_name,
        task_dto=task_dto,
        motioncor_settings=motioncor_settings
    )

    if motioncor_task:
        return push_task_to_task_queue(motioncor_task)
    return False




