"""
Result processor for motioncor test tasks.
Listens to the output queue and sends results to connected WebSocket clients.
"""

import json
import logging
import asyncio
from typing import Optional

from core.helper import append_json_to_file
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from core.model_dto import TaskResultDto
from pika.exceptions import ConnectionClosedByBroker

logger = logging.getLogger(__name__)

# For testing/debugging
log_file_path = "motioncor_test_results.json"


def parse_message_to_task_result_object(message_str: str) -> TaskResultDto:
    """Parse a JSON message string to a TaskResultDto object."""
    try:
        message_dict = json.loads(message_str)
        return TaskResultDto.parse_obj(message_dict)
    except Exception as e:
        logger.error(f"Error parsing result message: {e}")
        raise


async def process_result_message(ch, method, properties, body):
    """
    Process a task result from the motioncor test output queue.
    
    This callback:
    1. Parses the result
    2. Logs it for debugging
    3. Sends it to any connected WebSocket clients
    4. Acknowledges the message
    """
    try:
        message_text = body.decode("utf-8")
        logger.info(f"Received motioncor test result")
        
        # Log message for debugging
        append_json_to_file(log_file_path, message_text)
        
        # Parse result
        task_result = parse_message_to_task_result_object(message_text)
        
        logger.info(f"Processing result for task {task_result.id}")
        
        # Import here to avoid circular imports
        from services.motioncor_test_service import send_result, send_error
        
        task_id = str(task_result.id)
        
        # Check if result was successful
        if task_result.status.name == "COMPLETED":
            # Send successful result to WebSocket clients
            # Convert TaskResultDto to dictionary for WebSocket transmission
            result_data = task_result.model_dump()
            await send_result(task_id, result_data)
            logger.info(f"Sent result for task {task_id} to WebSocket clients")
        else:
            # Send error to WebSocket clients
            error_message = task_result.message or "Task failed"
            await send_error(task_id, error_message)
            logger.warning(f"Sent error for task {task_id} to WebSocket clients")
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON in result message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing result message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def process_result_message_sync(ch, method, properties, body):
    """
    Synchronous wrapper for process_result_message.
    RabbitMQ callbacks need to be synchronous, so we run the async function in a new event loop.
    """
    try:
        # Create a new event loop for this callback
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_result_message(ch, method, properties, body))
    except Exception as e:
        logger.error(f"Error in process_result_message_sync: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def result_consumer_engine():
    """
    Main result consumer engine that connects to RabbitMQ and starts consuming results.
    """
    settings = AppSettingsSingleton.get_instance().rabbitmq_settings
    rabbitmq_client = RabbitmqClient(settings)
    
    try:
        rabbitmq_client.connect()
        
        queue_name = settings.MOTIONCOR_TEST_OUT_QUEUE_NAME
        logger.info(f"Connecting to result queue: {queue_name}")
        
        rabbitmq_client.consume(queue_name, process_result_message_sync)
        rabbitmq_client.start_consuming()
        
    except ConnectionClosedByBroker as e:
        logger.error(f"Connection to RabbitMQ broker was closed: {e}")
    except KeyboardInterrupt:
        logger.info("Result consumer interrupted by user")
    except Exception as e:
        logger.error(f"Error in result consumer engine: {e}")
    finally:
        rabbitmq_client.close_connection()
        logger.info("Result consumer stopped")


def consume_results(queues_and_message_processors):
    """
    Generic consume function for multiple result queues.
    
    Args:
        queues_and_message_processors: List of tuples (queue_name, callback_function)
    """
    settings = AppSettingsSingleton.get_instance().rabbitmq_settings
    rabbitmq_client = RabbitmqClient(settings)
    
    try:
        rabbitmq_client.connect()
        
        # Register all queue callbacks
        for queue_name, callback in queues_and_message_processors:
            logger.info(f"Registering result consumer for queue: {queue_name}")
            rabbitmq_client.consume(queue_name, callback)
        
        logger.info("Starting result consumption")
        rabbitmq_client.start_consuming()
        
    except ConnectionClosedByBroker as e:
        logger.error(f"Connection to RabbitMQ broker was closed: {e}")
    except KeyboardInterrupt:
        logger.info("Result consumer interrupted by user")
    except Exception as e:
        logger.error(f"Error in consume_results: {e}")
    finally:
        rabbitmq_client.close_connection()
        logger.info("Result consumer stopped")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting Motioncor Test Result Processor")
    result_consumer_engine()
