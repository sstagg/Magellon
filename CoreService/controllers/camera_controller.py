from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import sessionmaker, Session
from starlette import status

from database import session_local
from models.pydantic_models import CameraDto
from repositories.camera_repository import CameraRepository

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

camera_router = APIRouter()


def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()


@camera_router.post('/',  response_model=CameraDto, status_code=201)
async def create_camera(camera_request: CameraDto, db: Session = Depends(get_db)):
    """
    Create a Camera and save it in the database
    """
    logger.info("Creating camera in database")
    # Validate input data
    if not camera_request.name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Name cannot be empty')
    db_camera = CameraRepository.fetch_by_name(db, name=camera_request.name)
    if db_camera:
        raise HTTPException(status_code=400, detail="Camera already exists!")

        # Create camera in the database
    try:
        created_camera = await CameraRepository.create(db=db, camera_dto=camera_request)
    except Exception as e:
        logger.exception('Error creating camera in database')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Error creating camera')

    return created_camera

    # return await CameraRepository.create(db=db, camera_dto=camera_request)


@camera_router.put('/',  response_model=CameraDto, status_code=201)
async def update_camera(camera_request: CameraDto, db: Session = Depends(get_db)):
    """
    Update a Camera and save it in the database
    """

    return await CameraRepository.update(db=db, camera_dto=camera_request)


@camera_router.get('/',  response_model=List[CameraDto])
def get_all_cameras(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the cameras camerad in database
    """
    if name:
        cameras = []
        db_camera = CameraRepository.fetch_by_name(db, name)
        print(db_camera)
        cameras.append(db_camera)
        return cameras
    else:
        return CameraRepository.fetch_all(db)


@camera_router.get('/{oid}',  response_model=CameraDto)
def get_camera(oid: UUID, db: Session = Depends(get_db)):
    """
    Get the camera with the given ID provided by User camerad in database
    """
    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="camera not found with the given ID")
    return db_camera


@camera_router.delete('/{oid}')
async def delete_camera(oid: UUID, db: Session = Depends(get_db)):
    """
    Delete the Item with the given ID provided by User camerad in database
    """
    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="camera not found with the given ID")
    await CameraRepository.delete(db, oid)
    return "camera deleted successfully!"
