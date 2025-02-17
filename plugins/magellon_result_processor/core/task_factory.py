import os
import uuid
from typing import Dict, Any
from uuid import  UUID

from core.model_dto import FftTaskData, CtfTaskData, TaskDto, FFT_TASK, CTF_TASK, PENDING, TaskCategory, TaskStatus, \
    CtfTask, FftTask


class TaskFactory:
    @classmethod
    def create_task(cls, pid: UUID, job_id: UUID, ptype: TaskCategory, pstatus: TaskStatus, instance_id: UUID,
                    data: Dict[str, Any]) -> TaskDto:
        return TaskDto.create(pid, job_id, ptype, pstatus, instance_id, data)


class CtfTaskFactory(TaskFactory):
    @classmethod
    def create_task(cls, pid: UUID, job_id: UUID, ptype: TaskCategory, pstatus: TaskStatus, instance_id: UUID,
                    data: Dict[str, Any]) -> CtfTask:

        if data is None:
            ctf_data = CtfTaskData(
                image_id=uuid.uuid4(),
                image_name="Image1",
                image_path=os.path.join(os.getcwd(), "gpfs", "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"),
                inputFile=os.path.join(os.getcwd(), "gpfs", "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"),
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
                defocusSearchStep=100,
                binning_x=1
            ).model_dump()
        else:
            ctf_data = data

        return CtfTask.create(
            pid,  # Assuming `id` is a unique identifier for the task
            job_id,
            ptype,
            pstatus,
            instance_id,
            ctf_data
        )


class FftTaskFactory(TaskFactory):
    @classmethod
    def create_task(cls, pid: UUID, job_id: UUID, ptype: TaskCategory, pstatus: TaskStatus, instance_id: UUID,
                    data: Dict[str, Any]) -> FftTask:
        return FftTask.create(
            pid,  # Assuming `id` is a unique identifier for the task
            job_id,
            ptype,
            pstatus,
            instance_id,
            data
        )
