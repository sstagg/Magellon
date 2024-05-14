from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from models.pydantic_models import ImageMetaDataDto

from fastapi import APIRouter
import logging

from repositories.image_metadata_repository  import ImageMetaDataRepository

logger = logging.getLogger(__name__)
image_meta_data_router = APIRouter()


@image_meta_data_router.post('/', response_model=ImageMetaDataDto, status_code=201)
async def create_image_meta_data(image_meta_data_request: ImageMetaDataDto, db: Session = Depends(get_db)):
    """
    Create a Camera and save it in the database
    """
    logger.info("Creating image_meta_data in database")
    if not image_meta_data_request.name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Name cannot be empty')
    db_image_meta_data = ImageMetaDataRepository.fetch_by_name(db, name=image_meta_data_request.name)
    if db_image_meta_data:
        raise HTTPException(status_code=400, detail="Camera already exists!")

        # Create image_meta_data in the database
    try:
        created_image_meta_data = await ImageMetaDataRepository.create(db=db, image_meta_data_dto=image_meta_data_request)
    except Exception as e:
        logger.exception('Error creating image_meta_data in database')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Error creating image_meta_data')

    return created_image_meta_data


@image_meta_data_router.put('/', response_model=ImageMetaDataDto, status_code=201)
async def update_image_meta_data(image_meta_data_request: ImageMetaDataDto, db: Session = Depends(get_db)):
    """
    Update a Camera and save it in the database
    """
    return await ImageMetaDataRepository.update(db=db, image_meta_data_dto=image_meta_data_request)




@image_meta_data_router.get('/', response_model=List[ImageMetaDataDto])
def get_all_image_meta_datas(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the image_meta_datas image_meta_datad in database
    """
    if name:
        image_meta_datas = []
        db_image_meta_data = ImageMetaDataRepository.fetch_by_name(db, name)
        print(db_image_meta_data)
        image_meta_datas.append(db_image_meta_data)
        return image_meta_datas
    else:
        return ImageMetaDataRepository.fetch_all(db)


@image_meta_data_router.get('/{oid}', response_model=ImageMetaDataDto)
def get_image_meta_data(oid: UUID, db: Session = Depends(get_db)):
    """
    Get the image_meta_data with the given ID provided by User image_meta_datad in database
    """
    db_image_meta_data = ImageMetaDataRepository.fetch_by_id(db, oid)
    if db_image_meta_data is None:
        raise HTTPException(status_code=404, detail="image_meta_data not found with the given ID")
    return db_image_meta_data


@image_meta_data_router.delete('/{oid}')
async def delete_image_meta_data(oid: UUID, db: Session = Depends(get_db)):
    """
    Delete the Item with the given ID provided by User image_meta_datad in database
    """
    db_image_meta_data = ImageMetaDataRepository.fetch_by_id(db, oid)
    if db_image_meta_data is None:
        raise HTTPException(status_code=404, detail="image_meta_data not found with the given ID")
    await ImageMetaDataRepository.delete(db, oid)
    return "image_meta_data deleted successfully!"

# @app.get("/image_meta_datas2/", response_model=List[ImageMetaDataDto])
# def show_image_meta_datas(db: Session = Depends(get_db)):
#     records = db.query(Camera).all()
#     return records
