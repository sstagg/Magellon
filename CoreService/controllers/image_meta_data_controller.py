from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from starlette import status
import logging

from database import get_db
from models.pydantic_models import ImageMetaDataDto
from repositories.image_metadata_repository import ImageMetaDataRepository
from dependencies.permissions import require_permission
from dependencies.auth import get_current_user_id

logger = logging.getLogger(__name__)
image_meta_data_router = APIRouter()


@image_meta_data_router.post('/', response_model=ImageMetaDataDto, status_code=201)
async def create_image_meta_data(
    image_meta_data_request: ImageMetaDataDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('image_metadata', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Create image metadata and save it in the database.

    **Requires:** 'create' permission on 'image_metadata' resource
    **Security:** Only users with metadata creation permission can access
    """
    logger.info(f"User {user_id} creating image metadata: {image_meta_data_request.name}")

    if not image_meta_data_request.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Name cannot be empty'
        )

    db_image_meta_data = ImageMetaDataRepository.fetch_by_name(db, name=image_meta_data_request.name)
    if db_image_meta_data:
        logger.warning(f"User {user_id} attempted to create duplicate metadata: {image_meta_data_request.name}")
        raise HTTPException(status_code=400, detail="Image metadata already exists!")

    try:
        created_image_meta_data = await ImageMetaDataRepository.create(
            db=db,
            image_meta_data_dto=image_meta_data_request
        )
        logger.info(f"Image metadata created by user {user_id}: {created_image_meta_data.oid}")
        return created_image_meta_data
    except Exception as e:
        logger.exception(f'Error creating image metadata for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating image metadata'
        )


@image_meta_data_router.put('/', response_model=ImageMetaDataDto, status_code=201)
async def update_image_meta_data(
    image_meta_data_request: ImageMetaDataDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('image_metadata', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Update image metadata and save it in the database.

    **Requires:** 'write' permission on 'image_metadata' resource
    **Security:** Only users with metadata write permission can access
    """
    logger.info(f"User {user_id} updating image metadata: {image_meta_data_request.oid}")
    try:
        updated_metadata = await ImageMetaDataRepository.update(
            db=db,
            image_meta_data_dto=image_meta_data_request
        )
        logger.info(f"Image metadata updated by user {user_id}: {image_meta_data_request.oid}")
        return updated_metadata
    except Exception as e:
        logger.exception(f'Error updating image metadata for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating image metadata'
        )


@image_meta_data_router.get('/', response_model=List[ImageMetaDataDto])
def get_all_image_meta_datas(
    name: Optional[str] = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get all image metadata in database.

    **Requires:** Authentication (all authenticated users can read)
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching image metadata")

    if name:
        db_image_meta_data = ImageMetaDataRepository.fetch_by_name(db, name)
        if db_image_meta_data:
            return [db_image_meta_data]
        return []
    else:
        return ImageMetaDataRepository.fetch_all(db)


@image_meta_data_router.get('/{oid}', response_model=ImageMetaDataDto)
def get_image_meta_data(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get image metadata by ID.

    **Requires:** Authentication
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching image metadata: {oid}")

    db_image_meta_data = ImageMetaDataRepository.fetch_by_id(db, oid)
    if db_image_meta_data is None:
        raise HTTPException(status_code=404, detail="Image metadata not found with the given ID")
    return db_image_meta_data


@image_meta_data_router.delete('/{oid}')
async def delete_image_meta_data(
    oid: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('image_metadata', 'delete')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Delete image metadata by ID.

    **Requires:** 'delete' permission on 'image_metadata' resource
    **Security:** Only users with metadata delete permission can access
    """
    logger.warning(f"User {user_id} deleting image metadata: {oid}")

    db_image_meta_data = ImageMetaDataRepository.fetch_by_id(db, oid)
    if db_image_meta_data is None:
        raise HTTPException(status_code=404, detail="Image metadata not found with the given ID")

    await ImageMetaDataRepository.delete(db, oid)
    logger.info(f"Image metadata {oid} deleted by user {user_id}")
    return {"message": "Image metadata deleted successfully", "deleted_by": str(user_id)}

# @app.get("/image_meta_datas2/", response_model=List[ImageMetaDataDto])
# def show_image_meta_datas(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records
