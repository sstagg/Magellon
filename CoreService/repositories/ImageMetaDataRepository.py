import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from models.pydantic_models import ImageMetaDataDto
from models.sqlalchemy_models import ImageMetaData


class ImageMetaDataRepository:

    async def create(db: Session, image_meta_data_dto: ImageMetaDataDto):
        if image_meta_data_dto.oid is None:
            image_meta_data_dto.oid = str(uuid.uuid4())
        image_meta_data = ImageMetaData(oid=image_meta_data_dto.oid, name= image_meta_data_dto.name)
        db.add(image_meta_data)
        db.commit()
        db.refresh(image_meta_data)
        return image_meta_data

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(ImageMetaData).filter(ImageMetaData.oid == _id).first()

    def fetch_by_name(db: Session, name: str):
        return db.query(ImageMetaData).filter(ImageMetaData.name == name).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(ImageMetaData).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: UUID):
        db_image_meta_data = db.query(ImageMetaData).filter_by(oid=_id).first()
        db.delete(db_image_meta_data)
        db.commit()

    async def update(db: Session, image_meta_data_dto):
        db.merge(image_meta_data_dto)
        db.commit()
