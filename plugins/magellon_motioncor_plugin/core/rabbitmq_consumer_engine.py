import json
import pdb
import time
import logging
import asyncio
from core.helper import append_json_to_file, parse_message_to_task_object, parse_json_for_cryoemctftask, extract_task_data_from_object, publish_message_to_queue
from core.rabbitmq_client import RabbitmqClient
from core.model_dto import TaskResultDto, CryoEmMotionCorTaskData, COMPLETED, FAILED, TaskDto, TaskCategory, TaskStatus
from core.settings import AppSettingsSingleton
from pika.exceptions import ConnectionClosedByBroker
from service.service import do_execute
from datetime import datetime
from uuid import uuid4
import os

file_path = "output_file.json"
logger = logging.getLogger(__name__)
settings = AppSettingsSingleton.get_instance().rabbitmq_settings
rabbitmq_client = RabbitmqClient(settings)  # Create the client with settings


def process_message(ch, method, properties, body):
    """Process standard motioncor tasks from the regular queue."""
    try:
        # pdb.set_trace()
        # logger.info("Just Got Message : ",body.decode("utf-8"))
        append_json_to_file(file_path, body.decode("utf-8"))  # just for testing , it adds a record to output_file.json
        the_task = parse_message_to_task_object(body.decode("utf-8"))
        # the_task_data = extract_task_data_from_object(the_task)
        asyncio.run(do_execute(params=the_task))
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: " ,e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing message: " ,e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def process_test_message(ch, method, properties, body):
    """Process motioncor test tasks from the test input queue."""
    message_text = None
    try:
        message_text = body.decode("utf-8")
        logger.info(f"Received motioncor test task message")
        append_json_to_file(file_path, message_text)
        
        # Parse the message as TaskDto and extract CryoEmMotionCorTaskData
        task_dto = parse_message_to_task_object(message_text)
        logger.info(f"TaskDto parsed: {task_dto.id}")
        
        # Map TaskDto fields to CryoEmMotionCorTaskData
        # Frontend sends: image_path, gain_path, motioncor_settings (FmDose, PatchesX, PatchesY, Group)
        task_data = task_dto.data if task_dto.data else {}
        
        image_path = task_data.get('image_path', '')
        image_name = os.path.basename(image_path) if image_path else "unknown"
        
        # Create complete CryoEmMotionCorTaskData with all required fields
        motioncor_task_data = CryoEmMotionCorTaskData(
            image_id=uuid4(),
            image_name=image_name,
            image_path=image_path,
            inputFile=image_path,
            outputFile="output.mrc",
            Gain=task_data.get('gain_path', ''),
            DefectFile=task_data.get('defects_path'),
            PatchesX=int(task_data.get('motioncor_settings', {}).get('PatchesX', 5)),
            PatchesY=int(task_data.get('motioncor_settings', {}).get('PatchesY', 5)),
            FmDose=float(task_data.get('motioncor_settings', {}).get('FmDose', 0.75)),
            PixSize=float(task_data.get('motioncor_settings', {}).get('PixSize', 1.0)),
            Group=task_data.get('motioncor_settings', {}).get('Group'),
            Gpu='0'
        )
        
        # Create a proper TaskDto object with all required fields
        test_task_dto = TaskDto(
            id=task_dto.id,
            worker_instance_id=uuid4(),
            job_id=uuid4(),
            data=motioncor_task_data.model_dump(),
            status=task_dto.status if hasattr(task_dto, 'status') else TaskStatus(code=1, name="in_progress", description="Task in progress"),
            type=task_dto.type if hasattr(task_dto, 'type') else TaskCategory(code=5, name="MOTIONCOR", description="Motion Correction"),
            sesson_name=task_data.get('session_name', image_name.split('_')[0] if image_name else 'test'),
            start_on=datetime.now()
        )
        
        logger.info(f"Executing motioncor test task: {task_dto.id}")
        
        # Execute the task with properly formed TaskDto
        result = asyncio.run(do_execute(params=test_task_dto))
        logger.info(f"Motioncor test task execution result: {result}")
        
        # Check if result is a TaskResultDto (successful execution) or error dict
        if isinstance(result, dict) and "error" in result:
            # Error occurred during execution
            error_result = TaskResultDto(
                task_id=task_dto.id,
                status=FAILED,
                message=f"Motioncor test task failed: {result.get('error', 'Unknown error')}",
                output_data=result,
                meta_data=[],
                output_files=[]
            )
            publish_message_to_queue(error_result, "motioncor_test_outqueue")
            logger.error(f"Motioncor test task error published for task: {task_dto.id}")
        else:
            # Result should be a TaskResultDto from do_motioncor
            # Ensure the task_id matches the incoming test task id
            if hasattr(result, 'task_id'):
                # Create a copy with updated task_id to ensure it's properly set
                result_dict = result.model_dump()
                result_dict['task_id'] = task_dto.id
                result = TaskResultDto(**result_dict)
            publish_message_to_queue(result, "motioncor_test_outqueue")
            logger.info(f"Result published for task: {task_dto.id}")
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Motioncor test task completed: {task_dto.id}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing test message: {e}")
        
        # Publish error result to test output queue
        if message_text:
            try:
                task_dto = parse_message_to_task_object(message_text)
                error_result = TaskResultDto(
                    id=task_dto.id,
                    status=FAILED,
                    message=f"Motioncor test task failed: {str(e)}",
                    data={"error": str(e)},
                    timestamp=datetime.now(),
                    meta_data=[],
                    output_files=[]
                )
                publish_message_to_queue(error_result, "motioncor_test_outqueue")
            except:
                pass
        
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# keep a live connection to rabbitmq server and
def consumer_engine():
    while True:
        try:
            consume(queues_and_callbacks)
        except KeyboardInterrupt:
            logger.info('Exiting...')
            break
        except ConnectionClosedByBroker:
            logger.warning('Connection closed by broker. Reconnecting...')
            time.sleep(5)
        except Exception as e:
            logger.error(f'Error: {e}')


def consume(pqueues_and_message_processors):
    # Establish connection
    rabbitmq_client.connect()

    for queue_name, callback in pqueues_and_message_processors:
        # Declare the queue if it doesn't exist
        rabbitmq_client.declare_queue(queue_name)
        rabbitmq_client.consume(queue_name, callback)

    # Start consuming messages
    logger.info('Waiting for messages. To exit press CTRL+C')
    rabbitmq_client.start_consuming()


queues_and_callbacks = [
    (AppSettingsSingleton.get_instance().rabbitmq_settings.QUEUE_NAME, process_message),
    ("motioncor_test_inqueue", process_test_message),  # Test queue uses dedicated handler
]
