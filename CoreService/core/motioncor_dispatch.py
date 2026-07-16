"""MotionCor task creation + dispatch.

Separate from :mod:`core.dispatch_builders` because MotionCor is the
only category whose task *creation* is also consumed directly by a
controller (``webapp_motioncor_controller`` builds a task without
dispatching it), and its input resolution (frame-file matching, gain /
defects references) is heavier than the other builders.

Split out of ``core.helper`` (2026-07-06); import from here in new code,
``core.helper`` re-exports for existing call sites.
"""
import logging
import os
import uuid

from config import app_settings
from core.file_utils import find_matching_file
from core.paths import to_canonical_gpfs_path
from core.task_dispatch import push_task_to_task_queue
from core.task_factory import MotioncorTaskFactory
from magellon_sdk.models import (
    MOTIONCOR as MOTIONCOR_TASK,
    PENDING,
    MotionCorInput,
)
from models.pydantic_models import ImportTaskDto

logger = logging.getLogger(__name__)


def create_motioncor_task_data(image_path, gain_path, defects_path=None, session_name=None, task_dto: ImportTaskDto=None, motioncor_settings: dict = None):
    """
    Create the common MotionCor task data structure used across different task creation methods.

    Args:
        image_path (str): Path to the input image file
        gain_path (str): Path to the gain reference file
        session_name (str, optional): Session name to use. If None, will be extracted from filename
        task_dto (ImportTaskDto, optional): Task data transfer object
        motioncor_settings (dict, optional): Dictionary of MotionCor settings to override defaults.
            Supported keys: FmDose, PatchesX, PatchesY, SumRangeMinDose, SumRangeMaxDose, Group

    Returns:
        MotionCorInput: Configured task data object
    """
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    # Default settings
    settings = {
        'FmDose': 0.75,
        'PatchesX': 5,
        'PatchesY': 5,
        'SumRangeMinDose': 0,
        'SumRangeMaxDose': 0,
        'Group': 3
    }

    # Update with user-provided settings if any
    if motioncor_settings:
        settings.update(motioncor_settings)


    if session_name is None:
        session_name = file_name.split("_")[0]
    return MotionCorInput(
            image_id=task_dto.image_id,
            image_name=os.path.basename(task_dto.image_path),
            image_path=task_dto.image_path,

            inputFile=image_path,
            OutMrc=os.path.basename(task_dto.image_path),
            Gain=gain_path,
            DefectFile=defects_path,
            PixSize=task_dto.pixel_size* 10**10,
            RotGain=task_dto.rot_gain,
            FlipGain=task_dto.flip_gain,
            **settings
        )


def create_motioncor_task(image_path=None,
                          gain_path=None,
                          defects_path=None,
                          session_name=None,
                          task_id=None,
                          job_id=None,
                          task_dto: ImportTaskDto=None,
                          motioncor_settings: dict = None

                          ):
    """
    Creates a MotionCor task with specified parameters

    Args:
        image_path (str, optional): Path to the input image file
        gain_path (str, optional): Path to the gain reference file
        session_name (str, optional): Session name
        task_id (str, optional): Task ID to use
        job_id (UUID, optional): Job ID to use

    Returns:
        MotioncorTask: Created task object or False if error occurs
        :param task_dto:
    """

    try:
        frame_path = getattr(task_dto, 'frame_path', None)
        frame_name = getattr(task_dto, 'frame_name', None)
        base_path = os.path.dirname(frame_path) if frame_path else None
        logger.info(
            "[MOTIONCOR-8] create_motioncor_task: frame_path=%r frame_name=%r base_path=%r",
            frame_path, frame_name, base_path,
        )

        matching_file = find_matching_file(base_path, frame_name)
        logger.info("[MOTIONCOR-9] find_matching_file result: %r", matching_file)

        if not matching_file:
            raise ValueError(f"motioncor input File not found: base_path={base_path!r} frame_name={frame_name!r}")

        motioncor_task_data = create_motioncor_task_data(
            image_path=matching_file,
            gain_path=gain_path,
            defects_path=defects_path,
            session_name=session_name,
            task_dto=task_dto,
            motioncor_settings=motioncor_settings
        )

        motioncor_task = MotioncorTaskFactory.create_task(
            pid=task_id or str(uuid.uuid4()),
            instance_id=uuid.uuid4(),
            job_id=job_id or uuid.uuid4(),
            data=motioncor_task_data.model_dump(),
            ptype=MOTIONCOR_TASK,
            pstatus=PENDING
        )
        motioncor_task.session_name = session_name or motioncor_task_data.image_name.split("_")[0]
        logger.info(
            "[MOTIONCOR-10] task created: id=%r session=%r inputFile=%r",
            motioncor_task.id, motioncor_task.session_name,
            motioncor_task_data.inputFile,
        )
        return motioncor_task
    except Exception as e:
        logger.error("[MOTIONCOR-ERR] create_motioncor_task failed: %s", e, exc_info=True)
        return False


def dispatch_motioncor_task(task_id,
                            full_image_path,
                            task_dto: ImportTaskDto,
                            gain_path="/gpfs/20241202_53597_gain_multi_ref.tif",
                            defects_path=None,
                            session_name="24dec03a",
                            motioncor_settings: dict = None
                            ):
    """
    Creates and dispatches a MotionCor task based on an import task DTO

    Args:
        task_id (str): ID for the new task
        full_image_path (str): Path to the input image file
        task_dto (ImportTaskDto): Import task data transfer object

    Returns:
        bool: True if task was successfully pushed to queue
    """
    logger.info(
        "[MOTIONCOR-A] dispatch_motioncor_task entry: task_id=%r full_image_path=%r gain_path=%r",
        task_id, full_image_path, gain_path,
    )

    job_id = None

    if task_dto is not None:
        if hasattr(task_dto, 'job_id'):
            job_id = task_dto.job_id
        elif hasattr(task_dto, 'job_dto') and task_dto.job_dto is not None:
            job_id = getattr(task_dto.job_dto, 'job_id', None)

    logger.info("[MOTIONCOR-B] job_id resolved: %r", job_id)

        # Handle debug CTF path replacement if needed
    if app_settings.DEBUG_CTF:
        full_image_path = full_image_path.replace(
            app_settings.DEBUG_CTF_PATH,
            app_settings.DEBUG_CTF_REPLACE
        )
    full_image_path = to_canonical_gpfs_path(full_image_path)
    gain_path = to_canonical_gpfs_path(gain_path)
    defects_path = to_canonical_gpfs_path(defects_path)
    logger.info(
        "[MOTIONCOR-C] canonical paths: full_image_path=%r gain_path=%r defects_path=%r",
        full_image_path, gain_path, defects_path,
    )

    if hasattr(task_dto, 'job_dto') and task_dto.job_dto and hasattr(task_dto.job_dto, 'session_name') and task_dto.job_dto.session_name:
        session_name = task_dto.job_dto.session_name
    logger.info("[MOTIONCOR-D] session_name=%r", session_name)

    motioncor_task = create_motioncor_task(
        image_path=full_image_path,
        task_id=task_id,
        job_id=job_id,
        gain_path=gain_path,
        defects_path=defects_path,
        session_name=session_name,
        task_dto=task_dto,
        motioncor_settings=motioncor_settings
    )

    if motioncor_task:
        logger.info("[MOTIONCOR-E] task created OK — pushing to queue")
        result = push_task_to_task_queue(motioncor_task)
        logger.info("[MOTIONCOR-F] push_task_to_task_queue returned: %r", result)
        return result

    logger.error("[MOTIONCOR-ERR] create_motioncor_task returned False — task not pushed")
    return False
