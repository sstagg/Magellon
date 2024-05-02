import logging
import uuid
import os
from core.helper import push_task_to_task_queue
from core.model_dto import FFT_TASK, PENDING, TaskDto, CryoEmCtfTaskData

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
    data1 = CryoEmCtfTaskData(
        image_id=uuid.uuid4(),
        image_name="Image1",
        image_path=os.path.join("/gpfs","23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"),
        inputFile=os.path.join("/gpfs","23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"),
        outputFile="ouput.mrc",
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

    return TaskDto.create(data1.model_dump(), FFT_TASK, PENDING, instance_id1, job_id1)


def create_push_task_to_task_queue():
    task = create_task()
    print("Running Publish with object ", task)
    return push_task_to_task_queue(task)


create_push_task_to_task_queue()
