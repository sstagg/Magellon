import logging
import os
import sys
import uuid
from typing import Optional
from fastapi import Depends, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from magellon_sdk.models import (
    Capability,
    IsolationLevel,
    PluginInfo,
    PluginManifest,
    ResourceHints,
    Transport,
)

from core.database import get_db, get_db_connection
from magellon_sdk.bootstrap import (
    check_operating_system,
    check_python_version,
    check_requirements_txt,
)
from magellon_sdk.models import TaskMessage, PluginInfoSingleton, TaskResultMessage

from core.settings import AppSettingsSingleton
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


def get_manifest() -> PluginManifest:
    """Capability manifest for the result-processor.

    This plugin is a sink: it consumes task results off the RMQ out-
    queues and projects them into the DB / filesystem. Declaring it
    here keeps it visible to the manager even though it never shows
    up as a "task type" a user picks — the shape still applies.
    """
    info = get_plugin_info()
    return PluginManifest(
        info=PluginInfo(
            name=info.name,
            version=info.version,
            developer=info.developer,
            description="Consumes task result envelopes and projects them into DB / filesystem",
        ),
        capabilities=[
            Capability.IDEMPOTENT,
        ],
        supported_transports=[Transport.RMQ],
        default_transport=Transport.RMQ,
        isolation=IsolationLevel.CONTAINER,
        resources=ResourceHints(
            memory_mb=500,
            cpu_cores=1,
        ),
        tags=["sink", "result-processor", "persistence"],
    )


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


async def do_execute(task_result_param: TaskResultMessage):
    try:
        engine = create_engine(get_db_connection())
        session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = session_local()
        processor = TaskOutputProcessor(db_session)
        return processor.process(task_result_param)
    except Exception as e:
        print(f"Error: {e}")


async def check_requirements():
    all_results = []
    # Execute each check function and aggregate results
    all_results.extend(await check_python_version())
    all_results.extend(await check_operating_system())
    all_results.extend(await check_requirements_txt())
    # Add more checks for other requirements here
    return all_results
