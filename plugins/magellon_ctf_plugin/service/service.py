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
from magellon_sdk.bootstrap import (
    check_operating_system,
    check_python_version,
    check_requirements_txt,
)
from magellon_sdk.models import TaskMessage, PluginInfoSingleton
from service.ctf_service import do_ctf
from service.step_events import (
    get_publisher,
    safe_emit_completed,
    safe_emit_failed,
    safe_emit_progress,
    safe_emit_started,
)

logger = logging.getLogger(__name__)

plugin_info_data = {
    "id": "29105843-518a-4086-b802-ad295883dfe1",
    "name": "CTF Plugin",
    "developer": "Behdad Khoshbin b.khoshbin@gmail.com & Puneeth Reddy",
    "copyright": "Copyright © 2024",
    "version": "1.0.2",
    "port_number": 8000,
    "Python version": sys.version
}


def get_plugin_info():
    return PluginInfoSingleton.get_instance(**plugin_info_data)


def get_manifest() -> PluginManifest:
    """Capability manifest for the containerized CTF plugin.

    Same shape as PluginBase.manifest() on in-house plugins — the
    CoreService plugin manager consumes this via GET /manifest so
    out-of-tree plugins appear in the registry uniformly.
    """
    info = get_plugin_info()
    return PluginManifest(
        info=PluginInfo(
            name=info.name,
            version=info.version,
            developer=info.developer,
            description="Defocus/astigmatism estimation via the ctffind4 binary",
        ),
        capabilities=[
            Capability.CPU_INTENSIVE,
            Capability.IDEMPOTENT,
        ],
        supported_transports=[Transport.RMQ, Transport.NATS, Transport.HTTP],
        default_transport=Transport.RMQ,
        isolation=IsolationLevel.CONTAINER,
        resources=ResourceHints(
            memory_mb=1_000,
            cpu_cores=1,
            typical_duration_seconds=10.0,
        ),
        tags=["ctf", "imaging"],
    )


async def do_execute(params: TaskMessage):
    publisher = await get_publisher()
    job_id, task_id = params.job_id, params.id
    await safe_emit_started(publisher, job_id=job_id, task_id=task_id)
    try:
        # Coarse-grained progress so the UI shows movement during the
        # ~10s ctffind run instead of staying frozen at "started".
        # Fine-grained per-iteration progress would require parsing
        # ctffind4 stdout — leave that for a future refinement.
        await safe_emit_progress(
            publisher, job_id=job_id, task_id=task_id,
            percent=10.0, message="running ctffind",
        )
        result = await do_ctf(params)
        await safe_emit_progress(
            publisher, job_id=job_id, task_id=task_id,
            percent=85.0, message="publishing result",
        )
        if result is not None:
            push_result_to_out_queue(result)
        await safe_emit_completed(publisher, job_id=job_id, task_id=task_id)
        return {"message": "CTF successfully executed"}
    except Exception as exc:
        await safe_emit_failed(
            publisher, job_id=job_id, task_id=task_id, error=str(exc)
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
