import logging
import uuid
import pika

from core.model_dto import FFT_TASK, PENDING, TaskDto, CryoEmFftTaskDetailDto
logger = logging.getLogger(__name__)


def publish_message(message: str, queue_name='fft_tasks_queue') -> bool:
    try:
        # Attempt to establish a connection to RabbitMQ
        credentials = pika.PlainCredentials("rabbit", "behd1d2")
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', credentials=credentials))
        channel = connection.channel()

        # Declare the queue if it doesn't exist
        channel.queue_declare(queue=queue_name, durable=True)

        # Publish the message to the queue
        channel.basic_publish(
            exchange='',
            routing_key=('%s' % queue_name),
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make the message persistent
            )
        )

        logger.info("Message published to %s" % queue_name)
        return True

    except Exception as e:
        # Handle exceptions, e.g., connection issues, channel errors
        logger.error(f"Error publishing message: {e}")
        return False

    finally:
        # Ensure the connection is closed, even if an exception occurs
        try:
            connection.close()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")


def publish1():
    data1 = {"key1": "value1", "key2": "value2"}
    instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
    job_id1 = uuid.uuid4()  # Replace with your specific job ID

    task1 = TaskDto.create(data1, FFT_TASK, PENDING, instance_id1, job_id1)

    publish_message(task1.model_dump_json())
    return task1.model_dump_json()


def publish():
    data1 = CryoEmFftTaskDetailDto(
        image_id=uuid.uuid4(),
        image_name="Image1",
        image_path=r"C:\temp\target\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW.mrc",
        target_name="Target1",
        target_path=r"C:\temp\target\results\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW.png",
        # frame_name="Frame1",
        # frame_path="/path/to/frame1"
    )
    instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
    job_id1 = uuid.uuid4()  # Replace with your specific job ID

    task1 = TaskDto.create(data1.model_dump(), FFT_TASK, PENDING, instance_id1, job_id1)

    publish_message(task1.model_dump_json())
    return task1.model_dump_json()


publish()

