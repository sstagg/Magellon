"""Shared task factories.

Historically each plugin carried its own ``core/task_factory.py`` —
near-identical code with one factory per task type. Consolidated here so
new plugins can ``from magellon_sdk.task_factory import CtfTaskFactory``
without copy-pasting.

The sample-data branches (``if data is None``) are legacy scaffolding
used by ``test_publish.py`` scripts; they are preserved verbatim so call
sites behave exactly as before.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict
from uuid import UUID

from magellon_sdk.models import (
    CryoEmMotionCorTaskData,
    CtfTask,
    CtfTaskData,
    FftTask,
    MotioncorTask,
    TaskCategory,
    TaskDto,
    TaskStatus,
)


class TaskFactory:
    @classmethod
    def create_task(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> TaskDto:
        return TaskDto.create(pid, job_id, ptype, pstatus, instance_id, data)


class CtfTaskFactory(TaskFactory):
    @classmethod
    def create_task(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> CtfTask:
        if data is None:
            ctf_data = CtfTaskData(
                image_id=uuid.uuid4(),
                image_name="Image1",
                image_path=os.path.join(
                    os.getcwd(),
                    "gpfs",
                    "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
                ),
                inputFile=os.path.join(
                    os.getcwd(),
                    "gpfs",
                    "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc",
                ),
                outputFile="23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex_ctf_output.mrc",
                pixelSize=1,
                binning_x=1,
                accelerationVoltage=300,
                sphericalAberration=2.7,
                amplitudeContrast=0.07,
                sizeOfAmplitudeSpectrum=512,
                minimumResolution=30,
                maximumResolution=5,
                minimumDefocus=5000,
                maximumDefocus=50000,
                defocusSearchStep=100,
            ).model_dump()
        else:
            ctf_data = data

        return CtfTask.create(pid, job_id, ptype, pstatus, instance_id, ctf_data)


class MotioncorTaskFactory(TaskFactory):
    @classmethod
    def create_task(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> MotioncorTask:
        if data is None:
            motioncor_data = CryoEmMotionCorTaskData(
                image_id=uuid.uuid4(),
                image_name="Image1",
                image_path=os.path.join(
                    os.getcwd(),
                    "gpfs",
                    "24mar28a_s_00012gr_00018sq_v01_00019hl_00007ex.frames.tif",
                ),
                inputFile=os.path.join(
                    os.getcwd(),
                    "gpfs",
                    "24mar28a_s_00012gr_00018sq_v01_00019hl_00007ex.frames.tif",
                ),
                InTiff=os.path.join(
                    os.getcwd(),
                    "gpfs",
                    "24mar28a_s_00012gr_00018sq_v01_00019hl_00007ex.frames.tif",
                ),
                OutMrc="output.files.mrc",
                Gain=os.path.join(
                    os.getcwd(),
                    "gpfs",
                    "20240328_04283_gain_multi_ref_superres.mrc",
                ),
                PatchesX=5,
                PatchesY=5,
                SumRangeMinDose=0,
                SumRangeMaxDose=0,
                FmDose=0.75,
                PixSize=0.705,
                Group=3,
            ).model_dump()
        else:
            motioncor_data = data

        return MotioncorTask.create(
            pid, job_id, ptype, pstatus, instance_id, motioncor_data
        )


class FftTaskFactory(TaskFactory):
    @classmethod
    def create_task(
        cls,
        pid: UUID,
        job_id: UUID,
        ptype: TaskCategory,
        pstatus: TaskStatus,
        instance_id: UUID,
        data: Dict[str, Any],
    ) -> FftTask:
        return FftTask.create(pid, job_id, ptype, pstatus, instance_id, data)


__all__ = [
    "CtfTaskFactory",
    "FftTaskFactory",
    "MotioncorTaskFactory",
    "TaskFactory",
]
