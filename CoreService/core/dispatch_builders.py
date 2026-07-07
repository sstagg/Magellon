"""Task-dispatch builders: CTF, FFT, ptolemy detection, topaz pick /
denoise, and generic particle picking.

Each ``dispatch_*`` helper canonicalizes wire paths to ``/gpfs/...``,
builds the typed input payload, wraps it in a TaskMessage via the
appropriate factory, and pushes it through
:func:`core.task_dispatch.push_task_to_task_queue` (which raises
:class:`core.exceptions.TaskDispatchError` on dispatch failure).

MotionCor builders live in :mod:`core.motioncor_dispatch`.

Split out of ``core.helper`` (2026-07-06); import from here in new code,
``core.helper`` re-exports for existing call sites.
"""
import os
import uuid

from config import app_settings
from core.paths import canonicalize_paths_in_payload, to_canonical_gpfs_path
from core.task_dispatch import push_task_to_task_queue
from core.task_factory import CtfTaskFactory, FftTaskFactory, TaskFactory
from magellon_sdk.models import (
    CTF_TASK,
    FFT_TASK,
    PENDING,
    CtfInput,
    FftInput,
    TaskCategory,
)
from magellon_sdk.models.tasks import (
    HOLE_DETECTION,
    MICROGRAPH_DENOISING,
    MicrographDenoiseInput,
    PARTICLE_PICKING,
    PtolemyInput,
    SQUARE_DETECTION,
    TOPAZ_PARTICLE_PICKING,
    TopazPickInput,
)
from models.pydantic_models import ImportTaskDto


def dispatch_ctf_task(task_id, full_image_path, task_dto: ImportTaskDto):
    if app_settings.DEBUG_CTF:
        full_image_path = full_image_path.replace(app_settings.DEBUG_CTF_PATH, app_settings.DEBUG_CTF_REPLACE)

    full_image_path = to_canonical_gpfs_path(full_image_path)
    file_name = os.path.splitext(os.path.basename(full_image_path))[0]

    #converting LeginonFrameTransferTaskDto to ctf task
    if hasattr(task_dto, 'job_dto') and task_dto.job_dto and hasattr(task_dto.job_dto, 'session_name') and task_dto.job_dto.session_name:
        session_name = task_dto.job_dto.session_name
    else:
        session_name = file_name.split("_")[0]
    out_file_name = f"{file_name}_ctf_output.mrc"
    ctf_task_data = CtfInput(
        image_id=task_dto.image_id,
        image_name=file_name,
        image_path=full_image_path,
        inputFile=full_image_path,
        outputFile=out_file_name,
        pixelSize= task_dto.pixel_size * 10**10,  #1
        accelerationVoltage=task_dto.acceleration_voltage,
        sphericalAberration = (task_dto.spherical_aberration if task_dto.spherical_aberration is not None else 2.7) , #    2.7,
        amplitudeContrast=task_dto.amplitude_contrast,
        sizeOfAmplitudeSpectrum=task_dto.size_of_amplitude_spectrum,
        minimumResolution=task_dto.minimum_resolution,
        maximumResolution=task_dto.maximum_resolution,
        minimumDefocus=task_dto.minimum_defocus,
        maximumDefocus=task_dto.maximum_defocus,
        defocusSearchStep=task_dto.defocus_search_step,
        binning_x=task_dto.binning_x
        )

    job_id = None

    if task_dto is not None:
        if hasattr(task_dto, 'job_id'):
            job_id = task_dto.job_id
        elif hasattr(task_dto, 'job_dto') and task_dto.job_dto is not None:
            job_id = getattr(task_dto.job_dto, 'job_id', None)

    ctf_task = CtfTaskFactory.create_task(pid=task_dto.task_id, instance_id=uuid.uuid4(), job_id=job_id,
                                          data=ctf_task_data.model_dump(), ptype=CTF_TASK, pstatus=PENDING)
    ctf_task.session_name = session_name
    return push_task_to_task_queue(ctf_task)


def _dispatch_ptolemy_task(
    *,
    category: TaskCategory,
    image_path: str,
    job_id=None,
    task_id=None,
    image_id=None,
    session_name=None,
) -> bool:
    """Shared body for dispatch_square_detection_task / dispatch_hole_detection_task.

    Both ptolemy categories take the same input shape (``PtolemyInput``
    with an MRC path) and differ only in the category that controls which
    queue + which plugin pipeline runs.
    """
    image_path = to_canonical_gpfs_path(image_path)
    file_name = os.path.splitext(os.path.basename(image_path))[0]
    data = PtolemyInput(
        image_id=image_id,
        image_name=file_name,
        image_path=image_path,
        input_file=image_path,
    )
    ptolemy_task = TaskFactory.create_task(
        pid=task_id or uuid.uuid4(),
        instance_id=uuid.uuid4(),
        job_id=job_id,
        data=data.model_dump(),
        ptype=category,
        pstatus=PENDING,
    )
    if session_name:
        ptolemy_task.session_name = session_name
    return push_task_to_task_queue(ptolemy_task)


def dispatch_square_detection_task(
    image_path: str,
    *,
    job_id=None,
    task_id=None,
    image_id=None,
    session_name=None,
) -> bool:
    """Dispatch a low-mag square-detection task to the ptolemy plugin."""
    return _dispatch_ptolemy_task(
        category=SQUARE_DETECTION,
        image_path=image_path,
        job_id=job_id,
        task_id=task_id,
        image_id=image_id,
        session_name=session_name,
    )


def dispatch_hole_detection_task(
    image_path: str,
    *,
    job_id=None,
    task_id=None,
    image_id=None,
    session_name=None,
) -> bool:
    """Dispatch a med-mag hole-detection task to the ptolemy plugin."""
    return _dispatch_ptolemy_task(
        category=HOLE_DETECTION,
        image_path=image_path,
        job_id=job_id,
        task_id=task_id,
        image_id=image_id,
        session_name=session_name,
    )


def dispatch_topaz_pick_task(
    image_path: str,
    *,
    model: str = "resnet16",
    radius: int = 14,
    threshold: float = -3.0,
    scale: int = 8,
    job_id=None,
    task_id=None,
    image_id=None,
    session_name=None,
) -> bool:
    """Dispatch a high-mag particle-picking task to the topaz plugin."""
    image_path = to_canonical_gpfs_path(image_path)
    file_name = os.path.splitext(os.path.basename(image_path))[0]
    data = TopazPickInput(
        image_id=image_id,
        image_name=file_name,
        image_path=image_path,
        input_file=image_path,
        engine_opts={
            "model":     model,
            "radius":    radius,
            "threshold": threshold,
            "scale":     scale,
        },
    )
    task = TaskFactory.create_task(
        pid=task_id or uuid.uuid4(),
        instance_id=uuid.uuid4(),
        job_id=job_id,
        data=data.model_dump(),
        ptype=TOPAZ_PARTICLE_PICKING,
        pstatus=PENDING,
    )
    if session_name:
        task.session_name = session_name
    return push_task_to_task_queue(task)


def dispatch_particle_pick_task(
    image_path: str,
    *,
    image_id=None,
    session_name: str | None = None,
    job_id=None,
    task_id=None,
    target_backend: str = "template-picker",
    ipp_name: str = "Auto-pick",
    engine_opts: dict | None = None,
) -> bool:
    """Dispatch a particle-picking task via the appropriate RMQ queue.

    Routes to the correct plugin queue based on ``target_backend``:
      - ``'topaz'``          → TOPAZ_PARTICLE_PICKING (code 8) → topaz_pick_tasks_queue
      - anything else        → PARTICLE_PICKING (code 3)        → particle_picking_tasks_queue

    The plugin's ``build_pick_result`` echoes ``image_id`` and ``ipp_name``
    back so the result processor can save particles to ``ImageMetaData``
    without a CoreService DB look-up.
    """
    image_path = to_canonical_gpfs_path(image_path)
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    # Topaz has its own TaskCategory (code 8) and queue — must not go
    # to particle_picking_tasks_queue which only template-picker / boxnet consume.
    # Match both the manifest backend_id ("topaz") and the SDK-derived fallback
    # ("topaz-particle-picking" when no manifest backend_id is announced).
    _TOPAZ_BACKEND_IDS = {"topaz", "topaz-particle-picking", "topaz_particle_picking"}
    is_topaz = target_backend in _TOPAZ_BACKEND_IDS

    data = {
        "image_id": str(image_id) if image_id else None,
        "image_name": file_name,
        "image_path": image_path,
        "input_file": image_path,
        "ipp_name": ipp_name,
    }
    # TopazPickInput keeps engine knobs (model/threshold/radius/scale)
    # nested under ``engine_opts``; template-picker / boxnet carry their
    # typed fields at the top level. Spreading topaz opts flat here left
    # engine_opts empty, so the plugin silently used its defaults.
    if is_topaz:
        data["engine_opts"] = engine_opts or {}
    else:
        protected = {"image_id", "image_name", "image_path", "input_file", "ipp_name"}
        data.update({
            key: value
            for key, value in (engine_opts or {}).items()
            if key not in protected
        })
    data = canonicalize_paths_in_payload(data)

    ptype = TOPAZ_PARTICLE_PICKING if is_topaz else PARTICLE_PICKING
    task = TaskFactory.create_task(
        pid=task_id or uuid.uuid4(),
        instance_id=uuid.uuid4(),
        job_id=job_id or uuid.uuid4(),
        data=data,
        ptype=ptype,
        pstatus=PENDING,
    )
    task.target_backend = target_backend
    if session_name:
        task.session_name = session_name
    return push_task_to_task_queue(task)


def dispatch_micrograph_denoise_task(
    image_path: str,
    *,
    output_file: str = None,
    model: str = "unet",
    patch_size: int = 1024,
    padding: int = 128,
    job_id=None,
    task_id=None,
    image_id=None,
    session_name=None,
) -> bool:
    """Dispatch a micrograph-denoise task to the topaz plugin."""
    image_path = to_canonical_gpfs_path(image_path)
    output_file = to_canonical_gpfs_path(output_file)
    file_name = os.path.splitext(os.path.basename(image_path))[0]
    data = MicrographDenoiseInput(
        image_id=image_id,
        image_name=file_name,
        image_path=image_path,
        input_file=image_path,
        output_file=output_file,
        engine_opts={
            "model":      model,
            "patch_size": patch_size,
            "padding":    padding,
        },
    )
    task = TaskFactory.create_task(
        pid=task_id or uuid.uuid4(),
        instance_id=uuid.uuid4(),
        job_id=job_id,
        data=data.model_dump(),
        ptype=MICROGRAPH_DENOISING,
        pstatus=PENDING,
    )
    if session_name:
        task.session_name = session_name
    return push_task_to_task_queue(task)


def dispatch_fft_task(
    image_path: str,
    target_path: str,
    *,
    job_id=None,
    task_id=None,
    image_id=None,
) -> bool:
    """Dispatch an FFT task to the fft plugin over RMQ.

    Small, stand-alone analog of :func:`dispatch_ctf_task` — the FFT
    plugin is a test bed for the async pipeline, so this helper exists
    mainly to drive it from the /fft/dispatch REST endpoint.

    ``image_path`` is the input (mrc/tiff/png), ``target_path`` is
    where the plugin should write the FFT PNG. Both are required;
    they're explicit here because the plugin has no knowledge of
    CoreService's FFT_SUB_URL conventions.
    """
    image_path = to_canonical_gpfs_path(image_path)
    target_path = to_canonical_gpfs_path(target_path)
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    fft_data = FftInput(
        image_id=image_id,
        image_name=file_name,
        image_path=image_path,
        target_path=target_path,
        target_name=os.path.basename(target_path),
    )

    fft_task = FftTaskFactory.create_task(
        pid=task_id or uuid.uuid4(),
        instance_id=uuid.uuid4(),
        job_id=job_id,
        data=fft_data.model_dump(),
        ptype=FFT_TASK,
        pstatus=PENDING,
    )
    return push_task_to_task_queue(fft_task)
