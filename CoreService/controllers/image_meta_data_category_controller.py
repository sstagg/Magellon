from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from starlette import status
import logging

from database import get_db
from models.pydantic_models import ImageMetaDataCategoryDto
from repositories.image_meta_data_category_repository import ImageMetaDataCategoryRepository
from dependencies.permissions import require_permission
from dependencies.auth import get_current_user_id

logger = logging.getLogger(__name__)
image_meta_data_category_router = APIRouter()


@image_meta_data_category_router.post('/', response_model=ImageMetaDataCategoryDto, status_code=201)
async def create_image_meta_data_category(
    image_meta_data_category_request: ImageMetaDataCategoryDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('metadata_category', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Create image metadata category and save it in the database.

    **Requires:** 'create' permission on 'metadata_category' resource
    **Security:** Only users with category creation permission can access
    """
    logger.info(f"User {user_id} creating metadata category: {image_meta_data_category_request.name}")

    if not image_meta_data_category_request.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Name cannot be empty'
        )

    db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_name(
        db,
        name=image_meta_data_category_request.name
    )
    if db_image_meta_data_category:
        logger.warning(f"User {user_id} attempted to create duplicate category: {image_meta_data_category_request.name}")
        raise HTTPException(status_code=400, detail="Metadata category already exists!")

    try:
        created_category = await ImageMetaDataCategoryRepository.create(
            db=db,
            image_meta_data_category_dto=image_meta_data_category_request
        )
        logger.info(f"Metadata category created by user {user_id}: {created_category.oid}")
        return created_category
    except Exception as e:
        logger.exception(f'Error creating metadata category for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating metadata category'
        )


@image_meta_data_category_router.put('/', response_model=ImageMetaDataCategoryDto, status_code=201)
async def update_image_meta_data_category(
    image_meta_data_category_request: ImageMetaDataCategoryDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('metadata_category', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Update image metadata category and save it in the database.

    **Requires:** 'write' permission on 'metadata_category' resource
    **Security:** Only users with category write permission can access
    """
    logger.info(f"User {user_id} updating metadata category: {image_meta_data_category_request.oid}")
    try:
        updated_category = await ImageMetaDataCategoryRepository.update(
            db=db,
            image_meta_data_category_dto=image_meta_data_category_request
        )
        logger.info(f"Metadata category updated by user {user_id}: {image_meta_data_category_request.oid}")
        return updated_category
    except Exception as e:
        logger.exception(f'Error updating metadata category for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating metadata category'
        )


@image_meta_data_category_router.get('/', response_model=List[ImageMetaDataCategoryDto])
def get_all_image_meta_data_categorys(
    name: Optional[str] = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get all metadata categories in database.

    **Requires:** Authentication (all authenticated users can read)
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching metadata categories")

    if name:
        db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_name(db, name)
        if db_image_meta_data_category:
            return [db_image_meta_data_category]
        return []
    else:
        return ImageMetaDataCategoryRepository.fetch_all(db)


@image_meta_data_category_router.get('/{oid}', response_model=ImageMetaDataCategoryDto)
def get_image_meta_data_category(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get metadata category by ID.

    **Requires:** Authentication
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching metadata category: {oid}")

    db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_id(db, oid)
    if db_image_meta_data_category is None:
        raise HTTPException(status_code=404, detail="Metadata category not found with the given ID")
    return db_image_meta_data_category


@image_meta_data_category_router.delete('/{oid}')
async def delete_image_meta_data_category(
    oid: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('metadata_category', 'delete')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Delete metadata category by ID.

    **Requires:** 'delete' permission on 'metadata_category' resource
    **Security:** Only users with category delete permission can access
    """
    logger.warning(f"User {user_id} deleting metadata category: {oid}")

    db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_id(db, oid)
    if db_image_meta_data_category is None:
        raise HTTPException(status_code=404, detail="Metadata category not found with the given ID")

    await ImageMetaDataCategoryRepository.delete(db, oid)
    logger.info(f"Metadata category {oid} deleted by user {user_id}")
    return {"message": "Metadata category deleted successfully", "deleted_by": str(user_id)}

# @app.get("/image_meta_data_categorys2/", response_model=List[ImageMetaDataCategoryDto])
# def show_image_meta_data_categorys(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records
