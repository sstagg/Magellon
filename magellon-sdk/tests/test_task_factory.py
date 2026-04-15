"""Task factory tests.

Each factory turns a raw ``data`` dict into the concrete ``*Task`` model.
The ``data is None`` branches are documented sample-data scaffolding and
are exercised here to keep them working until callers are retired.
"""
from __future__ import annotations

from uuid import uuid4

from magellon_sdk.models import (
    CTF_TASK,
    FFT_TASK,
    MOTIONCOR,
    PENDING,
    CtfTask,
    FftTask,
    MotioncorTask,
    TaskDto,
)
from magellon_sdk.task_factory import (
    CtfTaskFactory,
    FftTaskFactory,
    MotioncorTaskFactory,
    TaskFactory,
)


def _ids():
    return uuid4(), uuid4(), uuid4()


def test_base_task_factory_produces_task_dto():
    pid, job_id, instance = _ids()
    task = TaskFactory.create_task(pid, job_id, CTF_TASK, PENDING, instance, {"k": "v"})

    assert isinstance(task, TaskDto)
    assert task.id == pid
    assert task.job_id == job_id
    assert task.worker_instance_id == instance
    assert task.type == CTF_TASK
    assert task.status == PENDING
    assert task.data == {"k": "v"}


def test_fft_task_factory_returns_fft_task():
    pid, job_id, instance = _ids()
    task = FftTaskFactory.create_task(
        pid, job_id, FFT_TASK, PENDING, instance,
        {"image_id": str(uuid4()), "image_name": "x"},
    )
    assert isinstance(task, FftTask)
    assert task.data.image_name == "x"


def test_ctf_task_factory_with_explicit_data():
    pid, job_id, instance = _ids()
    data = {
        "inputFile": "/tmp/in.mrc",
        "outputFile": "/tmp/out.mrc",
        "pixelSize": 1.2,
    }
    task = CtfTaskFactory.create_task(pid, job_id, CTF_TASK, PENDING, instance, data)
    assert isinstance(task, CtfTask)
    assert task.data.inputFile == "/tmp/in.mrc"
    assert task.data.pixelSize == 1.2


def test_ctf_task_factory_default_sample_data_when_none():
    pid, job_id, instance = _ids()
    task = CtfTaskFactory.create_task(pid, job_id, CTF_TASK, PENDING, instance, None)
    assert isinstance(task, CtfTask)
    assert task.data.inputFile  # sample data populated
    assert task.data.maximumDefocus == 50000


def test_motioncor_task_factory_with_explicit_data():
    pid, job_id, instance = _ids()
    data = {
        "inputFile": "/tmp/movie.tif",
        "Gain": "/tmp/gain.mrc",
        "OutMrc": "aligned.mrc",
    }
    task = MotioncorTaskFactory.create_task(
        pid, job_id, MOTIONCOR, PENDING, instance, data
    )
    assert isinstance(task, MotioncorTask)
    assert task.data.inputFile == "/tmp/movie.tif"
    assert task.data.OutMrc == "aligned.mrc"


def test_motioncor_task_factory_default_sample_data_when_none():
    pid, job_id, instance = _ids()
    task = MotioncorTaskFactory.create_task(
        pid, job_id, MOTIONCOR, PENDING, instance, None
    )
    assert isinstance(task, MotioncorTask)
    assert task.data.Gain  # sample data populated
