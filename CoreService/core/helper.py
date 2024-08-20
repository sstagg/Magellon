import logging
import math
import os
# import pdb
import re
import uuid

from pydantic import BaseModel

from config import app_settings
from core.rabbitmq_client import RabbitmqClient
from core.task_factory import CtfTaskFactory
from models.plugins_models import TaskDto, CtfTaskData, TaskResultDto, CTF_TASK, PENDING
from models.pydantic_models import LeginonFrameTransferTaskDto

logger = logging.getLogger(__name__)


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


def push_result_to_out_queue(result: TaskResultDto):
    return publish_message_to_queue(result, app_settings.rabbitmq_settings.CTF_OUT_QUEUE_NAME)


def push_task_to_task_queue(task: TaskDto):
    return publish_message_to_queue(task, app_settings.rabbitmq_settings.CTF_QUEUE_NAME)


def dispatch_ctf_task(image_id, full_image_path, task_dto: LeginonFrameTransferTaskDto):
    file_name = os.path.splitext(os.path.basename(full_image_path))[0]

    #converting LeginonFrameTransferTaskDto to ctf task
    session_name = file_name.split("_")[0]
    out_file_name = f"{file_name}_ctf_output.mrc"
    ctf_task_data = CtfTaskData(
        image_id=image_id,
        image_name=file_name,
        image_path=full_image_path,
        inputFile=full_image_path,
        outputFile=out_file_name,
        pixelSize= max(1, math.ceil(task_dto.pixel_size * 10**10)),  #1
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
    ctf_task = CtfTaskFactory.create_task(pid=str(uuid.uuid4()), instance_id=uuid.uuid4(), job_id=uuid.uuid4(),
                                          data=ctf_task_data.model_dump(), ptype=CTF_TASK, pstatus=PENDING)
    ctf_task.sesson_name = session_name
    return push_task_to_task_queue(ctf_task)

# async def dispatch_ctf_task(task_dto : LeginonFrameTransferTaskDto):
#     file_name = os.path.splitext(os.path.basename(full_image_path))[0]
#     session_name = file_name.split("_")[0]
#     out_file_name = f"{file_name}_ctf_output.mrc"
#     ctf_task_data = CtfTaskData(
#         image_id=image_id,
#         image_name="Image1",
#         image_path=full_image_path,
#         inputFile=full_image_path,
#         outputFile=out_file_name,
#         pixelSize=1,
#         accelerationVoltage=300,
#         sphericalAberration=2.7,
#         amplitudeContrast=0.07,
#         sizeOfAmplitudeSpectrum=512,
#         minimumResolution=30,
#         maximumResolution=5,
#         minimumDefocus=5000,
#         maximumDefocus=50000,
#         defocusSearchStep=100
#     )
#     ctf_task = CtfTaskFactory.create_task(pid=str(uuid.uuid4()), instance_id=uuid.uuid4(), job_id=uuid.uuid4(),
#                                           data=ctf_task_data.model_dump(), ptype=CTF_TASK, pstatus=PENDING)
#     ctf_task.sesson_name = session_name
#     return push_task_to_task_queue(ctf_task)
