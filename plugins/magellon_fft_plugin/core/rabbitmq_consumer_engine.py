import asyncio
import json
import logging
import threading
import time

from core.helper import append_json_to_file, parse_message_to_task_object
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from pika.exceptions import ConnectionClosedByBroker
from service.service import do_execute

file_path = "output_file.json"
logger = logging.getLogger(__name__)
settings = AppSettingsSingleton.get_instance().rabbitmq_settings
rabbitmq_client = RabbitmqClient(settings)


# One long-lived event loop on a daemon thread — same pattern as CTF/MotionCor
# (daemon loop thread + run_coroutine_threadsafe). asyncio.run() per message
# would recreate the loop on every task and stall pika's heartbeat.
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def process_message(ch, method, properties, body):
    try:
        append_json_to_file(file_path, body.decode("utf-8"))
        the_task = parse_message_to_task_object(body.decode("utf-8"))
        future = asyncio.run_coroutine_threadsafe(do_execute(params=the_task), _loop)
        future.result()
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error("Error decoding JSON: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error("Error processing message: %s", e)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


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
    rabbitmq_client.connect()

    for queue_name, callback in pqueues_and_message_processors:
        rabbitmq_client.declare_queue(queue_name)
        rabbitmq_client.consume(queue_name, callback)

    logger.info('Waiting for messages. To exit press CTRL+C')
    rabbitmq_client.start_consuming()


queues_and_callbacks = [
    (AppSettingsSingleton.get_instance().rabbitmq_settings.QUEUE_NAME, process_message),
]
