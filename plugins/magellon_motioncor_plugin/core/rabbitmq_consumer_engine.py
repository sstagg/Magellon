import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from uuid import uuid4

from core.helper import (
    append_json_to_file,
    extract_task_data_from_object,
    parse_json_for_cryoemctftask,
    parse_message_to_task_object,
    publish_message_to_queue,
)
from core.model_dto import (
    COMPLETED,
    FAILED,
    CryoEmMotionCorTaskData,
    TaskCategory,
    TaskDto,
    TaskResultDto,
    TaskStatus,
)
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from pika.exceptions import ConnectionClosedByBroker
from service.service import do_execute

file_path = "output_file.json"
logger = logging.getLogger(__name__)
settings = AppSettingsSingleton.get_instance().rabbitmq_settings
rabbitmq_client = RabbitmqClient(settings)  # Create the client with settings

# One long-lived event loop on a daemon thread — see CTF plugin for rationale.
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def _run_coro(coro):
    """Schedule ``coro`` on the shared loop and block until it finishes.

    Using ``asyncio.run`` per-message would tear down and rebuild a
    loop for every task, stall pika's heartbeat, and break anything
    capturing loop references across calls.
    """
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def process_message(ch, method, properties, body):
    """Process standard motioncor tasks from the regular queue."""
    try:
        append_json_to_file(file_path, body.decode("utf-8"))
        the_task = parse_message_to_task_object(body.decode("utf-8"))
        _run_coro(do_execute(params=the_task))
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error("Error decoding JSON: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error("Error processing message: %s", e)
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
        # Frontend sends: image_path, gain_path, motioncor_settings with all parameters
        task_data = task_dto.data if task_dto.data else {}
        motioncor_settings = task_data.get('motioncor_settings', {})
        
        image_path = task_data.get('image_path', '')
        image_name = os.path.basename(image_path) if image_path else "unknown"
        
        # Create complete CryoEmMotionCorTaskData with all parameters from motioncor_settings
        # Only add parameters that are provided, let defaults handle the rest
        motioncor_task_data = CryoEmMotionCorTaskData(
            image_id=uuid4(),
            image_name=image_name,
            image_path=image_path,
            inputFile=image_path,
            outputFile="output.mrc",
            Gain=task_data.get('gain_path', ''),
            DefectFile=task_data.get('defects_path'),
            PatchesX=int(motioncor_settings.get('PatchesX', 5)) if 'PatchesX' in motioncor_settings else 5,
            PatchesY=int(motioncor_settings.get('PatchesY', 5)) if 'PatchesY' in motioncor_settings else 5,
            FmDose=float(motioncor_settings['FmDose']) if 'FmDose' in motioncor_settings else None,
            PixSize=float(motioncor_settings['PixSize']) if 'PixSize' in motioncor_settings else None,
            kV=int(motioncor_settings.get('kV', 300)) if 'kV' in motioncor_settings else 300,
            Group=int(motioncor_settings['Group']) if 'Group' in motioncor_settings else None,
            FtBin=float(motioncor_settings.get('FtBin', 2)) if 'FtBin' in motioncor_settings else 2,
            Iter=int(motioncor_settings.get('Iter', 5)) if 'Iter' in motioncor_settings else 5,
            Tol=float(motioncor_settings.get('Tol', 0.5)) if 'Tol' in motioncor_settings else 0.5,
            Bft=int(motioncor_settings.get('Bft_global', 100)) if 'Bft_global' in motioncor_settings else 100,
            FlipGain=int(motioncor_settings.get('FlipGain', 0)) if 'FlipGain' in motioncor_settings else 0,
            RotGain=int(motioncor_settings.get('RotGain', 0)) if 'RotGain' in motioncor_settings else 0,
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
        result = _run_coro(do_execute(params=test_task_dto))
        logger.info(f"Motioncor test task execution result: {result}")
        
        # Pull the test out-queue from settings instead of hard-coding so
        # deployments can rename it without editing this file.
        test_out_queue = (
            AppSettingsSingleton.get_instance().rabbitmq_settings.MOTIONCOR_TEST_OUT_QUEUE_NAME
            or "motioncor_test_outqueue"
        )

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
            publish_message_to_queue(error_result, test_out_queue)
            logger.error(f"Motioncor test task error published for task: {task_dto.id}")
        elif hasattr(result, "model_dump"):
            # Real TaskResultDto from do_motioncor — patch task_id and publish.
            result_dict = result.model_dump()
            result_dict['task_id'] = task_dto.id
            publish_message_to_queue(TaskResultDto(**result_dict), test_out_queue)
            logger.info(f"Result published for task: {task_dto.id}")
        else:
            # Defensive: do_motioncor returned an unexpected shape (raw dict
            # with no "error" key, or some other Python value). Wrap it in
            # a FAILED TaskResultDto rather than crashing on the publish path.
            unknown_result = TaskResultDto(
                task_id=task_dto.id,
                status=FAILED,
                message="Motioncor test task returned an unexpected result shape",
                output_data={"raw": str(result)[:1000]},
                meta_data=[],
                output_files=[],
            )
            publish_message_to_queue(unknown_result, test_out_queue)
            logger.error(
                "Motioncor test task: unexpected result type %s for task %s",
                type(result).__name__, task_dto.id,
            )
        
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
                publish_message_to_queue(
                    error_result,
                    AppSettingsSingleton.get_instance().rabbitmq_settings.MOTIONCOR_TEST_OUT_QUEUE_NAME
                    or "motioncor_test_outqueue",
                )
            except Exception:
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
