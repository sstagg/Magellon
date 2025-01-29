import logging
import math
import os
# import pdb
import re
import uuid

from pydantic import BaseModel

from config import app_settings
from core.rabbitmq_client import RabbitmqClient
from core.task_factory import CtfTaskFactory, MotioncorTaskFactory
from models.plugins_models import TaskDto, CtfTaskData, TaskResultDto, CTF_TASK, PENDING, CryoEmMotionCorTaskData, \
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


def parse_message_to_task_object(message_str):
    return TaskDto.model_validate_json(message_str)


def extract_task_data_from_object(task_object):
    return CtfTaskData.model_validate(task_object.data)


def parse_json_for_cryoemctftask(message_str):
    return CtfTaskData.model_validate(TaskDto.model_validate_json(message_str).data)


def publish_message_to_queue(message: BaseModel, queue_name: str) -> bool:
    """
    This function publishes a message to a specified RabbitMQ queue.

    Args:
        message: The message object to be published. Can be either a CryoEmTaskResultDto or a TaskDto.
        queue_name: The name of the RabbitMQ queue to publish to.

    Returns:
        True on success, False on error.
    """

    try:
        destination_dir =os.path.join("/magellon", "messages", queue_name )
        # Create the destination directory if it doesn't exist
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        append_json_to_file( os.path.join(destination_dir,"messages.json") , message.model_dump_json())
    except Exception as e:
        print(f"Error: {e}")


    try:
        settings = app_settings.rabbitmq_settings
        rabbitmq_client = RabbitmqClient(settings)
        rabbitmq_client.connect()  # Connect to RabbitMQ
        # pdb.set_trace()
        rabbitmq_client.publish_message(message.model_dump_json(), queue_name)  # Use client method
        logger.info(f"Message published to {queue_name}")
        return True
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False
    finally:
        rabbitmq_client.close_connection()  # Disconnect from RabbitMQ

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
        # Add other task types and their corresponding queues here
        # FFT_TASK: {
        #     'task': app_settings.rabbitmq_settings.FFT_QUEUE_NAME,
        #     'result': app_settings.rabbitmq_settings.FFT_OUT_QUEUE_NAME
        # },
        # PARTICLE_PICKING: {
        #     'task': app_settings.rabbitmq_settings.PARTICLE_PICKING_QUEUE_NAME,
        #     'result': app_settings.rabbitmq_settings.PARTICLE_PICKING_OUT_QUEUE_NAME
        # },
        # TWO_D_CLASSIFICATION: {
        #     'task': app_settings.rabbitmq_settings.TWO_D_CLASSIFICATION_QUEUE_NAME,
        #     'result': app_settings.rabbitmq_settings.TWO_D_CLASSIFICATION_OUT_QUEUE_NAME
        # }
    }

    if task_type.code not in queue_mapping:
        return None

    return queue_mapping[task_type.code]['result' if is_result else 'task']

# def push_task_to_task_queue(task: TaskDto):
#     return publish_message_to_queue(task, app_settings.rabbitmq_settings.CTF_QUEUE_NAME)

def push_task_to_task_queue(task: TaskDto) -> bool:
    """
    Push a task to its appropriate queue based on task type

    Args:
        task (TaskDto): Task to be published

    Returns:
        bool: True if successfully published, False otherwise
    """
    try:
        queue_name = get_queue_name_by_task_type(task.type, is_result=False)
        if not queue_name:
            logger.error(f"No queue found for task type: {task.type}")
            return False

        return publish_message_to_queue(task, queue_name)
    except Exception as e:
        logger.error(f"Error pushing task to queue: {e}")
        return False


def push_result_to_out_queue(result: TaskResultDto) -> bool:
    """
    Push a task result to its appropriate output queue based on task type

    Args:
        result (TaskResultDto): Result to be published

    Returns:
        bool: True if successfully published, False otherwise
    """
    try:
        queue_name = get_queue_name_by_task_type(result.type, is_result=True)
        if not queue_name:
            logger.error(f"No result queue found for task type: {result.type}")
            return False

        return publish_message_to_queue(result, queue_name)
    except Exception as e:
        logger.error(f"Error pushing result to queue: {e}")
        return False



def dispatch_ctf_task(task_id, full_image_path, task_dto: ImportTaskDto):
    file_name = os.path.splitext(os.path.basename(full_image_path))[0]

    #converting LeginonFrameTransferTaskDto to ctf task
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
        sphericalAberration=task_dto.spherical_aberration * 1000,  #    2.7,
        amplitudeContrast=task_dto.amplitude_contrast,
        sizeOfAmplitudeSpectrum=task_dto.size_of_amplitude_spectrum,
        minimumResolution=task_dto.minimum_resolution,
        maximumResolution=task_dto.maximum_resolution,
        minimumDefocus=task_dto.minimum_defocus,
        maximumDefocus=task_dto.maximum_defocus,
        defocusSearchStep=task_dto.defocus_search_step
    )

    job_id = task_dto.job_dto.job_id if getattr(task_dto, 'job_dto', None) else task_dto.job_id
    # job_id = getattr(task_dto.job_dto, 'job_id', getattr(task_dto, 'job_id', None))


    # str(uuid.uuid4())
    ctf_task = CtfTaskFactory.create_task(pid=task_dto.task_id, instance_id=uuid.uuid4(), job_id=job_id,
                                          data=ctf_task_data.model_dump(), ptype=CTF_TASK, pstatus=PENDING)
    ctf_task.sesson_name = session_name
    return push_task_to_task_queue(ctf_task)


def create_motioncor_task_data(image_path, gain_path, session_name=None):
    """
    Create the common MotionCor task data structure used across different task creation methods.

    Args:
        image_path (str): Path to the input image file
        gain_path (str): Path to the gain reference file
        session_name (str, optional): Session name to use. If None, will be extracted from filename

    Returns:
        CryoEmMotionCorTaskData: Configured task data object
    """
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    if session_name is None:
        session_name = file_name.split("_")[0]

    return CryoEmMotionCorTaskData(
        image_id=uuid.uuid4(),
        image_name="Image1",
        image_path=image_path,
        inputFile=image_path,
        OutMrc="output.files.mrc",
        Gain=gain_path,
        PatchesX=5,
        PatchesY=5,
        SumRangeMinDose=0,
        SumRangeMaxDose=0,
        FmDose=0.75,
        PixSize=0.705,
        Group=3
    )


def create_motioncor_task(image_path=None, gain_path=None, session_name=None, task_id=None, job_id=None):
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
    """

    try:
        # Use provided paths or defaults
        default_image = os.path.join(os.getcwd(), "gpfs", "20241203_54449_integrated_movie.mrc.tif")
        default_gain = os.path.join(os.getcwd(), "gpfs", "20241202_53597_gain_multi_ref.tif")

        image_path = image_path or default_image
        gain_path = gain_path or default_gain

        task_data = create_motioncor_task_data(image_path, gain_path, session_name)

        motioncor_task = MotioncorTaskFactory.create_task(
            pid=task_id or str(uuid.uuid4()),
            instance_id=uuid.uuid4(),
            job_id=job_id or uuid.uuid4(),
            data=task_data.model_dump(),
            ptype=MOTIONCOR_TASK,
            pstatus=PENDING
        )
        motioncor_task.sesson_name = session_name or "24mar28a"
        return motioncor_task
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False


def dispatch_motioncor_task(task_id, full_image_path, task_dto: ImportTaskDto):
    """
    Creates and dispatches a MotionCor task based on an import task DTO

    Args:
        task_id (str): ID for the new task
        full_image_path (str): Path to the input image file
        task_dto (ImportTaskDto): Import task data transfer object

    Returns:
        bool: True if task was successfully pushed to queue
    """
    job_id = task_dto.job_dto.job_id if getattr(task_dto, 'job_dto', None) else task_dto.job_id

    motioncor_task = create_motioncor_task(
        image_path=full_image_path,
        task_id=task_id,
        job_id=job_id
    )

    if motioncor_task:
        return push_task_to_task_queue(motioncor_task)
    return False





