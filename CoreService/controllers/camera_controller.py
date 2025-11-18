from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from starlette import status
import logging

from database import get_db
from models.pydantic_models import CameraDto
from repositories.camera_repository import CameraRepository
from dependencies.permissions import require_permission
from dependencies.auth import get_current_user_id

logger = logging.getLogger(__name__)
camera_router = APIRouter()


@camera_router.post('/', response_model=CameraDto, status_code=201)
async def create_camera(
    camera_request: CameraDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('camera', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Create a Camera and save it in the database.

    **Requires:** 'create' permission on 'camera' resource
    **Security:** Only users with camera creation permission can access
    """
    logger.info(f"User {user_id} creating camera: {camera_request.name}")

    # Validate input data
    if not camera_request.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Name cannot be empty'
        )

    # Check if camera already exists
    db_camera = CameraRepository.fetch_by_name(db, name=camera_request.name)
    if db_camera:
        logger.warning(f"User {user_id} attempted to create duplicate camera: {camera_request.name}")
        raise HTTPException(status_code=400, detail="Camera already exists!")

    # Create camera in the database
    try:
        created_camera = await CameraRepository.create(db=db, camera_dto=camera_request)
        logger.info(f"Camera created by user {user_id}: {created_camera.oid}")
        return created_camera
    except Exception as e:
        logger.exception(f'Error creating camera for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating camera'
        )


@camera_router.put('/', response_model=CameraDto, status_code=201)
async def update_camera(
    camera_request: CameraDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('camera', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Update a Camera and save it in the database.

    **Requires:** 'write' permission on 'camera' resource
    **Security:** Only users with camera write permission can access
    """
    logger.info(f"User {user_id} updating camera: {camera_request.oid}")
    try:
        updated_camera = await CameraRepository.update(db=db, camera_dto=camera_request)
        logger.info(f"Camera updated by user {user_id}: {camera_request.oid}")
        return updated_camera
    except Exception as e:
        logger.exception(f'Error updating camera for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating camera'
        )


@camera_router.get('/', response_model=List[CameraDto])
def get_all_cameras(
    name: Optional[str] = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get all cameras in database.

    **Requires:** Authentication (all authenticated users can read)
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching cameras")

    if name:
        db_camera = CameraRepository.fetch_by_name(db, name)
        if db_camera:
            return [db_camera]
        return []
    else:
        return CameraRepository.fetch_all(db)


@camera_router.get('/{oid}', response_model=CameraDto)
def get_camera(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get a camera by ID.

    **Requires:** Authentication
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching camera: {oid}")

    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found with the given ID")
    return db_camera


@camera_router.delete('/{oid}')
async def delete_camera(
    oid: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('camera', 'delete')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Delete a camera by ID.

    **Requires:** 'delete' permission on 'camera' resource
    **Security:** Only users with camera delete permission can access
    """
    logger.warning(f"User {user_id} deleting camera: {oid}")

    db_camera = CameraRepository.fetch_by_id(db, oid)
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found with the given ID")

    await CameraRepository.delete(db, oid)
    logger.info(f"Camera {oid} deleted by user {user_id}")
    return {"message": "Camera deleted successfully", "deleted_by": str(user_id)}

# @app.get("/cameras2/", response_model=List[CameraDto])
# def show_cameras(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records
