"""
Result processor for motioncor test tasks.
Listens to the motioncor test output queue and broadcasts results to WebSocket clients.
"""

import json
import logging
import asyncio
from datetime import datetime

from core.rabbitmq_client import RabbitmqClient
from config import app_settings
from models.plugins_models import TaskResultDto
from services.motioncor_test_service import broadcast_to_task_connections

logger = logging.getLogger(__name__)


def process_result_message(ch, method, properties, body):
    """
    Process a motioncor test result from the output queue and broadcast to WebSocket clients.
    
    This callback:
    1. Parses the incoming result
    2. Broadcasts to all connected WebSocket clients for that task
    3. Acknowledges the message
    """
    try:
        message_text = body.decode("utf-8")
        logger.info(f"Received motioncor test result message")
        
        # Parse the result message
        result_dict = json.loads(message_text)
        # Try to get task_id first (from TaskResultDto), then fall back to id
        task_id = result_dict.get("task_id") or result_dict.get("id")
        
        logger.info(f"Processing result for task: {task_id}")
        logger.debug(f"Full result dict keys: {list(result_dict.keys())}")
        logger.debug(f"Result code: {result_dict.get('code')}, Message: {result_dict.get('message')}")
        
        # Check if result has output_files
        output_files = result_dict.get('output_files', [])
        logger.info(f"Result has {len(output_files)} output file(s)")
        
        # Broadcast the full result to all connected WebSocket clients
        broadcast_message = {
            "type": "result",
            "task_id": task_id,
            "status": "completed" if result_dict.get("code", 200) < 400 else "failed",
            "data": result_dict,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.debug(f"Broadcasting message with keys: {list(broadcast_message.keys())}")
        logger.debug(f"Data section has keys: {list(result_dict.keys())}")
        
        asyncio.run(broadcast_to_task_connections(
            task_id,
            broadcast_message
        ))
        logger.info(f"Successfully broadcasted result for task: {task_id}")
        
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Result processed and broadcasted for task: {task_id}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON result: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing result message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def result_consumer_engine():
    """
    Main consumer engine for the motioncor test output queue.
    Listens to results and broadcasts them to WebSocket clients.
    """
    logger.info("Starting Motioncor Test Result Processor")
    
    rabbitmq_settings = app_settings.rabbitmq_settings
    rabbitmq_client = RabbitmqClient(rabbitmq_settings)
    
    try:
        # Connect to RabbitMQ
        rabbitmq_client.connect()
        logger.info("Connected to RabbitMQ")
        
        # Declare the output queue
        queue_name = "motioncor_test_outqueue"
        rabbitmq_client.declare_queue(queue_name)
        logger.info(f"Declared queue: {queue_name}")
        
        # Set up consumer callback
        rabbitmq_client.consume(queue_name, process_result_message)
        logger.info(f"Started consuming from queue: {queue_name}")
        
        # Start consuming messages
        logger.info("Waiting for result messages. To exit press CTRL+C")
        rabbitmq_client.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Result processor interrupted by user")
    except Exception as e:
        logger.error(f"Error in result consumer engine: {e}")
    finally:
        rabbitmq_client.close_connection()
        logger.info("Result processor stopped")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    result_consumer_engine()
