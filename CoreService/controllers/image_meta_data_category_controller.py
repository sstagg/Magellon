from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from models.pydantic_models import ImageMetaDataCategoryDto
from repositories.image_meta_data_category_repository import ImageMetaDataCategoryRepository

from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
image_meta_data_category_router = APIRouter()


@image_meta_data_category_router.post('/', response_model=ImageMetaDataCategoryDto, status_code=201)
async def create_image_meta_data_category(image_meta_data_category_request: ImageMetaDataCategoryDto, db: Session = Depends(get_db)):
    """
    Create a Camera and save it in the database
    """
    logger.info("Creating image_meta_data_category in database")
    if not image_meta_data_category_request.name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Name cannot be empty')
    db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_name(db, name=image_meta_data_category_request.name)
    if db_image_meta_data_category:
        raise HTTPException(status_code=400, detail="Camera already exists!")

        # Create image_meta_data_category in the database
    try:
        created_image_meta_data_category = await ImageMetaDataCategoryRepository.create(db=db, image_meta_data_category_dto=image_meta_data_category_request)
    except Exception as e:
        logger.exception('Error creating image_meta_data_category in database')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Error creating image_meta_data_category')

    return created_image_meta_data_category


@image_meta_data_category_router.put('/', response_model=ImageMetaDataCategoryDto, status_code=201)
async def update_image_meta_data_category(image_meta_data_category_request: ImageMetaDataCategoryDto, db: Session = Depends(get_db)):
    """
    Update a Camera and save it in the database
    """
    return await ImageMetaDataCategoryRepository.update(db=db, image_meta_data_category_dto=image_meta_data_category_request)




@image_meta_data_category_router.get('/', response_model=List[ImageMetaDataCategoryDto])
def get_all_image_meta_data_categorys(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the image_meta_data_categorys image_meta_data_categoryd in database
    """
    if name:
        image_meta_data_categorys = []
        db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_name(db, name)
        print(db_image_meta_data_category)
        image_meta_data_categorys.append(db_image_meta_data_category)
        return image_meta_data_categorys
    else:
        return ImageMetaDataCategoryRepository.fetch_all(db)


@image_meta_data_category_router.get('/{oid}', response_model=ImageMetaDataCategoryDto)
def get_image_meta_data_category(oid: UUID, db: Session = Depends(get_db)):
    """
    Get the image_meta_data_category with the given ID provided by User image_meta_data_categoryd in database
    """
    db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_id(db, oid)
    if db_image_meta_data_category is None:
        raise HTTPException(status_code=404, detail="image_meta_data_category not found with the given ID")
    return db_image_meta_data_category


@image_meta_data_category_router.delete('/{oid}')
async def delete_image_meta_data_category(oid: UUID, db: Session = Depends(get_db)):
    """
    Delete the Item with the given ID provided by User image_meta_data_categoryd in database
    """
    db_image_meta_data_category = ImageMetaDataCategoryRepository.fetch_by_id(db, oid)
    if db_image_meta_data_category is None:
        raise HTTPException(status_code=404, detail="image_meta_data_category not found with the given ID")
    await ImageMetaDataCategoryRepository.delete(db, oid)
    return "image_meta_data_category deleted successfully!"

# @app.get("/image_meta_data_categorys2/", response_model=List[ImageMetaDataCategoryDto])
# def show_image_meta_data_categorys(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records
