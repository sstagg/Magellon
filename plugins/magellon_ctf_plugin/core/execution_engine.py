import json
import time
import pika
import logging

from core.settings import AppSettingsSingleton

from pika.exceptions import ConnectionClosedByBroker
from core.model_dto import TaskDto, CryoEmFftTaskDetailDto
from service.service import execute

logger = logging.getLogger(__name__)


# keep a live connection to rabbitmq server and
def worker_engine():
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


# async def consume(loop):
#     """Setup message listener with the current running loop"""
#     connection = await connect_robust(host=env('RABBIT_HOST', '127.0.0.1'), port=5672, loop=loop)
#     channel = await connection.channel()
#     queue = await channel.declare_queue(env('CONSUME_QUEUE', 'foo_consume_queue'))
#     await queue.consume(self.process_incoming_message, no_ack=False)
#     logger.info('Established pika async listener')
#     return connection

def consume(pqueues_and_callbacks):
    # Establish connection

    credentials = pika.PlainCredentials(AppSettingsSingleton.get_instance().rabbitmq_settings.USER_NAME, AppSettingsSingleton.get_instance().rabbitmq_settings.PASSWORD)
    connection = pika.BlockingConnection(pika.ConnectionParameters(AppSettingsSingleton.get_instance().rabbitmq_settings.HOST_NAME, credentials=credentials))
    channel = connection.channel()

    for queue_name, callback in pqueues_and_callbacks:
        # Declare the queue if it doesn't exist
        channel.queue_declare(queue=('%s' % queue_name), durable=True)
        channel.basic_consume(queue=queue_name, on_message_callback=callback)

    # Start consuming messages
    logger.info('Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


file_path = "output_file.json"


def process_task(ch, method, properties, body):
    try:
        # Decode the JSON message
        message_data = json.loads(body.decode("utf-8"))
        task_object = TaskDto.model_validate_json(body.decode("utf-8"))
        # Your processing logic for the FFT task goes here
        logger.debug(f"Received message: {task_object}")

        # Append the message to a file
        with open(file_path, 'a') as file:
            json.dump(message_data, file)
            file.write('\n')  # Add a newline for each message

        # theData =CryoEmFftTaskData(**task_object.data)
        theData = CryoEmFftTaskDetailDto.model_validate(task_object.data)

        execute(request=theData)
        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: {e}")
        # Optionally, you can reject or handle the message differently in case of a JSON decoding error
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing message: {e}")


queues_and_callbacks = [
    ('fft_tasks_queue', process_task),
]

# def publish_message(message: str, queue_name='fft_tasks_queue') -> bool:
#     try:
#         # Attempt to establish a connection to RabbitMQ
#         credentials = pika.PlainCredentials("rabbit", "behd1d2")
#         connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', credentials=credentials))
#         channel = connection.channel()
#
#         # Declare the queue if it doesn't exist
#         channel.queue_declare(queue=queue_name, durable=True)
#
#         # Publish the message to the queue
#         channel.basic_publish(
#             exchange='',
#             routing_key=('%s' % queue_name),
#             body=message,
#             properties=pika.BasicProperties(
#                 delivery_mode=2,  # Make the message persistent
#             )
#         )
#
#         logger.info("Message published to %s" % queue_name)
#         return True
#
#     except Exception as e:
#         # Handle exceptions, e.g., connection issues, channel errors
#         logger.error(f"Error publishing message: {e}")
#         return False
#
#     finally:
#         # Ensure the connection is closed, even if an exception occurs
#         try:
#             connection.close()
#         except Exception as e:
#             logger.error(f"Error closing connection: {e}")
