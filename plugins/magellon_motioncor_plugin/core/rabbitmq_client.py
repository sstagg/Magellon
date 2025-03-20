import json
import time
import pika
import logging
from pika.exceptions import AMQPConnectionError, ChannelError

logger = logging.getLogger(__name__)

class RabbitmqClient:
    def __init__(self, settings):
        self.settings = settings
        self.connection = None
        self.channel = None

    def connect(self):
        credentials = pika.PlainCredentials(
            self.settings.USER_NAME,
            self.settings.PASSWORD
        )
        parameters = pika.ConnectionParameters(
            host=self.settings.HOST_NAME,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        try:
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Connected to RabbitMQ server")
        except (AMQPConnectionError, ChannelError) as e:
            logger.error(f"Error connecting to RabbitMQ: {e}")

    def close_connection(self):
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
                logger.info("Disconnected from RabbitMQ server")
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

    def declare_queue(self, queue_name):
        self.channel.queue_declare(queue=queue_name, durable=True)
        logger.info(f"Declared queue: {queue_name}")

    def publish_message(self, message, queue_name=None):
        queue_name = queue_name or self.settings.QUEUE_NAME
        self.declare_queue(queue_name)
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Make the message persistent
                )
            )
            logger.info(f"Message published to {queue_name}")
        except (AMQPConnectionError, ChannelError) as e:
            logger.error(f"Error publishing message: {e}")


    def consume(self, queue_name, callback):
        self.declare_queue(queue_name)
        self.channel.basic_consume(queue=queue_name, on_message_callback=callback)

    def start_consuming(self):
        logger.info('Waiting for messages. To exit press CTRL+C')
        self.channel.start_consuming()
