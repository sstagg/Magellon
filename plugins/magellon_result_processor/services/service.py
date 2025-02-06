import json
import logging
import os
import shutil
import sys
import uuid
from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.database import get_db, get_db_connection
from core.helper import append_json_to_file
from core.model_dto import TaskDto, PluginInfoSingleton, TaskResultDto
from core.settings import AppSettingsSingleton
from core.setup_plugin import check_python_version, check_operating_system, check_requirements_txt
from core.sqlalchemy_models import Camera, ImageJobTask, ImageMetaData, Msession
from services.task_output_processor import TaskOutputProcessor

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

def is_valid_json(my_json: str) -> bool:
    try:
        json.loads(my_json)
        return True
    except ValueError:
        return False

async def do_execute(task_result_param: TaskResultDto):
    engine = create_engine(get_db_connection())
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = session_local()
    processor = TaskOutputProcessor(db_session)
    return processor.process(task_result_param)

# async def do_execute(task_result_param: TaskResultDto):
#     try:
#         # print(task_result_param)
#         engine = create_engine(get_db_connection())
#         session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#         db = session_local()
#
#         file_name = os.path.splitext(os.path.basename(task_result_param.image_path))[0]
#         destination_dir = os.path.join(AppSettingsSingleton.get_instance().MAGELLON_HOME_DIR,
#                                        task_result_param.session_name,"ctf",
#                                        file_name )
#         try:
#             # Create the destination directory if it doesn't exist
#             if not os.path.exists(destination_dir):
#                 os.makedirs(destination_dir)
#
#             #For Debugging purposes Write the model dump JSON to a file in the destination directory
#             append_json_to_file( os.path.join(destination_dir,"ctf_message.json") , task_result_param.model_dump_json())
#         except Exception as e:
#             print(f"Error: {e}")
#         # for debugging purposes we save the message
#
#
#         for ofile in task_result_param.output_files:
#             # copy files
#             move_file_to_directory(ofile.path, destination_dir)
#
#         output_data = task_result_param.output_data
#         if output_data is not None and output_data != "":
#             # Create a new ImageMetaData instance
#             image_meta_data = ImageMetaData(
#                 oid=uuid.uuid4(),
#                 name="CTF Data",
#                 data=json.dumps(output_data).encode("utf-8"),
#                 image_id=task_result_param.image_id,
#                 # task_id=task_result_param.task_id
#             )
#             try:
#                 db.add(image_meta_data)
#                 db.commit()
#             # ... your database operations using `db` here ...
#             except Exception as exc:
#                 return {"error": str(exc)}
#         if task_result_param.meta_data and len(task_result_param.meta_data) > 0:
#             meta_list_dicts = [meta.dict(exclude_none=True) for meta in task_result_param.meta_data]
#             json_str = json.dumps(meta_list_dicts, indent=4)
#             # Create a new ImageMetaData instance
#             ctf_meta_data = ImageMetaData(
#                 oid=uuid.uuid4(),
#                 name="CTF Meta Data",
#                 data_json=json.loads(json_str),
#                 # data_json=json.dumps(task_result_param.meta_data).encode("utf-8"),
#                 image_id=task_result_param.image_id,
#                 # task_id=task_result_param.task_id
#             )
#             try:
#                 db.add(ctf_meta_data)
#                 db.commit()
#             except Exception as exc:
#                 return {"error": str(exc)}
#
#         # try:
#         #     db_task : ImageJobTask= db.query(ImageJobTask).filter(ImageJobTask.oid == task_result_param.task_id).first()
#         #     db_task.stage = 5
#         #     db.commit()
#         # except Exception as exc:
#         #     return {"error": str(exc)}
#         return {"message": "CTF successfully executed"}
#     except Exception as exc:
#         return {"error": str(exc)}
#     finally:
#         db.close()
#

async def check_requirements():
    all_results = []
    # Execute each check function and aggregate results
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    # Add more checks for other requirements here
    return all_results
