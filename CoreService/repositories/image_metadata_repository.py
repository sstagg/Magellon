import uuid
from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.pydantic_models import ImageMetaDataDto
from models.sqlalchemy_models import ImageMetadata


class ImageMetaDataRepository:
    @staticmethod
    async def create(db: Session, image_meta_data_dto: ImageMetaDataDto):
        if image_meta_data_dto.Oid is None:
            image_meta_data_dto.Oid = str(uuid.uuid4())
        image_meta_data_entity = ImageMetadata(**image_meta_data_dto.dict())
        db.add(image_meta_data_entity)
        db.commit()
        db.refresh(image_meta_data_entity)
        return image_meta_data_entity

    @staticmethod
    def fetch_by_id(db: Session, oid: UUID):
        return db.query(ImageMetadata).filter(ImageMetadata.OID == oid).first()

    @staticmethod
    def fetch_all(db: Session, skip: int = 0, limit: int = 100) -> List[ImageMetadata]:
        return db.query(ImageMetadata).offset(skip).limit(limit).all()

    @staticmethod
    async def delete(db: Session, oid: uuid.UUID):
        image_meta_data_entity = db.query(ImageMetadata).filter(ImageMetadata.OID == oid).first()
        if image_meta_data_entity:
            db.delete(image_meta_data_entity)
            db.commit()
        else:
            raise HTTPException(status_code=404, detail="Image Metadata not found")

    @staticmethod
    async def update(db: Session, image_meta_data_dto: ImageMetaDataDto):
        db.merge(image_meta_data_dto)
        db.commit()

    async def update_by_data(db: Session, _id: UUID, req_body: str):
        try:
            db_item = db.query(ImageMetadata).filter(ImageMetadata.OID == _id).first()
            if not db_item:
                raise HTTPException(status_code=404, detail="Image Metadata  not found")
            db_item.data = req_body
            db.commit()
            db.refresh(db_item)
        except Exception as e:
            db.rollback()
    @staticmethod
    async def update(db: Session, oid: UUID, image_meta_data_dto: ImageMetaDataDto):
        image_meta_data_entity = db.query(ImageMetadata).filter(ImageMetadata.OID == oid).first()
        if image_meta_data_entity:
            for key, value in image_meta_data_dto.dict(exclude_unset=True).items():
                setattr(image_meta_data_entity, key, value)
            db.commit()
            db.refresh(image_meta_data_entity)
            return image_meta_data_entity
        else:
            raise HTTPException(status_code=404, detail="Image Metadata not found")