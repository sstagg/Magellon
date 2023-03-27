from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import sessionmaker, Session

from database import session_local
from models.pydantic_models import CameraDto
from repositories.camera_repository import CameraRepository

from fastapi import APIRouter

camera_router = APIRouter()


def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()


@camera_router.post('/cameras', tags=["Camera"], response_model=CameraDto, status_code=201)
async def create_camera(camera_request: CameraDto, db: Session = Depends(get_db)):
    """
    Create a Camera and save it in the database
    """
    db_camera = CameraRepository.fetch_by_name(db, name=camera_request.name)
    print(db_camera)
    if db_camera:
        raise HTTPException(status_code=400, detail="Camera already exists!")

    return await CameraRepository.create(db=db, camera_dto=camera_request)


@camera_router.put('/cameras', tags=["Camera"], response_model=CameraDto, status_code=201)
async def update_camera(camera_request: CameraDto, db: Session = Depends(get_db)):
    """
    Update a Camera and save it in the database
    """

    return await CameraRepository.update(db=db, camera_dto=camera_request)


@camera_router.get('/cameras', tags=["Camera"], response_model=List[CameraDto])
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


@camera_router.get('/cameras/{oid}', tags=["Camera"], response_model=CameraDto)
def get_camera(oid: UUID, db: Session = Depends(get_db)):
    """
    Get the camera with the given ID provided by User camerad in database
    """
    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="camera not found with the given ID")
    return db_camera


@camera_router.delete('/cameras/{oid}', tags=["Camera"])
async def delete_camera(oid: UUID, db: Session = Depends(get_db)):
    """
    Delete the Item with the given ID provided by User camerad in database
    """
    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="camera not found with the given ID")
    await CameraRepository.delete(db, oid)
    return "camera deleted successfully!"
