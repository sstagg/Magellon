import logging
from core.model_dto import CryoEmCtfTaskData, TaskDto
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt
from service.ctf_service import do_ctf

logger = logging.getLogger(__name__)


async def do_execute_task(task_object: TaskDto):
    try:
        the_data = CryoEmCtfTaskData.model_validate(task_object.data)
        await do_execute(the_data)
        return {"message": "MRC file successfully converted to fft PNG!"}
    except Exception as exc:
        return {"error": str(exc)}


async def do_execute(params: CryoEmCtfTaskData):
    try:
        await do_ctf(params)
        return {"message": "MRC file successfully converted to fft PNG!"}
    except Exception as exc:
        return {"error": str(exc)}
    #     compute_file_fft(mrc_abs_path=request.image_path, abs_out_file_name=request.target_path)


async def check_requirements():
    all_results = []
    # Execute each check function and aggregate results
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    # Add more checks for other requirements here
    return all_results
