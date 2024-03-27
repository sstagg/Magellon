import logging

from aio_pika import connect, Message, IncomingMessage, connect_robust

logger = logging.getLogger(__name__)


async def publish_message(message: str):
    connection = await connect_robust("amqp://rabbit:behd1d2@localhost/")
    channel = await connection.channel()
    await channel.default_exchange.publish(Message(message.encode()), routing_key="tasks_queue")
    await connection.close()
    logger.info('Message published to Rabbit')


async def consume_queue():
    while True:
        print("hello")
    logger.info('starting consume_queue')
    connection = await connect_robust("amqp://rabbit:behd1d2@localhost/")

    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("tasks_queue")
        await queue.consume(process_message)  # Assuming process_message is defined somewhere

    logger.info('Established pika async listener')
    return connection


async def process_message(message: IncomingMessage):
    try:
        body = message.body
        await  message.ack()
        # Process the message asynchronously
        logger.info(f"Received message: {message.body}")
        # Simulate some processing that might raise an exception

    except Exception as e:
        # Handle the exception (replace this with your actual exception handling logic)
        logger.error(f"Error processing message: {e}")
