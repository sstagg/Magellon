import os
import uuid
from typing import Dict, Any
from uuid import  UUID

from core.model_dto import FftTaskData, CryoEmMotionCorTaskData, MotioncorTask, TaskDto, FFT_TASK, CTF_TASK, PENDING, TaskCategory, TaskStatus, FftTask


class TaskFactory:
    @classmethod
    def create_task(cls, pid: UUID, job_id: UUID, ptype: TaskCategory, pstatus: TaskStatus, instance_id: UUID,
                    data: Dict[str, Any]) -> TaskDto:
        return TaskDto.create(pid, job_id, ptype, pstatus, instance_id, data)


class MotioncorTaskFactory(TaskFactory):
    @classmethod
    def create_task(cls, pid: UUID, job_id: UUID, ptype: TaskCategory, pstatus: TaskStatus, instance_id: UUID,
                    data: Dict[str, Any]) -> MotioncorTask:
        print(data)
        if data is None:
            motioncordata = CryoEmMotionCorTaskData(
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
        ).model_dump()
        else:
            motioncor_data = data

        return MotioncorTask.create(
            pid,  # Assuming `id` is a unique identifier for the task
            job_id,
            ptype,
            pstatus,
            instance_id,
            motioncor_data
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
