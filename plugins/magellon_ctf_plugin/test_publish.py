import logging
import uuid
import os
from core.helper import push_task_to_task_queue
from core.model_dto import FFT_TASK, PENDING, TaskDto, CtfTaskData, CTF_TASK
from core.task_factory import CtfTaskFactory

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
    ctf_task_data = CtfTaskData(
        image_id=uuid.uuid4(),
        image_name="Image1",
        image_path=os.path.join( "/gpfs/24jun28a/rawdata", "24jun28a_Valle001-04_00011gr_00002sq_v01_00002hl_00001fc.mrc"),
        inputFile=os.path.join( "/gpfs/24jun28a/rawdata", "24jun28a_Valle001-04_00011gr_00002sq_v01_00002hl_00001fc.mrc"),

        # image_path=os.path.join(os.getcwd(), "gpfs", "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"),
        # inputFile=os.path.join(os.getcwd(), "gpfs", "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"),

        # image_path= "/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
        # inputFile="/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
        outputFile="23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex_ctf_output.mrc",
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

    ctf_task = CtfTaskFactory.create_task(pid=str(uuid.uuid4()), instance_id=uuid.uuid4(), job_id=uuid.uuid4(),
                                      data=ctf_task_data.model_dump(), ptype=CTF_TASK, pstatus=PENDING)
    ctf_task.sesson_name="23oct13x"
    return ctf_task
    # return TaskDto.create(ctf_task_data.model_dump(), FFT_TASK, PENDING, instance_id1, job_id1)


def create_push_task_to_task_queue():
    task = create_task()
    print("Running Publish with object ", task)
    return push_task_to_task_queue(task)


create_push_task_to_task_queue()
