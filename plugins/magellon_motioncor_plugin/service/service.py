import logging
from core.model_dto import CryoEmMotionCorTaskData, TaskDto, PluginInfoSingleton
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt
from service.motioncor_service import do_motioncor

logger = logging.getLogger(__name__)

plugin_info_data = {
    "id": "29105843-518a-4086-b802-bd295883dfe1",
    "name": "MotionCor Plugin",
    "developer": "Behdad Khoshbin b.khoshbin@gmail.com & Puneeth ",
    "copyright": "Copyright © 2024",
    "version": "1.0.2",
    "port_number": 8000
}


def get_plugin_info():
    return PluginInfoSingleton.get_instance(**plugin_info_data)


async def do_execute_task(task_object: TaskDto):
    try:
        the_data = CryoEmMotionCorTaskData.model_validate(task_object.data)
        await do_execute(the_data)
        return {"message": "MotionCor!"}
    except Exception as exc:
        return {"error": str(exc)}


async def do_execute(params: CryoEmMotionCorTaskData):
    try:
        await do_motioncor(params)
        return {"message": "MotionCor successfully executed"}
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

