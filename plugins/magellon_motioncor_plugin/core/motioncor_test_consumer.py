"""
Consumer for motioncor test tasks.
Listens to the motioncor test input queue, processes tasks, and sends results to output queue.
"""

import json
import logging
import asyncio
from datetime import datetime

from core.helper import publish_message_to_queue, append_json_to_file
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from core.model_dto import TaskDto, TaskResultDto, COMPLETED, FAILED
from pika.exceptions import ConnectionClosedByBroker
from service.service import do_execute

logger = logging.getLogger(__name__)

# For testing/debugging - log all messages
log_file_path = "motioncor_test_messages.json"


def parse_message_to_task_object(message_str: str) -> TaskDto:
    """Parse a JSON message string to a TaskDto object."""
    try:
        message_dict = json.loads(message_str)
        return TaskDto.parse_obj(message_dict)
    except Exception as e:
        logger.error(f"Error parsing task message: {e}")
        raise


def process_message(ch, method, properties, body):
    """
    Process a motioncor test task from the queue.
    
    This callback:
    1. Parses the incoming task
    2. Logs it for debugging
    3. Executes the task
    4. Publishes result to output queue
    5. Acknowledges the message
    """
    try:
        message_text = body.decode("utf-8")
        logger.info(f"Received motioncor test task message")
        
        # Log message for debugging
        append_json_to_file(log_file_path, message_text)
        
        # Parse task
        the_task = parse_message_to_task_object(message_text)
        
        logger.info(f"Processing motioncor test task {the_task.id}")
        
        # Execute the task asynchronously
        result = asyncio.run(do_execute(params=the_task))
        
        # Create result object
        task_result = TaskResultDto(
            id=the_task.id,
            job_id=the_task.job_id,
            type=the_task.type,
            status=COMPLETED if result.get("success") else FAILED,
            result=result,
            started_on=the_task.start_on,
            ended_on=datetime.now()
        )
        
        # Publish result to output queue
        output_queue_name = AppSettingsSingleton.get_instance().rabbitmq_settings.MOTIONCOR_TEST_OUT_QUEUE_NAME
        publish_message_to_queue(task_result, output_queue_name)
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Successfully processed motioncor test task {the_task.id}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON in motioncor test message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing motioncor test message: {e}")
        # Don't requeue on error
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def consumer_engine():
    """
    Main consumer engine that connects to RabbitMQ and starts consuming messages.
    """
    settings = AppSettingsSingleton.get_instance().rabbitmq_settings
    rabbitmq_client = RabbitmqClient(settings)
    
    try:
        rabbitmq_client.connect()
        
        queue_name = settings.MOTIONCOR_TEST_QUEUE_NAME
        logger.info(f"Connecting to queue: {queue_name}")
        
        rabbitmq_client.consume(queue_name, process_message)
        rabbitmq_client.start_consuming()
        
    except ConnectionClosedByBroker as e:
        logger.error(f"Connection to RabbitMQ broker was closed: {e}")
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except Exception as e:
        logger.error(f"Error in consumer engine: {e}")
    finally:
        rabbitmq_client.close_connection()
        logger.info("Consumer stopped")


def consume(queues_and_message_processors):
    """
    Generic consume function for multiple queues.
    
    Args:
        queues_and_message_processors: List of tuples (queue_name, callback_function)
    """
    settings = AppSettingsSingleton.get_instance().rabbitmq_settings
    rabbitmq_client = RabbitmqClient(settings)
    
    try:
        rabbitmq_client.connect()
        
        # Register all queue callbacks
        for queue_name, callback in queues_and_message_processors:
            logger.info(f"Registering consumer for queue: {queue_name}")
            rabbitmq_client.consume(queue_name, callback)
        
        logger.info("Starting message consumption")
        rabbitmq_client.start_consuming()
        
    except ConnectionClosedByBroker as e:
        logger.error(f"Connection to RabbitMQ broker was closed: {e}")
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except Exception as e:
        logger.error(f"Error in consume: {e}")
    finally:
        rabbitmq_client.close_connection()
        logger.info("Consumer stopped")


# Default queue configuration for motioncor test
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Motioncor Test Consumer")
    consumer_engine()
