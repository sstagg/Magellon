import json
import pdb
import time
import logging
import asyncio
from core.helper import append_json_to_file, parse_message_to_task_object, parse_message_to_task_result_object
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from pika.exceptions import ConnectionClosedByBroker
from service.service import do_execute

file_path = "output_file.json"
logger = logging.getLogger(__name__)
settings = AppSettingsSingleton.get_instance().rabbitmq_settings
rabbitmq_client = RabbitmqClient(settings)  # Create the client with settings


def process_message(ch, method, properties, body):
    try:
        # pdb.set_trace()

        # logger.info("Just Got Message : ",body.decode("utf-8"))
        append_json_to_file(file_path, body.decode("utf-8"))  # just for testing , it adds a record to output_file.json
        the_task = parse_message_to_task_result_object(body.decode("utf-8"))
        # the_task_data = extract_task_data_from_object(the_task)
        asyncio.run(do_execute(task_result_param=the_task))
        # Acknowledge the message
        #ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON: ", e)
        # Optionally, you can reject or handle the message differently in case of a JSON decoding error
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"Error processing message: ", e)


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


queues_and_callbacks = [(AppSettingsSingleton.get_instance().rabbitmq_settings.QUEUE_NAME, process_message), ]
