import logging
import uuid
import os
from core.helper import push_task_to_task_queue
from core.model_dto import FFT_TASK, PENDING, MOTIONCOR,MotioncorTask,  CryoEmMotionCorTaskData
from core.rabbitmq_client import RabbitmqClient
from core.settings import AppSettingsSingleton
from core.task_factory import MotioncorTaskFactory
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


def create_task():
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
        motioncor_task = MotioncorTaskFactory.create_task(pid=str(uuid.uuid4()), instance_id=uuid.uuid4(), job_id=uuid.uuid4(),
                                      data=data1.model_dump(), ptype=MOTIONCOR, pstatus=PENDING)
        motioncor_task.sesson_name="24mar28a"
        return motioncor_task
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False

def create_push_task_to_task_queue():
    task = create_task()
    print("Running Publish with object ", task)
    return push_task_to_task_queue(task)


create_push_task_to_task_queue()

