import logging
import uuid
import os
from core.model_dto import FFT_TASK, PENDING, TaskDto,  CryoEmMotionCorTaskData
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
    try:
        data1 = CryoEmMotionCorTaskData(
            image_id=uuid.uuid4(),
            image_name="Image1",
            image_path=os.path.join(os.getcwd(),"gpfs","24mar28a_s_00012gr_00018sq_v01_00019hl_00007ex.frames.tif"),
            inputFile=os.path.join(os.getcwd(),"gpfs","24mar28a_s_00012gr_00018sq_v01_00019hl_00007ex.frames.tif"),
            InTiff=os.path.join(os.getcwd(),"gpfs","24mar28a_s_00012gr_00018sq_v01_00019hl_00007ex.frames.tif"),
            OutMrc="output.files.mrc",
            Gain=os.path.join(os.getcwd(),"gpfs","20240328_04283_gain_multi_ref_superres.mrc"),
        PatchesX= 5,
        PatchesY= 5,
        SumRangeMinDose= 0,
        SumRangeMaxDose= 0,
        FmDose= 0.75,
        PixSize= 0.705,
        Group= 3

        )
        instance_id1 = uuid.uuid4()  # Replace with your specific worker instance ID
        job_id1 = uuid.uuid4()  # Replace with your specific job ID

        task1 = TaskDto.create(data1.model_dump(), FFT_TASK, PENDING, instance_id1, job_id1)

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

