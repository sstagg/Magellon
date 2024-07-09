import logging
import os
import shutil
import sys
import uuid
from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.helper import push_result_to_out_queue
from core.model_dto import TaskDto, PluginInfoSingleton, TaskResultDto
from core.settings import AppSettingsSingleton
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt
from core.sqlalchemy_models import Camera, ImageJobTask, ImageMetaData , Msession

logger = logging.getLogger(__name__)

plugin_info_data = {
    "id": "29105843-518a-4086-b802-ad295883dfe1",
    "name": "Output Processor Plugin",
    "developer": "Behdad Khoshbin b.khoshbin@gmail.com & Puneeth Reddy",
    "copyright": "Copyright © 2024",
    "version": "1.0.2",
    "port_number": 8000,
    "Python version": sys.version
}


def get_plugin_info():
    return PluginInfoSingleton.get_instance(**plugin_info_data)


async def get_all_cameras(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the cameras camerad in database
    """
    if name:
        cameras = []
        db_camera = db.query(Camera).filter(Camera.name == name).first()
        print(db_camera)
        cameras.append(db_camera)
        return cameras
    else:
        skip: int = 0
        limit: int = 100
        return db.query(Camera).offset(skip).limit(limit).all()

def move_file_to_directory(file_path, destination_dir):
    # Extract the file name from the full file path
    filename = os.path.basename(file_path)
    # Create the destination path by joining the destination directory and the file name
    destination_path = os.path.join(destination_dir, filename)

    try:
        # Create the destination directory if it doesn't exist
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        shutil.move(file_path, destination_path)
        print(f"File moved from {file_path} to {destination_path}")
    except Exception as e:
        print(f"Error: {e}")


async def do_execute(task_result_param: TaskResultDto, db: Session = Depends(get_db)):
    try:
        # db_m_session = db.query(Msession).filter(Msession.name == name).first()
        # db_task : ImageJobTask= db.query(ImageJobTask).filter(ImageJobTask.oid == task_result_param.task_id).first()
        # db_task.image_id

        destination_dir=os.path.join(AppSettingsSingleton.get_instance().ROOT_DIR, task_result_param.session_name,"ctf")
        #task_result_param.output_data
        for ofile in task_result_param.output_files:
            # copy files
            move_file_to_directory(ofile.path,destination_dir)
            print("hello")

        # for meta_data in task_result_param.meta_data:
        #     # sd
        #     db_meta = ImageMetaData(oid=uuid.uuid4())
        #     #db_meta.name=meta_data.
        #     db_meta.task_id=task_result_param.task_id
        #     db.add(db_meta)
        #     db.commit()


            # db_meta.created_date

        # set tht task to done ,

        # db_task.stage = 5
        # db.commit()



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
