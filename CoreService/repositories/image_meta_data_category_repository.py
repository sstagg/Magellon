import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from models.pydantic_models import ImageMetaDataCategoryDto
from models.sqlalchemy_models import ImageMetaDataCategory


class ImageMetaDataCategoryRepository:

    async def create(db: Session, image_meta_data_category_dto: ImageMetaDataCategoryDto):
        if image_meta_data_category_dto.oid is None:
            image_meta_data_category_dto.oid = str(uuid.uuid4())
        image_meta_data_category = ImageMetaDataCategory(oid=image_meta_data_category_dto.oid, name= image_meta_data_category_dto.name)
        db.add(image_meta_data_category)
        db.commit()
        db.refresh(image_meta_data_category)
        return image_meta_data_category

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(ImageMetaDataCategory).filter(ImageMetaDataCategory.oid == _id).first()

    def fetch_by_name(db: Session, name: str):
        return db.query(ImageMetaDataCategory).filter(ImageMetaDataCategory.name == name).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(ImageMetaDataCategory).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: UUID):
        db_image_meta_data_category = db.query(ImageMetaDataCategory).filter_by(oid=_id).first()
        db.delete(db_image_meta_data_category)
        db.commit()

    async def update(db: Session, image_meta_data_category_dto):
        db.merge(image_meta_data_category_dto)
        db.commit()
