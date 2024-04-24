import re

from core.model_dto import TaskDto, CryoEmCtfTaskData, CryoEmTaskResultDto
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from test_publish import logger


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


def append_json_to_file(file_path, json_str):
    try:
        # Append the JSON string as a new line to the file
        with open(file_path, 'a') as file:
            file.write(json_str + '\n')

        return True  # Success
    except Exception as e:
        print(f"Error appending JSON to file: {e}")
        return False  # Failure


def parse_message_to_task_object(message_str):
    return TaskDto.model_validate_json(message_str)


def extract_task_data_from_object(task_object):
    return CryoEmCtfTaskData.model_validate(task_object.data)


def parse_json_for_cryoemctftask(message_str):
    return CryoEmCtfTaskData.model_validate(TaskDto.model_validate_json(message_str).data)


def push_result_to_out_queue(result : CryoEmTaskResultDto):
    try:
        settings = AppSettingsSingleton.get_instance().rabbitmq_settings
        rabbitmq_client = RabbitmqClient(settings)
        rabbitmq_client.connect()  # Connect to RabbitMQ
        rabbitmq_client.publish_message(result.model_dump_json(), AppSettingsSingleton.get_instance().rabbitmq_settings.OUT_QUEUE_NAME)  # Use client method
        logger.info(f"Message published to {AppSettingsSingleton.get_instance().rabbitmq_settings.OUT_QUEUE_NAME}")
        return True
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False
    finally:
        rabbitmq_client.close_connection() # Disconnect from RabbitMQ
