import logging
import uuid

from core.model_dto import FFT_TASK, PENDING, TaskDto, CryoEmCtfTaskData
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton

logger = logging.getLogger(__name__)


# def publish1():
#     data1 = {"key1": "value1", "key2": "value2"}
#     instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
#     job_id1 = uuid.uuid4()  # Replace with your specific job ID
#
#     task1 = TaskDto.create(data1, FFT_TASK, PENDING, instance_id1, job_id1)
#
#     publish_message(task1.model_dump_json())
#     return task1.model_dump_json()
#
#
# def publish2():
#     data1 = CryoEmFftTaskDetailDto(
#         image_id=uuid.uuid4(),
#         image_name="Image1",
#         image_path=r"C:\temp\target\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW.mrc",
#         target_name="Target1",
#         target_path=r"C:\temp\target\results\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW.png",
#         # frame_name="Frame1",
#         # frame_path="/path/to/frame1"
#     )
#     instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
#     job_id1 = uuid.uuid4()  # Replace with your specific job ID
#
#     task1 = TaskDto.create(data1.model_dump(), FFT_TASK, PENDING, instance_id1, job_id1)
#
#     publish_message(task1.model_dump_json())
#     return task1.model_dump_json()


def push_task_to_task_queue():
    print("Running Publish")

    data1 = CryoEmCtfTaskData(
        image_id=uuid.uuid4(),
        image_name="Image1",
        image_path=r"/gpfs/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
        inputFile=r"/gpfs/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
        outputFile="ouput.txt",
        pixelSize=1,
        accelerationVoltage=300,
        sphericalAberration=2.7,
        amplitudeContrast=0.07,
        sizeOfAmplitudeSpectrum=512,
        minimumResolution=30,
        maximumResolution=5,
        minimumDefocus=5000,
        maximumDefocus=50000,
        defocusSearchStep=100
    )

    instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
    job_id1 = uuid.uuid4()  # Replace with your specific job ID

    task1 = TaskDto.create(data1.model_dump(), FFT_TASK, PENDING, instance_id1, job_id1)

    try:
        settings = AppSettingsSingleton.get_instance().rabbitmq_settings
        rabbitmq_client = RabbitmqClient(settings)
        rabbitmq_client.connect()  # Connect to RabbitMQ
        rabbitmq_client.publish_message(task1.model_dump_json(), AppSettingsSingleton.get_instance().rabbitmq_settings.QUEUE_NAME)  # Use client method
        logger.info(f"Message published to {AppSettingsSingleton.get_instance().rabbitmq_settings.QUEUE_NAME}")
        return True
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False
    finally:
        rabbitmq_client.close_connection() # Disconnect from RabbitMQ
    return task1.model_dump_json()


push_task_to_task_queue()

