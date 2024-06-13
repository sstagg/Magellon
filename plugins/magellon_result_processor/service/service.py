import logging
import sys

from core.helper import push_result_to_out_queue
from core.model_dto import TaskDto, PluginInfoSingleton
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt


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


async def do_execute(params: TaskDto):
    try:
        # the_data = CryoEmCtfTaskData.model_validate(params.data)
        # result = await do_ctf(params)

        # if result is not None:
        #     push_result_to_out_queue(result)
        #     compute_file_fft(mrc_abs_path=request.image_path, abs_out_file_name=request.target_path)
        return {"message": "CTF successfully executed"}
    except Exception as exc:
        return {"error": str(exc)}


async def check_requirements():
    all_results = []
    # Execute each check function and aggregate results
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    # Add more checks for other requirements here
    return all_results
