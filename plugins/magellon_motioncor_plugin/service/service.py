import logging
import sys

from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    PluginInfo,
    PluginManifest,
    ResourceHints,
    Transport,
)

from core.helper import push_result_to_out_queue
from core.model_dto import TaskDto, PluginInfoSingleton
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt
from service.motioncor_service import do_motioncor
from service.step_events import (
    get_publisher,
    safe_emit_completed,
    safe_emit_failed,
    safe_emit_started,
)


logger = logging.getLogger(__name__)

plugin_info_data = {
    "id": "29105843-518a-4086-b802-ad295883dfe1",
    "name": "Motioncor Plugin",
    "developer": "Behdad Khoshbin b.khoshbin@gmail.com & Puneeth Reddy",
    "copyright": "Copyright © 2024",
    "version": "1.0.2",
    "port_number": 8000,
    "Python version": sys.version
}


def get_plugin_info():
    return PluginInfoSingleton.get_instance(**plugin_info_data)


def get_manifest() -> PluginManifest:
    """Capability manifest for the MotionCor plugin.

    The canonical GPU / memory-intensive plugin — 8k×8k × ~75 frames
    per movie. The manifest's job here is to keep a scheduler from
    ever treating this as something that could run in-process next to
    the backend: one OOM would kill the whole service. Resources are
    deliberately conservative high-end so a bin-packer leaves margin.
    """
    info = get_plugin_info()
    return PluginManifest(
        info=PluginInfo(
            name=info.name,
            version=info.version,
            developer=info.developer,
            description="Movie motion correction via UCSF MotionCor2 / MotionCor3",
        ),
        capabilities=[
            Capability.GPU_REQUIRED,
            Capability.MEMORY_INTENSIVE,
            Capability.CPU_INTENSIVE,
            Capability.LONG_RUNNING,
            Capability.PROGRESS_REPORTING,
            Capability.IDEMPOTENT,
        ],
        supported_transports=[Transport.RMQ, Transport.NATS, Transport.HTTP],
        default_transport=Transport.RMQ,
        isolation=IsolationLevel.CONTAINER,
        resources=ResourceHints(
            memory_mb=32_000,
            gpu_count=1,
            gpu_memory_mb=16_000,
            cpu_cores=4,
            typical_duration_seconds=180.0,
        ),
        tags=["motion-correction", "gpu", "movie"],
    )


async def do_execute(params: TaskDto):
    publisher = await get_publisher()
    await safe_emit_started(publisher, job_id=params.job_id, task_id=params.id)
    try:
        # the_data = CryoEmCtfTaskData.model_validate(params.data)
        result = await do_motioncor(params)
        if result is not None:
            push_result_to_out_queue(result)
            await safe_emit_completed(
                publisher, job_id=params.job_id, task_id=params.id
            )
            return result
        #     compute_file_fft(mrc_abs_path=request.image_path, abs_out_file_name=request.target_path)
        await safe_emit_completed(publisher, job_id=params.job_id, task_id=params.id)
        return {"message": "Motioncor successfully executed"}
    except Exception as exc:
        await safe_emit_failed(
            publisher, job_id=params.job_id, task_id=params.id, error=str(exc)
        )
        return {"error": str(exc)}


async def check_requirements():
    all_results = []
    # Execute each check function and aggregate results
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    # Add more checks for other requirements here
    return all_results
